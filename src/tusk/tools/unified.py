"""Unified tools for Tusk - single tools with action parameters like Goldfish."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List
from uuid import uuid4

from ..models.task import Task, TaskStatus, TaskPriority
from ..models.checkpoint import Checkpoint
from ..models.plan import Plan, PlanStatus, PlanStep
from .base import BaseTool

logger = logging.getLogger(__name__)


class UnifiedTaskTool(BaseTool):
    """Unified todo tool - handles all todo operations via action parameter."""
    
    def register(self, mcp_server) -> None:
        """Register the unified todo tool."""
        
        @mcp_server.tool
        async def todo(
            action: str,
            task: Optional[str] = None,
            task_id: Optional[str] = None,
            status: Optional[str] = None,
            query: Optional[str] = None,
            limit: int = 10
        ) -> str:
            """Manage tasks efficiently with one simple tool.
            
            Args:
                action: What to do - "add", "list", "start", "complete", "update", "search"
                task: Task content (for add action)
                task_id: Task ID (for start/complete/update actions)
                status: New status (for update action - "pending", "in_progress", "completed")
                query: Search query (for search action)
                limit: Max results (for list/search actions)
            
            Examples:
                todo(action="add", task="Fix the bug in login system")
                todo(action="list")
                todo(action="start", task_id="abc123")
                todo(action="complete", task_id="abc123")
                todo(action="update", task_id="abc123", status="in_progress")
                todo(action="search", query="bug", limit=5)
            """
            try:
                if action == "add":
                    return await self._add_task(task)
                elif action == "list":
                    return await self._list_tasks(limit)
                elif action == "start":
                    return await self._start_task(task_id)
                elif action == "complete":
                    return await self._complete_task(task_id)
                elif action == "update":
                    return await self._update_task(task_id, status)
                elif action == "search":
                    return await self._search_tasks(query, limit)
                else:
                    return json.dumps({
                        "success": False,
                        "error": f"Unknown action: {action}. Use: add, list, start, complete, update, search"
                    }, ensure_ascii=False, indent=2)
                    
            except Exception as e:
                logger.error(f"Todo operation failed: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e)
                }, ensure_ascii=False, indent=2)
    
    async def _add_task(self, task: Optional[str]) -> str:
        """Add a new task."""
        if not task:
            return json.dumps({
                "success": False,
                "error": "Task content is required for add action"
            }, ensure_ascii=False, indent=2)
        
        # Get current project context
        project_id = self.config.get_current_project_id()
        project_path = self.config.get_current_project_path()
        
        todo = Todo(
            workspace_id="",
            project_id=project_id,
            project_path=project_path,
            content=task,
            active_form=f"Working on {task.lower()}",
            priority=TodoPriority.MEDIUM,
            status=TodoStatus.PENDING,
        )
        
        if self.task_storage.save(todo):
            self.search_engine.index_task(todo)
            logger.info(f"Created todo {todo.id}")
            
            return json.dumps({
                "success": True,
                "action": "task_added",
                "task": {
                    "id": todo.id,
                    "content": task,
                    "priority": todo.priority.value,
                    "status": todo.status.value,
                    "created_at": todo.created_at.strftime("%Y-%m-%d %H:%M")
                },
                "message": f"Added task: {task}"
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "success": False,
                "error": "Failed to add task"
            }, ensure_ascii=False, indent=2)
    
    async def _list_tasks(self, limit: int) -> str:
        """List active tasks."""
        active_todos = self.task_storage.get_active_tasks()[:limit]
        
        if not active_todos:
            return json.dumps({
                "success": True,
                "total_tasks": 0,
                "message": "No active tasks",
                "suggestion": "Use todo(action='add', task='your task') to create one!"
            }, ensure_ascii=False, indent=2)
        
        # Group by status
        in_progress = [t for t in active_todos if t.status == TodoStatus.IN_PROGRESS]
        pending = [t for t in active_todos if t.status == TodoStatus.PENDING]
        
        result = {
            "success": True,
            "total_tasks": len(active_todos),
            "tasks": {
                "in_progress": [
                    {
                        "id": todo.id,
                        "content": todo.content,
                        "active_form": todo.active_form,
                        "priority": todo.priority.value,
                        "created_at": todo.created_at.strftime("%Y-%m-%d %H:%M"),
                        "started_at": todo.started_at.strftime("%Y-%m-%d %H:%M") if todo.started_at else None
                    }
                    for todo in in_progress
                ],
                "pending": [
                    {
                        "id": todo.id,
                        "content": todo.content,
                        "priority": todo.priority.value,
                        "created_at": todo.created_at.strftime("%Y-%m-%d %H:%M")
                    }
                    for todo in pending
                ]
            },
            "counts": {
                "in_progress": len(in_progress),
                "pending": len(pending)
            },
            "suggestion": "Use todo(action='start', task_id='ID') or todo(action='complete', task_id='ID')"
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    async def _start_task(self, task_id: Optional[str]) -> str:
        """Start working on a task."""
        if not task_id:
            return json.dumps({
                "success": False,
                "error": "Task ID is required for start action"
            }, ensure_ascii=False, indent=2)
        
        todo = self.task_storage.load(task_id)
        if not todo:
            return json.dumps({
                "success": False,
                "error": f"Task {task_id} not found"
            }, ensure_ascii=False, indent=2)
        
        if todo.status == TodoStatus.IN_PROGRESS:
            return json.dumps({
                "success": True,
                "action": "task_already_started",
                "task": {
                    "id": todo.id,
                    "content": todo.content,
                    "active_form": todo.active_form,
                    "status": todo.status.value
                },
                "message": f"Already working on: {todo.get_display_form()}"
            }, ensure_ascii=False, indent=2)
        
        todo.mark_in_progress()
        
        if self.task_storage.save(todo):
            self.search_engine.index_task(todo)
            
            return json.dumps({
                "success": True,
                "action": "task_started",
                "task": {
                    "id": todo.id,
                    "content": todo.content,
                    "active_form": todo.active_form,
                    "status": todo.status.value,
                    "started_at": todo.started_at.strftime("%Y-%m-%d %H:%M") if todo.started_at else None
                },
                "message": f"Started working on: {todo.get_display_form()}"
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "success": False,
                "error": "Failed to update task"
            }, ensure_ascii=False, indent=2)
    
    async def _complete_task(self, task_id: Optional[str]) -> str:
        """Mark a task as completed."""
        if not task_id:
            return json.dumps({
                "success": False,
                "error": "Task ID is required for complete action"
            }, ensure_ascii=False, indent=2)
        
        todo = self.task_storage.load(task_id)
        if not todo:
            return json.dumps({
                "success": False,
                "error": f"Task {task_id} not found"
            }, ensure_ascii=False, indent=2)
        
        if todo.status == TodoStatus.COMPLETED:
            return json.dumps({
                "success": True,
                "action": "task_already_completed",
                "task": {
                    "id": todo.id,
                    "content": todo.content,
                    "status": todo.status.value
                },
                "message": f"Task already completed: {todo.content}"
            }, ensure_ascii=False, indent=2)
        
        todo.mark_completed()
        
        if self.task_storage.save(todo):
            self.search_engine.index_task(todo)
            
            return json.dumps({
                "success": True,
                "action": "task_completed",
                "task": {
                    "id": todo.id,
                    "content": todo.content,
                    "status": todo.status.value,
                    "completed_at": todo.completed_at.strftime("%Y-%m-%d %H:%M") if todo.completed_at else None
                },
                "message": f"Completed: {todo.content}",
                "celebration": "Great job! The task is now done."
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "success": False,
                "error": "Failed to update task"
            }, ensure_ascii=False, indent=2)
    
    async def _update_task(self, task_id: Optional[str], status: Optional[str]) -> str:
        """Update a task's status."""
        if not task_id:
            return json.dumps({
                "success": False,
                "error": "Task ID is required for update action"
            }, ensure_ascii=False, indent=2)
        
        if not status:
            return json.dumps({
                "success": False,
                "error": "Status is required for update action"
            }, ensure_ascii=False, indent=2)
        
        # Validate status
        from ..models.todo import TodoStatus
        try:
            new_status = TodoStatus(status.lower())
        except ValueError:
            return json.dumps({
                "success": False,
                "error": f"Invalid status: {status}. Valid values: pending, in_progress, completed"
            }, ensure_ascii=False, indent=2)
        
        todo = self.task_storage.load(task_id)
        if not todo:
            return json.dumps({
                "success": False,
                "error": f"Task {task_id} not found"
            }, ensure_ascii=False, indent=2)
        
        old_status = todo.status
        
        # Update the status using the appropriate method
        if new_status == TodoStatus.IN_PROGRESS:
            todo.mark_in_progress()
        elif new_status == TodoStatus.COMPLETED:
            todo.mark_completed()
        elif new_status == TodoStatus.PENDING:
            # Reset to pending
            todo.status = TodoStatus.PENDING
            todo.started_at = None
            todo.completed_at = None
            todo.updated_at = datetime.now(timezone.utc)
        
        if self.task_storage.save(todo):
            self.search_engine.index_task(todo)
            
            return json.dumps({
                "success": True,
                "action": "task_updated",
                "task": {
                    "id": todo.id,
                    "content": todo.content,
                    "old_status": old_status.value,
                    "new_status": todo.status.value,
                    "updated_at": todo.updated_at.strftime("%Y-%m-%d %H:%M") if todo.updated_at else None
                },
                "message": f"Updated task status from {old_status.value} to {todo.status.value}"
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "success": False,
                "error": "Failed to update task"
            }, ensure_ascii=False, indent=2)
    
    async def _search_tasks(self, query: Optional[str], limit: int) -> str:
        """Search tasks by content."""
        if not query:
            return json.dumps({
                "success": False,
                "error": "Search query is required for search action"
            }, ensure_ascii=False, indent=2)
        
        results = self.search_engine.search(
            query=query,
            limit=limit,
            doc_types=["todo"]
        )
        
        if not results:
            return json.dumps({
                "success": True,
                "query": query,
                "total_results": 0,
                "todos": [],
                "message": f"No todos found for query: '{query}'"
            }, ensure_ascii=False, indent=2)
        
        todos = []
        for search_result in results:
            todo = self.task_storage.load(search_result.doc_id)
            if todo:
                todos.append({
                    "id": todo.id,
                    "content": todo.content,
                    "status": todo.status.value,
                    "priority": todo.priority.value,
                    "created_at": todo.created_at.strftime("%Y-%m-%d %H:%M"),
                    "score": search_result.score
                })
        
        return json.dumps({
            "success": True,
            "query": query,
            "total_results": len(todos),
            "todos": todos
        }, ensure_ascii=False, indent=2)


class UnifiedCheckpointTool(BaseTool):
    """Unified checkpoint tool."""
    
    def register(self, mcp_server) -> None:
        """Register the unified checkpoint tool."""
        
        @mcp_server.tool
        async def checkpoint(
            action: str,
            description: Optional[str] = None,
            limit: int = 5,
            query: Optional[str] = None
        ) -> str:
            """Save and retrieve work progress checkpoints.
            
            Args:
                action: What to do - "save", "list", "search"
                description: Progress description (for save action)
                limit: Max results (for list/search actions)
                query: Search query (for search action)
            
            Examples:
                checkpoint(action="save", description="Fixed the login bug")
                checkpoint(action="list")
                checkpoint(action="search", query="bug fix", limit=3)
            """
            try:
                if action == "save":
                    return await self._save_checkpoint(description)
                elif action == "list":
                    return await self._list_checkpoints(limit)
                elif action == "search":
                    return await self._search_checkpoints(query, limit)
                else:
                    return json.dumps({
                        "success": False,
                        "error": f"Unknown action: {action}. Use: save, list, search"
                    }, ensure_ascii=False, indent=2)
                    
            except Exception as e:
                logger.error(f"Checkpoint operation failed: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e)
                }, ensure_ascii=False, indent=2)
    
    async def _save_checkpoint(self, description: Optional[str]) -> str:
        """Save a progress checkpoint."""
        if not description:
            return json.dumps({
                "success": False,
                "error": "Description is required for save action"
            }, ensure_ascii=False, indent=2)
        
        # Get current project context
        project_id = self.config.get_current_project_id()
        project_path = self.config.get_current_project_path()
        
        checkpoint = Checkpoint(
            workspace_id="",
            project_id=project_id,
            project_path=project_path,
            description=description,
            session_id=f"session_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        )
        
        checkpoint.set_ttl(self.config.default_checkpoint_ttl)
        
        if self.checkpoint_storage.save(checkpoint):
            self.search_engine.index_checkpoint(checkpoint)
            logger.info(f"Created checkpoint {checkpoint.id}")
            
            return json.dumps({
                "success": True,
                "action": "progress_saved",
                "checkpoint": {
                    "id": checkpoint.id,
                    "description": description,
                    "workspace_id": checkpoint.workspace_id,
                    "created_at": checkpoint.created_at.strftime("%Y-%m-%d %H:%M"),
                    "session_id": checkpoint.session_id
                },
                "message": f"Saved progress: {description}"
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "success": False,
                "error": "Failed to save progress"
            }, ensure_ascii=False, indent=2)
    
    async def _list_checkpoints(self, limit: int) -> str:
        """List recent checkpoints."""
        checkpoints = self.checkpoint_storage.list_recent(limit)
        
        if not checkpoints:
            return json.dumps({
                "success": True,
                "total_checkpoints": 0,
                "checkpoints": [],
                "message": "No saved progress found."
            }, ensure_ascii=False, indent=2)
        
        checkpoints_data = [
            {
                "id": checkpoint.id,
                "description": checkpoint.description,
                "created_at": checkpoint.created_at.strftime("%Y-%m-%d %H:%M"),
                "workspace_id": checkpoint.workspace_id,
                "session_id": getattr(checkpoint, 'session_id', ''),
                "highlights_count": len(getattr(checkpoint, 'highlights', []))
            }
            for checkpoint in checkpoints
        ]
        
        return json.dumps({
            "success": True,
            "total_checkpoints": len(checkpoints),
            "checkpoints": checkpoints_data
        }, ensure_ascii=False, indent=2)
    
    async def _search_checkpoints(self, query: Optional[str], limit: int) -> str:
        """Search checkpoints by content."""
        if not query:
            return json.dumps({
                "success": False,
                "error": "Search query is required for search action"
            }, ensure_ascii=False, indent=2)
        
        results = self.search_engine.search(
            query=query,
            limit=limit,
            doc_types=["checkpoint"]
        )
        
        if not results:
            return json.dumps({
                "success": True,
                "query": query,
                "total_results": 0,
                "checkpoints": [],
                "message": f"No checkpoints found for query: '{query}'"
            }, ensure_ascii=False, indent=2)
        
        checkpoints_data = []
        for search_result in results:
            checkpoint = self.checkpoint_storage.load(search_result.doc_id)
            if checkpoint:
                checkpoints_data.append({
                    "id": checkpoint.id,
                    "description": checkpoint.description,
                    "created_at": checkpoint.created_at.strftime("%Y-%m-%d %H:%M"),
                    "workspace_id": checkpoint.workspace_id,
                    "session_id": getattr(checkpoint, 'session_id', ''),
                    "score": search_result.score,
                    "highlights_count": len(getattr(checkpoint, 'highlights', []))
                })
        
        return json.dumps({
            "success": True,
            "query": query,
            "total_results": len(checkpoints_data),
            "checkpoints": checkpoints_data
        }, ensure_ascii=False, indent=2)


class UnifiedRecallTool(BaseTool):
    """Unified recall tool."""
    
    def register(self, mcp_server) -> None:
        """Register the unified recall tool."""
        
        @mcp_server.tool
        async def recall(
            context: str = "recent",
            days_back: int = 7,
            session_id: Optional[str] = None,
            git_branch: Optional[str] = None
        ) -> str:
            """Smart memory recall - gets the context you need automatically.
            
            Args:
                context: What to recall - "recent", "week", "all", or specific context
                days_back: How many days to look back
                session_id: Specific session to recall
                git_branch: Git branch to filter by
            
            Examples:
                recall()  # Recent context (default)
                recall(context="week", days_back=7)
                recall(context="session", session_id="session_123")
                recall(context="branch", git_branch="feature/new-auth")
            """
            try:
                if context == "recent":
                    return await self._recall_quick()
                elif context == "week":
                    return await self._recall_timeframe(days_back, True, True, True)
                elif context == "session" and session_id:
                    return await self._recall_session(session_id)
                elif context == "branch" and git_branch:
                    return await self._recall_branch(git_branch, days_back)
                else:
                    return json.dumps({
                        "success": False,
                        "error": "Invalid context or missing required parameters"
                    }, ensure_ascii=False, indent=2)
                    
            except Exception as e:
                logger.error(f"Recall operation failed: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e)
                }, ensure_ascii=False, indent=2)
    
    async def _recall_quick(self) -> str:
        """Quick recall of the most recent context (last 2 days)."""
        from datetime import timedelta
        
        context_data = await self._build_recall_context(
            days_back=2,
            include_todos=True,
            include_plans=True,
            include_checkpoints=True
        )
        return self._build_recall_response(context_data)
    
    async def _recall_timeframe(self, days_back: int, include_todos: bool, include_plans: bool, include_checkpoints: bool) -> str:
        """Recall context for a specific timeframe."""
        context_data = await self._build_recall_context(
            days_back=days_back,
            include_todos=include_todos,
            include_plans=include_plans,
            include_checkpoints=include_checkpoints
        )
        return self._build_recall_response(context_data)
    
    async def _recall_session(self, session_id: str) -> str:
        """Recall context from a specific session."""
        context_data = await self._build_recall_context(
            days_back=30,  # Broader search for session-specific recall
            include_todos=True,
            include_plans=True,
            include_checkpoints=True,
            session_id=session_id
        )
        return self._build_recall_response(context_data)
    
    async def _recall_branch(self, git_branch: str, days_back: int) -> str:
        """Recall context for work on a specific git branch."""
        context_data = await self._build_recall_context(
            days_back=days_back,
            include_todos=True,
            include_plans=True,
            include_checkpoints=True,
            git_branch=git_branch
        )
        return self._build_recall_response(context_data)
    
    async def _build_recall_context(
        self,
        days_back: int,
        include_todos: bool,
        include_plans: bool,
        include_checkpoints: bool,
        session_id: Optional[str] = None,
        git_branch: Optional[str] = None,
    ) -> dict:
        """Build the context information for recall."""
        from datetime import timedelta
        
        context = {
            "project_id": self.config.get_current_project_id(),
            "project_path": self.config.get_current_project_path(),
            "recall_time": datetime.now(timezone.utc),
            "filter_applied": bool(session_id or git_branch),
            "checkpoints": [],
            "todos": [],
            "plans": [],
            "summary": {},
        }
        
        # Calculate time range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_back)
        
        # Get checkpoints
        if include_checkpoints:
            if session_id:
                context["checkpoints"] = self.checkpoint_storage.find_by_session(session_id)
            elif git_branch:
                context["checkpoints"] = self.checkpoint_storage.find_by_git_branch(git_branch)
            else:
                context["checkpoints"] = self.checkpoint_storage.list_by_date_range(start_date, end_date)
        
        # Get todos
        if include_todos:
            all_todos = self.task_storage.get_active_tasks()
            
            # Filter todos by timeframe or specific criteria
            if session_id or git_branch:
                # For specific filters, get all active todos
                context["todos"] = all_todos
            else:
                # For time-based, filter by creation/update time
                filtered_todos = []
                for todo in all_todos:
                    if (todo.created_at >= start_date or 
                        (todo.updated_at and todo.updated_at >= start_date)):
                        filtered_todos.append(todo)
                context["todos"] = filtered_todos
        
        # Get plans
        if include_plans:
            active_plans = self.plan_storage.find_active()
            
            # Filter similar to todos
            if session_id or git_branch:
                context["plans"] = active_plans
            else:
                filtered_plans = []
                for plan in active_plans:
                    if (plan.created_at >= start_date or 
                        (plan.updated_at and plan.updated_at >= start_date)):
                        filtered_plans.append(plan)
                context["plans"] = filtered_plans
        
        # Build summary stats
        from ..models.todo import TodoStatus
        context["summary"] = {
            "checkpoints_count": len(context["checkpoints"]),
            "todos_count": len(context["todos"]),
            "active_todos": len([t for t in context["todos"] if t.status == TodoStatus.IN_PROGRESS]),
            "pending_todos": len([t for t in context["todos"] if t.status == TodoStatus.PENDING]),
            "plans_count": len(context["plans"]),
            "days_covered": days_back,
            "session_filter": session_id,
            "branch_filter": git_branch,
        }
        
        return context
    
    def _build_recall_response(self, context: dict) -> str:
        """Build JSON response for recall context."""
        from ..models.todo import TodoStatus
        return json.dumps({
            "success": True,
            "project_id": context["project_id"],
            "project_path": context["project_path"],
            "recall_time": context["recall_time"].strftime("%Y-%m-%d %H:%M"),
            "filter_applied": context["filter_applied"],
            "summary": context["summary"],
            "checkpoints": [
                {
                    "id": cp.id,
                    "description": cp.description,
                    "created_at": cp.created_at.strftime("%Y-%m-%d %H:%M"),
                    "session_id": getattr(cp, 'session_id', ''),
                    "highlights_count": len(getattr(cp, 'highlights', []))
                }
                for cp in sorted(context["checkpoints"], key=lambda c: c.created_at, reverse=True)[:5]
            ],
            "todos": {
                "in_progress": [
                    {
                        "id": todo.id,
                        "content": todo.content,
                        "active_form": todo.active_form,
                        "created_at": todo.created_at.strftime("%Y-%m-%d %H:%M")
                    }
                    for todo in context["todos"] if todo.status == TodoStatus.IN_PROGRESS
                ],
                "pending": [
                    {
                        "id": todo.id,
                        "content": todo.content,
                        "created_at": todo.created_at.strftime("%Y-%m-%d %H:%M")
                    }
                    for todo in context["todos"] if todo.status == TodoStatus.PENDING
                ]
            },
            "plans": [
                {
                    "id": plan.id,
                    "title": plan.title,
                    "description": plan.description[:100] + "..." if len(plan.description) > 100 else plan.description,
                    "status": plan.status.value,
                    "progress": f"{plan.get_progress()[0]}/{plan.get_progress()[1]}"
                }
                for plan in context["plans"][:3]
            ]
        }, ensure_ascii=False, indent=2)


class UnifiedStandupTool(BaseTool):
    """Unified standup tool."""
    
    def register(self, mcp_server) -> None:
        """Register the unified standup tool."""
        
        @mcp_server.tool
        async def standup(
            timeframe: str = "daily",
            include_completed: bool = True,
            days_back: int = 1
        ) -> str:
            """Generate a quick standup report of your recent work.
            
            Args:
                timeframe: Report timeframe - "daily", "weekly", "custom"
                include_completed: Include completed tasks
                days_back: How many days to include (for custom timeframe)
            
            Examples:
                standup()  # Daily standup
                standup(timeframe="weekly")
                standup(timeframe="custom", days_back=3)
            """
            try:
                # Parse timeframe to days_back if needed
                if timeframe == "daily":
                    days_back = 1
                elif timeframe == "weekly":
                    days_back = 7
                elif timeframe == "custom":
                    # Use provided days_back
                    pass
                else:
                    days_back = 1
                
                # Build report data
                report_data = await self._build_standup_data(
                    days_back=days_back,
                    include_completed=include_completed,
                )
                
                return self._build_standup_response(report_data, timeframe)
                    
            except Exception as e:
                logger.error(f"Standup operation failed: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e)
                }, ensure_ascii=False, indent=2)
    
    async def _build_standup_data(
        self,
        days_back: int,
        include_completed: bool,
        project_ids: Optional[List[str]] = None,
    ) -> dict:
        """Build standup report data using cross-project search."""
        # Use search engine for cross-project aggregation
        search_results = self.search_engine.search_cross_project(
            query="*",  # Get everything
            days_back=days_back,
            project_ids=project_ids,  # None = all projects
            limit=200  # Get more results for standup
        )
        
        # Group results by type and project
        checkpoints_by_project = {}
        todos_by_project = {}
        plans_by_project = {}
        
        # Get actual objects from search results
        for result in search_results:
            project_id = "unknown"  # Default fallback
            
            try:
                if result.doc_type == "checkpoint":
                    checkpoint = self.checkpoint_storage.load(result.doc_id)
                    if checkpoint:
                        project_id = checkpoint.project_id or "unknown"
                        if project_id not in checkpoints_by_project:
                            checkpoints_by_project[project_id] = []
                        checkpoints_by_project[project_id].append(checkpoint)
                
                elif result.doc_type == "todo":
                    todo = self.task_storage.load(result.doc_id)
                    if todo:
                        project_id = todo.project_id or "unknown"
                        if project_id not in todos_by_project:
                            todos_by_project[project_id] = []
                        todos_by_project[project_id].append(todo)
                
                elif result.doc_type == "plan":
                    plan = self.plan_storage.load(result.doc_id)
                    if plan:
                        project_id = plan.project_id or "unknown"
                        if project_id not in plans_by_project:
                            plans_by_project[project_id] = []
                        plans_by_project[project_id].append(plan)
            
            except Exception as e:
                logger.warning(f"Failed to load {result.doc_type} {result.doc_id}: {e}")
                continue
        
        # Filter completed todos if requested
        completed_todos_by_project = {}
        if include_completed:
            for project_id, todos in todos_by_project.items():
                completed = [t for t in todos if t.status.value == "completed"]
                if completed:
                    completed_todos_by_project[project_id] = completed
        
        # Get project registry for friendly names
        registry = self.config.load_projects_registry()
        project_names = {path: project_id for path, project_id in registry.items()}
        
        return {
            "timeframe": days_back,
            "checkpoints_by_project": checkpoints_by_project,
            "todos_by_project": todos_by_project,
            "completed_todos_by_project": completed_todos_by_project,
            "plans_by_project": plans_by_project,
            "project_registry": registry,
            "total_projects": len(set(list(checkpoints_by_project.keys()) + 
                                   list(todos_by_project.keys()) + 
                                   list(plans_by_project.keys()))),
        }
    
    def _build_standup_response(self, data: dict, timeframe: str) -> str:
        """Build JSON response for cross-project standup report."""
        from ..models.todo import TodoStatus
        
        # Calculate totals across all projects
        total_checkpoints = sum(len(cps) for cps in data["checkpoints_by_project"].values())
        total_todos = sum(len(todos) for todos in data["todos_by_project"].values())
        total_completed = sum(len(todos) for todos in data["completed_todos_by_project"].values())
        total_plans = sum(len(plans) for plans in data["plans_by_project"].values())
        
        # Build project-specific data
        projects_data = {}
        for project_id in set(list(data["checkpoints_by_project"].keys()) + 
                             list(data["todos_by_project"].keys()) + 
                             list(data["plans_by_project"].keys())):
            
            project_checkpoints = data["checkpoints_by_project"].get(project_id, [])
            project_todos = data["todos_by_project"].get(project_id, [])
            project_completed = data["completed_todos_by_project"].get(project_id, [])
            project_plans = data["plans_by_project"].get(project_id, [])
            
            # Categorize todos for this project
            in_progress = [t for t in project_todos if t.status == TodoStatus.IN_PROGRESS]
            pending = [t for t in project_todos if t.status == TodoStatus.PENDING]
            
            projects_data[project_id] = {
                "summary": {
                    "checkpoints": len(project_checkpoints),
                    "todos_in_progress": len(in_progress),
                    "todos_pending": len(pending),
                    "todos_completed": len(project_completed),
                    "plans_active": len(project_plans)
                },
                "recent_activity": {
                    "checkpoints": [
                        {
                            "id": cp.id,
                            "description": cp.description,
                            "created_at": cp.created_at.strftime("%Y-%m-%d %H:%M"),
                            "project_path": cp.project_path[:50] + "..." if len(cp.project_path) > 50 else cp.project_path
                        }
                        for cp in sorted(project_checkpoints, key=lambda c: c.created_at, reverse=True)[:5]
                    ],
                    "todos_in_progress": [
                        {
                            "id": todo.id,
                            "content": todo.content,
                            "active_form": todo.active_form,
                            "started_at": todo.started_at.strftime("%Y-%m-%d %H:%M") if todo.started_at else None
                        }
                        for todo in in_progress[:5]
                    ],
                    "todos_completed": [
                        {
                            "id": todo.id,
                            "content": todo.content,
                            "completed_at": todo.completed_at.strftime("%Y-%m-%d %H:%M") if todo.completed_at else None
                        }
                        for todo in project_completed[:5]
                    ]
                }
            }
        
        return json.dumps({
            "success": True,
            "timeframe": timeframe,
            "days_covered": data["timeframe"],
            "cross_project_summary": {
                "total_projects": data["total_projects"],
                "total_checkpoints": total_checkpoints,
                "total_todos": total_todos,
                "total_completed": total_completed,
                "total_plans": total_plans
            },
            "projects": projects_data
        }, ensure_ascii=False, indent=2)


class UnifiedPlanTool(BaseTool):
    """Unified plan tool - the starting point for complex multi-step work."""
    
    def register(self, mcp_server) -> None:
        """Register the unified plan tool."""
        
        @mcp_server.tool
        async def plan(
            action: str,
            title: Optional[str] = None,
            description: Optional[str] = None,
            plan_id: Optional[str] = None,
            step_description: Optional[str] = None,
            step_id: Optional[str] = None,
            query: Optional[str] = None,
            limit: int = 10
        ) -> str:
            """Plan complex work with structured multi-step approach.
            
            BEHAVIORAL GUIDANCE: Use this FIRST for any complex task. Planning helps
            break down work, get user alignment, and track multi-session progress.
            
            Args:
                action: What to do - "create", "list", "activate", "complete", "add_step", "complete_step", "search"
                title: Plan title (for create action)
                description: Plan description (for create action)
                plan_id: Plan ID (for activate/complete/add_step actions)
                step_description: Step description (for add_step action)
                step_id: Step ID (for complete_step action)
                query: Search query (for search action)
                limit: Max results (for list/search actions)
            
            Examples:
                plan(action="create", title="Implement user auth", description="Add complete authentication system")
                plan(action="list")
                plan(action="activate", plan_id="abc123")
                plan(action="add_step", plan_id="abc123", step_description="Create login form")
                plan(action="complete_step", step_id="step456")
                plan(action="search", query="authentication", limit=5)
            """
            try:
                if action == "create":
                    return await self._create_plan(title, description)
                elif action == "list":
                    return await self._list_plans(limit)
                elif action == "activate":
                    return await self._activate_plan(plan_id)
                elif action == "complete":
                    return await self._complete_plan(plan_id)
                elif action == "add_step":
                    return await self._add_step(plan_id, step_description)
                elif action == "complete_step":
                    return await self._complete_step(step_id)
                elif action == "search":
                    return await self._search_plans(query, limit)
                else:
                    return json.dumps({
                        "success": False,
                        "error": f"Unknown action: {action}. Use: create, list, activate, complete, add_step, complete_step, search"
                    }, ensure_ascii=False, indent=2)
                    
            except Exception as e:
                logger.error(f"Plan operation failed: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e)
                }, ensure_ascii=False, indent=2)
    
    async def _create_plan(self, title: Optional[str], description: Optional[str]) -> str:
        """Create a new plan."""
        if not title:
            return json.dumps({
                "success": False,
                "error": "Plan title is required for create action"
            }, ensure_ascii=False, indent=2)
        
        if not description:
            return json.dumps({
                "success": False,
                "error": "Plan description is required for create action"
            }, ensure_ascii=False, indent=2)
        
        # Get current project context
        project_id = self.config.get_current_project_id()
        project_path = self.config.get_current_project_path()
        
        plan = Plan(
            workspace_id="",
            project_id=project_id,
            project_path=project_path,
            title=title,
            description=description,
            status=PlanStatus.DRAFT,
        )
        
        if self.plan_storage.save(plan):
            self.search_engine.index_plan(plan)
            logger.info(f"Created plan {plan.id}")
            
            return json.dumps({
                "success": True,
                "action": "plan_created",
                "plan": {
                    "id": plan.id,
                    "title": title,
                    "description": description,
                    "status": plan.status.value,
                    "priority": plan.priority,
                    "created_at": plan.created_at.strftime("%Y-%m-%d %H:%M"),
                    "steps_count": len(plan.steps),
                    "workspace_id": plan.workspace_id
                },
                "message": f"Created plan: {title}",
                "next_steps": "Use plan(action='add_step') to add steps, then plan(action='activate') to start working"
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "success": False,
                "error": "Failed to create plan"
            }, ensure_ascii=False, indent=2)
    
    async def _list_plans(self, limit: int) -> str:
        """List active plans."""
        active_plans = self.plan_storage.find_active()
        
        if not active_plans:
            return json.dumps({
                "success": True,
                "total_plans": 0,
                "plans": [],
                "message": "No active plans found.",
                "suggestion": "Use plan(action='create', title='...', description='...') to create one!"
            }, ensure_ascii=False, indent=2)
        
        # Limit results
        limited_plans = active_plans[:limit]
        
        plans_data = []
        for plan in limited_plans:
            completed_steps = len([s for s in plan.steps if s.completed])
            total_steps = len(plan.steps)
            
            plans_data.append({
                "id": plan.id,
                "title": plan.title,
                "description": plan.description[:100] + "..." if len(plan.description) > 100 else plan.description,
                "status": plan.status.value,
                "priority": plan.priority,
                "progress": f"{completed_steps}/{total_steps}",
                "created_at": plan.created_at.strftime("%Y-%m-%d %H:%M"),
                "updated_at": plan.updated_at.strftime("%Y-%m-%d %H:%M") if plan.updated_at else None
            })
        
        return json.dumps({
            "success": True,
            "total_plans": len(active_plans),
            "showing": len(limited_plans),
            "plans": plans_data,
            "suggestion": "Use plan(action='activate', plan_id='ID') to focus on a specific plan"
        }, ensure_ascii=False, indent=2)
    
    async def _activate_plan(self, plan_id: Optional[str]) -> str:
        """Activate a plan to focus on it."""
        if not plan_id:
            return json.dumps({
                "success": False,
                "error": "Plan ID is required for activate action"
            }, ensure_ascii=False, indent=2)
        
        plan = self.plan_storage.load(plan_id)
        if not plan:
            return json.dumps({
                "success": False,
                "error": f"Plan {plan_id} not found"
            }, ensure_ascii=False, indent=2)
        
        if plan.status != PlanStatus.DRAFT:
            return json.dumps({
                "success": True,
                "action": "plan_already_active",
                "plan": {
                    "id": plan.id,
                    "title": plan.title,
                    "status": plan.status.value
                },
                "message": f"Plan '{plan.title}' is already {plan.status.value}"
            }, ensure_ascii=False, indent=2)
        
        plan.status = PlanStatus.ACTIVE
        plan.updated_at = datetime.now(timezone.utc)
        
        if self.plan_storage.save(plan):
            self.search_engine.index_plan(plan)
            
            completed_steps = len([s for s in plan.steps if s.completed])
            total_steps = len(plan.steps)
            
            return json.dumps({
                "success": True,
                "action": "plan_activated",
                "plan": {
                    "id": plan.id,
                    "title": plan.title,
                    "description": plan.description,
                    "status": plan.status.value,
                    "progress": f"{completed_steps}/{total_steps}",
                    "steps": [
                        {
                            "id": step.id,
                            "description": step.description,
                            "completed": step.completed,
                            "notes": step.notes
                        }
                        for step in plan.steps
                    ]
                },
                "message": f"Activated plan: {plan.title}",
                "next_steps": "Start working on the plan steps. Use todo(action='add') to create specific tasks for each step."
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "success": False,
                "error": "Failed to activate plan"
            }, ensure_ascii=False, indent=2)
    
    async def _complete_plan(self, plan_id: Optional[str]) -> str:
        """Mark a plan as completed."""
        if not plan_id:
            return json.dumps({
                "success": False,
                "error": "Plan ID is required for complete action"
            }, ensure_ascii=False, indent=2)
        
        plan = self.plan_storage.load(plan_id)
        if not plan:
            return json.dumps({
                "success": False,
                "error": f"Plan {plan_id} not found"
            }, ensure_ascii=False, indent=2)
        
        if plan.status == PlanStatus.COMPLETED:
            return json.dumps({
                "success": True,
                "action": "plan_already_completed",
                "plan": {
                    "id": plan.id,
                    "title": plan.title,
                    "status": plan.status.value
                },
                "message": f"Plan '{plan.title}' is already completed"
            }, ensure_ascii=False, indent=2)
        
        plan.status = PlanStatus.COMPLETED
        plan.updated_at = datetime.now(timezone.utc)
        
        # Mark all steps as completed
        for step in plan.steps:
            if not step.completed:
                step.completed = True
                step.completed_at = datetime.now(timezone.utc)
        
        if self.plan_storage.save(plan):
            self.search_engine.index_plan(plan)
            
            return json.dumps({
                "success": True,
                "action": "plan_completed",
                "plan": {
                    "id": plan.id,
                    "title": plan.title,
                    "status": plan.status.value,
                    "completed_steps": len(plan.steps),
                    "completed_at": plan.updated_at.strftime("%Y-%m-%d %H:%M")
                },
                "message": f"Completed plan: {plan.title}",
                "celebration": "🎉 Great job finishing this plan!"
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "success": False,
                "error": "Failed to complete plan"
            }, ensure_ascii=False, indent=2)
    
    async def _add_step(self, plan_id: Optional[str], step_description: Optional[str]) -> str:
        """Add a step to a plan."""
        if not plan_id:
            return json.dumps({
                "success": False,
                "error": "Plan ID is required for add_step action"
            }, ensure_ascii=False, indent=2)
        
        if not step_description:
            return json.dumps({
                "success": False,
                "error": "Step description is required for add_step action"
            }, ensure_ascii=False, indent=2)
        
        plan = self.plan_storage.load(plan_id)
        if not plan:
            return json.dumps({
                "success": False,
                "error": f"Plan {plan_id} not found"
            }, ensure_ascii=False, indent=2)
        
        # Create new step
        new_step = PlanStep(
            description=step_description,
            completed=False
        )
        
        plan.steps.append(new_step)
        plan.updated_at = datetime.now(timezone.utc)
        
        if self.plan_storage.save(plan):
            self.search_engine.index_plan(plan)
            
            return json.dumps({
                "success": True,
                "action": "step_added",
                "plan": {
                    "id": plan.id,
                    "title": plan.title,
                    "total_steps": len(plan.steps)
                },
                "step": {
                    "id": new_step.id,
                    "description": step_description,
                    "completed": False
                },
                "message": f"Added step to plan '{plan.title}': {step_description}"
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "success": False,
                "error": "Failed to add step to plan"
            }, ensure_ascii=False, indent=2)
    
    async def _complete_step(self, step_id: Optional[str]) -> str:
        """Mark a plan step as completed."""
        if not step_id:
            return json.dumps({
                "success": False,
                "error": "Step ID is required for complete_step action"
            }, ensure_ascii=False, indent=2)
        
        # Find the plan containing this step
        all_plans = self.plan_storage.load_all()
        target_plan = None
        target_step = None
        
        for plan in all_plans:
            for step in plan.steps:
                if step.id == step_id:
                    target_plan = plan
                    target_step = step
                    break
            if target_plan:
                break
        
        if not target_plan or not target_step:
            return json.dumps({
                "success": False,
                "error": f"Step {step_id} not found"
            }, ensure_ascii=False, indent=2)
        
        if target_step.completed:
            return json.dumps({
                "success": True,
                "action": "step_already_completed",
                "step": {
                    "id": step_id,
                    "description": target_step.description,
                    "completed": True
                },
                "message": f"Step already completed: {target_step.description}"
            }, ensure_ascii=False, indent=2)
        
        target_step.completed = True
        target_step.completed_at = datetime.now(timezone.utc)
        target_plan.updated_at = datetime.now(timezone.utc)
        
        if self.plan_storage.save(target_plan):
            self.search_engine.index_plan(target_plan)
            
            completed_steps = len([s for s in target_plan.steps if s.completed])
            total_steps = len(target_plan.steps)
            
            return json.dumps({
                "success": True,
                "action": "step_completed",
                "plan": {
                    "id": target_plan.id,
                    "title": target_plan.title,
                    "progress": f"{completed_steps}/{total_steps}"
                },
                "step": {
                    "id": step_id,
                    "description": target_step.description,
                    "completed_at": target_step.completed_at.strftime("%Y-%m-%d %H:%M")
                },
                "message": f"Completed step: {target_step.description}",
                "plan_status": "Plan completed!" if completed_steps == total_steps else f"Progress: {completed_steps}/{total_steps} steps done"
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "success": False,
                "error": "Failed to complete step"
            }, ensure_ascii=False, indent=2)
    
    async def _search_plans(self, query: Optional[str], limit: int) -> str:
        """Search plans by content."""
        if not query:
            return json.dumps({
                "success": False,
                "error": "Search query is required for search action"
            }, ensure_ascii=False, indent=2)
        
        results = self.search_engine.search(
            query=query,
            limit=limit,
            doc_types=["plan"]
        )
        
        if not results:
            return json.dumps({
                "success": True,
                "query": query,
                "total_results": 0,
                "plans": [],
                "message": f"No plans found for query: '{query}'"
            }, ensure_ascii=False, indent=2)
        
        plans_data = []
        for search_result in results:
            plan = self.plan_storage.load(search_result.doc_id)
            if plan:
                completed_steps = len([s for s in plan.steps if s.completed])
                total_steps = len(plan.steps)
                
                plans_data.append({
                    "id": plan.id,
                    "title": plan.title,
                    "description": plan.description[:100] + "..." if len(plan.description) > 100 else plan.description,
                    "status": plan.status.value,
                    "priority": plan.priority,
                    "progress": f"{completed_steps}/{total_steps}",
                    "created_at": plan.created_at.strftime("%Y-%m-%d %H:%M"),
                    "score": search_result.score
                })
        
        return json.dumps({
            "success": True,
            "query": query,
            "total_results": len(plans_data),
            "plans": plans_data
        }, ensure_ascii=False, indent=2)


class UnifiedCleanupTool(BaseTool):
    """Unified system cleanup tool."""
    
    def register(self, mcp_server) -> None:
        """Register the unified cleanup tool."""
        
        @mcp_server.tool
        async def cleanup(
            target: str = "locks",
            force: bool = False
        ) -> str:
            """Clean up Tusk system resources.
            
            Args:
                target: What to clean up - "locks" (search index locks)
                force: If True, force cleanup regardless of file age
            
            Examples:
                cleanup(target="locks")  # Clean stale lock files
                cleanup(target="locks", force=True)  # Force remove all locks
            """
            try:
                if target == "locks":
                    removed = self.search_engine.cleanup_locks(force=force)
                    if removed:
                        return json.dumps({
                            "success": True,
                            "message": "Successfully cleaned up stale lock files",
                            "force_used": force
                        }, ensure_ascii=False, indent=2)
                    else:
                        return json.dumps({
                            "success": True,
                            "message": "No stale lock files found to clean up",
                            "force_used": force
                        }, ensure_ascii=False, indent=2)
                else:
                    return json.dumps({
                        "success": False,
                        "error": f"Unknown cleanup target: {target}. Supported: 'locks'"
                    }, ensure_ascii=False, indent=2)
                    
            except Exception as e:
                logger.error(f"Cleanup operation failed: {e}")
                return json.dumps({
                    "success": False,
                    "error": f"Cleanup failed: {str(e)}"
                }, ensure_ascii=False, indent=2)