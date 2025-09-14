"""Unified tools for Tusk - single tools with action parameters like Goldfish."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from ..models.types import utc_now

from ..models.checkpoint import Checkpoint
from ..models.plan import Plan, PlanStatus, PlanStep
from ..models.task import Task, TaskPriority, TaskStatus
from .base import BaseTool

logger = logging.getLogger(__name__)


class UnifiedTaskTool(BaseTool):
    """Unified task tool - handles all task operations via action parameter."""

    def register(self, mcp_server) -> None:
        """Register the unified task tool."""

        @mcp_server.tool
        async def task(
            action: str,
            task: str | None = None,
            task_id: str | None = None,
            status: str | None = None,
            query: str | None = None,
            limit: int = 10,
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
                task(action="add", task="Fix the bug in login system")
                task(action="list")
                task(action="start", task_id="abc123")
                task(action="complete", task_id="abc123")
                task(action="update", task_id="abc123", status="in_progress")
                task(action="search", query="bug", limit=5)
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
                    return json.dumps(
                        {
                            "success": False,
                            "error": f"Unknown action: {action}. Use: add, list, start, complete, update, search",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )

            except Exception as e:
                logger.error(f"Task operation failed: {e}")
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False, indent=2)

    async def _add_task(self, task: str | None) -> str:
        """Add a new task."""
        if not task:
            return json.dumps(
                {"success": False, "error": "Task content is required for add action"},
                ensure_ascii=False,
                indent=2,
            )

        # Get current project context
        project_id = self.config.get_current_project_id()
        project_path = self.config.get_current_project_path()

        task_obj = Task(
            workspace_id="",
            project_id=project_id,
            project_path=project_path,
            content=task,
            active_form=f"Working on {task.lower()}",
            priority=TaskPriority.MEDIUM,
            status=TaskStatus.PENDING,
        )

        if self.task_storage.save(task_obj):
            self.search_engine.index_task(task_obj)
            logger.info(f"Created task {task_obj.id}")

            return json.dumps(
                {
                    "success": True,
                    "action": "task_added",
                    "task": {
                        "id": task_obj.id,
                        "content": task_obj.content,
                        "priority": task_obj.priority.value,
                        "status": task_obj.status.value,
                        "created_at": task_obj.created_at.strftime("%Y-%m-%d %H:%M"),
                    },
                    "message": f"Added task: {task_obj.content}",
                },
                ensure_ascii=False,
                indent=2,
            )
        else:
            return json.dumps({"success": False, "error": "Failed to add task"}, ensure_ascii=False, indent=2)
    async def _list_tasks(self, limit: int) -> str:
        """List active tasks."""
        active_tasks = self.task_storage.get_active_tasks()[:limit]

        if not active_tasks:
            return json.dumps(
                {
                    "success": True,
                    "total_tasks": 0,
                    "message": "No active tasks",
                    "suggestion": "Use task(action='add', task='your task') to create one!",
                },
                ensure_ascii=False,
                indent=2,
            )

        # Group by status
        in_progress = [t for t in active_tasks if t.status == TaskStatus.IN_PROGRESS]
        pending = [t for t in active_tasks if t.status == TaskStatus.PENDING]

        result = {
            "success": True,
            "total_tasks": len(active_tasks),
            "tasks": {
                "in_progress": [
                    {
                        "id": task.id,
                        "content": task.content,
                        "active_form": task.active_form,
                        "priority": task.priority.value,
                        "created_at": task.created_at.strftime("%Y-%m-%d %H:%M"),
                        "started_at": (task.started_at.strftime("%Y-%m-%d %H:%M") if task.started_at else None),
                    }
                    for task in in_progress
                ],
                "pending": [
                    {
                        "id": task.id,
                        "content": task.content,
                        "priority": task.priority.value,
                        "created_at": task.created_at.strftime("%Y-%m-%d %H:%M"),
                    }
                    for task in pending
                ],
            },
            "counts": {"in_progress": len(in_progress), "pending": len(pending)},
            "suggestion": "Use task(action='start', task_id='ID') or task(action='complete', task_id='ID')",
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _start_task(self, task_id: str | None) -> str:
        """Start working on a task."""
        if not task_id:
            return json.dumps(
                {"success": False, "error": "Task ID is required for start action"},
                ensure_ascii=False,
                indent=2,
            )

        task = self.task_storage.load(task_id)
        if not task:
            return json.dumps(
                {"success": False, "error": f"Task {task_id} not found"},
                ensure_ascii=False,
                indent=2,
            )

        if task.status == TaskStatus.IN_PROGRESS:
            return json.dumps(
                {
                    "success": True,
                    "action": "task_already_started",
                    "task": {
                        "id": task.id,
                        "content": task.content,
                        "active_form": task.active_form,
                        "status": task.status.value,
                    },
                    "message": f"Already working on: {task.get_display_form()}",
                },
                ensure_ascii=False,
                indent=2,
            )

        task.mark_in_progress()

        if self.task_storage.save(task):
            self.search_engine.index_task(task)

            return json.dumps(
                {
                    "success": True,
                    "action": "task_started",
                    "task": {
                        "id": task.id,
                        "content": task.content,
                        "active_form": task.active_form,
                        "status": task.status.value,
                        "started_at": (task.started_at.strftime("%Y-%m-%d %H:%M") if task.started_at else None),
                    },
                    "message": f"Started working on: {task.get_display_form()}",
                },
                ensure_ascii=False,
                indent=2,
            )
        else:
            return json.dumps({"success": False, "error": "Failed to update task"}, ensure_ascii=False, indent=2)

    async def _complete_task(self, task_id: str | None) -> str:
        """Mark a task as completed."""
        if not task_id:
            return json.dumps(
                {"success": False, "error": "Task ID is required for complete action"},
                ensure_ascii=False,
                indent=2,
            )

        task = self.task_storage.load(task_id)
        if not task:
            return json.dumps(
                {"success": False, "error": f"Task {task_id} not found"},
                ensure_ascii=False,
                indent=2,
            )

        if task.status == TaskStatus.COMPLETED:
            return json.dumps(
                {
                    "success": True,
                    "action": "task_already_completed",
                    "task": {"id": task.id, "content": task.content, "status": task.status.value},
                    "message": f"Task already completed: {task.content}",
                },
                ensure_ascii=False,
                indent=2,
            )

        task.mark_completed()

        if self.task_storage.save(task):
            self.search_engine.index_task(task)

            return json.dumps(
                {
                    "success": True,
                    "action": "task_completed",
                    "task": {
                        "id": task.id,
                        "content": task.content,
                        "status": task.status.value,
                        "completed_at": (task.completed_at.strftime("%Y-%m-%d %H:%M") if task.completed_at else None),
                    },
                    "message": f"Completed: {task.content}",
                    "celebration": "Great job! The task is now done.",
                },
                ensure_ascii=False,
                indent=2,
            )
        else:
            return json.dumps({"success": False, "error": "Failed to update task"}, ensure_ascii=False, indent=2)

    async def _update_task(self, task_id: str | None, status: str | None) -> str:
        """Update a task's status."""
        if not task_id:
            return json.dumps(
                {"success": False, "error": "Task ID is required for update action"},
                ensure_ascii=False,
                indent=2,
            )

        if not status:
            return json.dumps(
                {"success": False, "error": "Status is required for update action"},
                ensure_ascii=False,
                indent=2,
            )

        # Validate status
        from ..models.task import TaskStatus

        try:
            new_status = TaskStatus(status.lower())
        except ValueError:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Invalid status: {status}. Valid values: pending, in_progress, completed",
                },
                ensure_ascii=False,
                indent=2,
            )

        task = self.task_storage.load(task_id)
        if not task:
            return json.dumps(
                {"success": False, "error": f"Task {task_id} not found"},
                ensure_ascii=False,
                indent=2,
            )

        old_status = task.status

        # Update the status using the appropriate method
        if new_status == TaskStatus.IN_PROGRESS:
            task.mark_in_progress()
        elif new_status == TaskStatus.COMPLETED:
            task.mark_completed()
        elif new_status == TaskStatus.PENDING:
            # Reset to pending
            task.status = TaskStatus.PENDING
            task.started_at = None
            task.completed_at = None
            task.updated_at = utc_now()

        if self.task_storage.save(task):
            self.search_engine.index_task(task)

            return json.dumps(
                {
                    "success": True,
                    "action": "task_updated",
                    "task": {
                        "id": task.id,
                        "content": task.content,
                        "old_status": old_status.value,
                        "new_status": task.status.value,
                        "updated_at": (task.updated_at.strftime("%Y-%m-%d %H:%M") if task.updated_at else None),
                    },
                    "message": f"Updated task status from {old_status.value} to {task.status.value}",
                },
                ensure_ascii=False,
                indent=2,
            )
        else:
            return json.dumps({"success": False, "error": "Failed to update task"}, ensure_ascii=False, indent=2)

    async def _search_tasks(self, query: str | None, limit: int) -> str:
        """Search tasks by content."""
        if not query:
            return json.dumps(
                {"success": False, "error": "Search query is required for search action"},
                ensure_ascii=False,
                indent=2,
            )

        results = self.search_engine.search(query=query, limit=limit, doc_types=["task"])

        if not results:
            return json.dumps(
                {
                    "success": True,
                    "query": query,
                    "total_results": 0,
                    "tasks": [],
                    "message": f"No tasks found for query: '{query}'",
                },
                ensure_ascii=False,
                indent=2,
            )

        tasks = []
        for search_result in results:
            task = self.task_storage.load(search_result.doc_id)
            if task:
                tasks.append(
                    {
                        "id": task.id,
                        "content": task.content,
                        "status": task.status.value,
                        "priority": task.priority.value,
                        "created_at": task.created_at.strftime("%Y-%m-%d %H:%M"),
                        "score": search_result.score,
                    }
                )

        return json.dumps(
            {"success": True, "query": query, "total_results": len(tasks), "tasks": tasks},
            ensure_ascii=False,
            indent=2,
        )


class UnifiedCheckpointTool(BaseTool):
    """Unified checkpoint tool."""

    def register(self, mcp_server) -> None:
        """Register the unified checkpoint tool."""

        @mcp_server.tool
        async def checkpoint(
            action: str,
            description: str | None = None,
            limit: int = 5,
            query: str | None = None,
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
                    return json.dumps(
                        {
                            "success": False,
                            "error": f"Unknown action: {action}. Use: save, list, search",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )

            except Exception as e:
                logger.error(f"Checkpoint operation failed: {e}")
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False, indent=2)

    async def _save_checkpoint(self, description: str | None) -> str:
        """Save a progress checkpoint."""
        if not description:
            return json.dumps(
                {"success": False, "error": "Description is required for save action"},
                ensure_ascii=False,
                indent=2,
            )

        # Get current project context
        project_id = self.config.get_current_project_id()
        project_path = self.config.get_current_project_path()

        checkpoint = Checkpoint(
            workspace_id="",
            project_id=project_id,
            project_path=project_path,
            description=description,
            session_id=f"session_{utc_now().strftime('%Y%m%d_%H%M%S')}",
        )

        checkpoint.set_ttl(self.config.default_checkpoint_ttl)

        if self.checkpoint_storage.save(checkpoint):
            self.search_engine.index_checkpoint(checkpoint)
            logger.info(f"Created checkpoint {checkpoint.id}")

            return json.dumps(
                {
                    "success": True,
                    "action": "progress_saved",
                    "checkpoint": {
                        "id": checkpoint.id,
                        "description": description,
                        "workspace_id": checkpoint.workspace_id,
                        "created_at": checkpoint.created_at.strftime("%Y-%m-%d %H:%M"),
                        "session_id": checkpoint.session_id,
                    },
                    "message": f"Saved progress: {description}",
                },
                ensure_ascii=False,
                indent=2,
            )
        else:
            return json.dumps({"success": False, "error": "Failed to save progress"}, ensure_ascii=False, indent=2)

    async def _list_checkpoints(self, limit: int) -> str:
        """List recent checkpoints."""
        checkpoints = self.checkpoint_storage.list_recent(limit)

        if not checkpoints:
            return json.dumps(
                {
                    "success": True,
                    "total_checkpoints": 0,
                    "checkpoints": [],
                    "message": "No saved progress found.",
                },
                ensure_ascii=False,
                indent=2,
            )

        checkpoints_data = [
            {
                "id": checkpoint.id,
                "description": checkpoint.description,
                "created_at": checkpoint.created_at.strftime("%Y-%m-%d %H:%M"),
                "workspace_id": checkpoint.workspace_id,
                "session_id": getattr(checkpoint, "session_id", ""),
                "highlights_count": len(getattr(checkpoint, "highlights", [])),
            }
            for checkpoint in checkpoints
        ]

        return json.dumps(
            {
                "success": True,
                "total_checkpoints": len(checkpoints),
                "checkpoints": checkpoints_data,
            },
            ensure_ascii=False,
            indent=2,
        )

    async def _search_checkpoints(self, query: str | None, limit: int) -> str:
        """Search checkpoints by content."""
        if not query:
            return json.dumps(
                {"success": False, "error": "Search query is required for search action"},
                ensure_ascii=False,
                indent=2,
            )

        results = self.search_engine.search(query=query, limit=limit, doc_types=["checkpoint"])

        if not results:
            return json.dumps(
                {
                    "success": True,
                    "query": query,
                    "total_results": 0,
                    "checkpoints": [],
                    "message": f"No checkpoints found for query: '{query}'",
                },
                ensure_ascii=False,
                indent=2,
            )

        checkpoints_data = []
        for search_result in results:
            checkpoint = self.checkpoint_storage.load(search_result.doc_id)
            if checkpoint:
                checkpoints_data.append(
                    {
                        "id": checkpoint.id,
                        "description": checkpoint.description,
                        "created_at": checkpoint.created_at.strftime("%Y-%m-%d %H:%M"),
                        "workspace_id": checkpoint.workspace_id,
                        "session_id": getattr(checkpoint, "session_id", ""),
                        "score": search_result.score,
                        "highlights_count": len(getattr(checkpoint, "highlights", [])),
                    }
                )

        return json.dumps(
            {
                "success": True,
                "query": query,
                "total_results": len(checkpoints_data),
                "checkpoints": checkpoints_data,
            },
            ensure_ascii=False,
            indent=2,
        )


class UnifiedRecallTool(BaseTool):
    """Unified recall tool."""

    def register(self, mcp_server) -> None:
        """Register the unified recall tool."""

        @mcp_server.tool
        async def recall(
            context: str = "recent",
            days_back: int = 7,
            session_id: str | None = None,
            git_branch: str | None = None,
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
                    return json.dumps(
                        {
                            "success": False,
                            "error": "Invalid context or missing required parameters",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )

            except Exception as e:
                logger.error(f"Recall operation failed: {e}")
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False, indent=2)

    async def _recall_quick(self) -> str:
        """Quick recall of the most recent context (last 2 days)."""

        context_data = await self._build_recall_context(days_back=2, include_tasks=True, include_plans=True, include_checkpoints=True)
        return self._build_recall_response(context_data)

    async def _recall_timeframe(self, days_back: int, include_tasks: bool, include_plans: bool, include_checkpoints: bool) -> str:
        """Recall context for a specific timeframe."""
        context_data = await self._build_recall_context(
            days_back=days_back,
            include_tasks=include_tasks,
            include_plans=include_plans,
            include_checkpoints=include_checkpoints,
        )
        return self._build_recall_response(context_data)

    async def _recall_session(self, session_id: str) -> str:
        """Recall context from a specific session."""
        context_data = await self._build_recall_context(
            days_back=30,  # Broader search for session-specific recall
            include_tasks=True,
            include_plans=True,
            include_checkpoints=True,
            session_id=session_id,
        )
        return self._build_recall_response(context_data)

    async def _recall_branch(self, git_branch: str, days_back: int) -> str:
        """Recall context for work on a specific git branch."""
        context_data = await self._build_recall_context(
            days_back=days_back,
            include_tasks=True,
            include_plans=True,
            include_checkpoints=True,
            git_branch=git_branch,
        )
        return self._build_recall_response(context_data)

    async def _build_recall_context(
        self,
        days_back: int,
        include_tasks: bool,
        include_plans: bool,
        include_checkpoints: bool,
        session_id: str | None = None,
        git_branch: str | None = None,
    ) -> dict[str, Any]:
        """Build the context information for recall."""
        from datetime import timedelta

        context = {
            "project_id": self.config.get_current_project_id(),
            "project_path": self.config.get_current_project_path(),
            "recall_time": utc_now(),
            "filter_applied": bool(session_id or git_branch),
            "checkpoints": [],
            "tasks": [],
            "plans": [],
            "summary": {},
        }

        # Calculate time range
        end_date = utc_now()
        start_date = end_date - timedelta(days=days_back)

        # Get checkpoints
        if include_checkpoints:
            if session_id:
                context["checkpoints"] = self.checkpoint_storage.find_by_session(session_id)
            elif git_branch:
                context["checkpoints"] = self.checkpoint_storage.find_by_git_branch(git_branch)
            else:
                context["checkpoints"] = self.checkpoint_storage.list_by_date_range(start_date, end_date)

        # Get tasks
        if include_tasks:
            all_tasks = self.task_storage.get_active_tasks()

            # Filter tasks by timeframe or specific criteria
            if session_id or git_branch:
                # For specific filters, get all active tasks
                context["tasks"] = all_tasks
            else:
                # For time-based, filter by creation/update time
                filtered_tasks = []
                for task in all_tasks:
                    if task.created_at >= start_date or (task.updated_at and task.updated_at >= start_date):
                        filtered_tasks.append(task)
                context["tasks"] = filtered_tasks

        # Get plans
        if include_plans:
            active_plans = self.plan_storage.find_active()

            # Filter similar to tasks
            if session_id or git_branch:
                context["plans"] = active_plans
            else:
                filtered_plans = []
                for plan in active_plans:
                    if plan.created_at >= start_date or (plan.updated_at and plan.updated_at >= start_date):
                        filtered_plans.append(plan)
                context["plans"] = filtered_plans

        # Build summary stats
        from ..models.task import TaskStatus

        context["summary"] = {
            "checkpoints_count": len(context["checkpoints"]),
            "tasks_count": len(context["tasks"]),
            "active_tasks": len([t for t in context["tasks"] if t.status == TaskStatus.IN_PROGRESS]),
            "pending_tasks": len([t for t in context["tasks"] if t.status == TaskStatus.PENDING]),
            "plans_count": len(context["plans"]),
            "days_covered": days_back,
            "session_filter": session_id,
            "branch_filter": git_branch,
        }

        return context

    def _build_recall_response(self, context: dict[str, Any]) -> str:
        """Build JSON response for recall context."""
        from ..models.task import TaskStatus

        return json.dumps(
            {
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
                        "session_id": getattr(cp, "session_id", ""),
                        "highlights_count": len(getattr(cp, "highlights", [])),
                    }
                    for cp in sorted(context["checkpoints"], key=lambda c: c.created_at, reverse=True)[:5]
                ],
                "tasks": {
                    "in_progress": [
                        {
                            "id": task.id,
                            "content": task.content,
                            "active_form": task.active_form,
                            "created_at": task.created_at.strftime("%Y-%m-%d %H:%M"),
                        }
                        for task in context["tasks"]
                        if task.status == TaskStatus.IN_PROGRESS
                    ],
                    "pending": [
                        {
                            "id": task.id,
                            "content": task.content,
                            "created_at": task.created_at.strftime("%Y-%m-%d %H:%M"),
                        }
                        for task in context["tasks"]
                        if task.status == TaskStatus.PENDING
                    ],
                },
                "plans": [
                    {
                        "id": plan.id,
                        "title": plan.title,
                        "description": (plan.description[:100] + "..." if len(plan.description) > 100 else plan.description),
                        "status": plan.status.value,
                        "progress": f"{plan.get_progress()[0]}/{plan.get_progress()[1]}",
                    }
                    for plan in context["plans"][:3]
                ],
            },
            ensure_ascii=False,
            indent=2,
        )


class UnifiedStandupTool(BaseTool):
    """Unified standup tool."""

    def register(self, mcp_server) -> None:
        """Register the unified standup tool."""

        @mcp_server.tool
        async def standup(timeframe: str = "daily", include_completed: bool = True, days_back: int = 1) -> str:
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
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False, indent=2)

    async def _build_standup_data(
        self,
        days_back: int,
        include_completed: bool,
        project_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Build standup report data using cross-project search."""
        # Use search engine for cross-project aggregation
        search_results = self.search_engine.search_cross_project(
            query="*",  # Get everything
            days_back=days_back,
            project_ids=project_ids,  # None = all projects
            limit=200,  # Get more results for standup
        )

        # Group results by type and project
        checkpoints_by_project: dict[str, list[Any]] = {}
        tasks_by_project: dict[str, list[Any]] = {}
        plans_by_project: dict[str, list[Any]] = {}

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

                elif result.doc_type == "task":
                    task = self.task_storage.load(result.doc_id)
                    if task:
                        project_id = task.project_id or "unknown"
                        if project_id not in tasks_by_project:
                            tasks_by_project[project_id] = []
                        tasks_by_project[project_id].append(task)

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

        # Filter completed tasks if requested
        completed_tasks_by_project = {}
        if include_completed:
            for project_id, tasks in tasks_by_project.items():
                completed = [t for t in tasks if t.status.value == "completed"]
                if completed:
                    completed_tasks_by_project[project_id] = completed

        # Get project registry for friendly names
        registry = self.config.load_projects_registry()
        dict(registry.items())

        return {
            "timeframe": days_back,
            "checkpoints_by_project": checkpoints_by_project,
            "tasks_by_project": tasks_by_project,
            "completed_tasks_by_project": completed_tasks_by_project,
            "plans_by_project": plans_by_project,
            "project_registry": registry,
            "total_projects": len(set(list(checkpoints_by_project.keys()) + list(tasks_by_project.keys()) + list(plans_by_project.keys()))),
        }

    def _build_standup_response(self, data: dict[str, Any], timeframe: str) -> str:
        """Build JSON response for cross-project standup report."""
        from ..models.task import TaskStatus

        # Calculate totals across all projects
        total_checkpoints = sum(len(cps) for cps in data["checkpoints_by_project"].values())
        total_tasks = sum(len(tasks) for tasks in data["tasks_by_project"].values())
        total_completed = sum(len(tasks) for tasks in data["completed_tasks_by_project"].values())
        total_plans = sum(len(plans) for plans in data["plans_by_project"].values())

        # Build project-specific data
        projects_data = {}
        for project_id in set(list(data["checkpoints_by_project"].keys()) + list(data["tasks_by_project"].keys()) + list(data["plans_by_project"].keys())):

            project_checkpoints = data["checkpoints_by_project"].get(project_id, [])
            project_tasks = data["tasks_by_project"].get(project_id, [])
            project_completed = data["completed_tasks_by_project"].get(project_id, [])
            project_plans = data["plans_by_project"].get(project_id, [])

            # Categorize tasks for this project
            in_progress = [t for t in project_tasks if t.status == TaskStatus.IN_PROGRESS]
            pending = [t for t in project_tasks if t.status == TaskStatus.PENDING]

            projects_data[project_id] = {
                "summary": {
                    "checkpoints": len(project_checkpoints),
                    "tasks_in_progress": len(in_progress),
                    "tasks_pending": len(pending),
                    "tasks_completed": len(project_completed),
                    "plans_active": len(project_plans),
                },
                "recent_activity": {
                    "checkpoints": [
                        {
                            "id": cp.id,
                            "description": cp.description,
                            "created_at": cp.created_at.strftime("%Y-%m-%d %H:%M"),
                            "project_path": (cp.project_path[:50] + "..." if len(cp.project_path) > 50 else cp.project_path),
                        }
                        for cp in sorted(project_checkpoints, key=lambda c: c.created_at, reverse=True)[:5]
                    ],
                    "tasks_in_progress": [
                        {
                            "id": task.id,
                            "content": task.content,
                            "active_form": task.active_form,
                            "started_at": (task.started_at.strftime("%Y-%m-%d %H:%M") if task.started_at else None),
                        }
                        for task in in_progress[:5]
                    ],
                    "tasks_completed": [
                        {
                            "id": task.id,
                            "content": task.content,
                            "completed_at": (task.completed_at.strftime("%Y-%m-%d %H:%M") if task.completed_at else None),
                        }
                        for task in project_completed[:5]
                    ],
                },
            }

        return json.dumps(
            {
                "success": True,
                "timeframe": timeframe,
                "days_covered": data["timeframe"],
                "cross_project_summary": {
                    "total_projects": data["total_projects"],
                    "total_checkpoints": total_checkpoints,
                    "total_tasks": total_tasks,
                    "total_completed": total_completed,
                    "total_plans": total_plans,
                },
                "projects": projects_data,
            },
            ensure_ascii=False,
            indent=2,
        )


class UnifiedPlanTool(BaseTool):
    """Unified plan tool - the starting point for complex multi-step work."""

    def register(self, mcp_server) -> None:
        """Register the unified plan tool."""

        @mcp_server.tool
        async def plan(
            action: str,
            title: str | None = None,
            description: str | None = None,
            plan_id: str | None = None,
            step_description: str | None = None,
            step_id: str | None = None,
            query: str | None = None,
            limit: int = 10,
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
                    return json.dumps(
                        {
                            "success": False,
                            "error": f"Unknown action: {action}. Use: create, list, activate, complete, add_step, complete_step, search",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )

            except Exception as e:
                logger.error(f"Plan operation failed: {e}")
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False, indent=2)

    async def _create_plan(self, title: str | None, description: str | None) -> str:
        """Create a new plan."""
        if not title:
            return json.dumps(
                {"success": False, "error": "Plan title is required for create action"},
                ensure_ascii=False,
                indent=2,
            )

        if not description:
            return json.dumps(
                {"success": False, "error": "Plan description is required for create action"},
                ensure_ascii=False,
                indent=2,
            )

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

            return json.dumps(
                {
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
                        "workspace_id": plan.workspace_id,
                    },
                    "message": f"Created plan: {title}",
                    "next_steps": "Use plan(action='add_step') to add steps, then plan(action='activate') to start working",
                },
                ensure_ascii=False,
                indent=2,
            )
        else:
            return json.dumps({"success": False, "error": "Failed to create plan"}, ensure_ascii=False, indent=2)

    async def _list_plans(self, limit: int) -> str:
        """List active plans."""
        active_plans = self.plan_storage.find_active()

        if not active_plans:
            return json.dumps(
                {
                    "success": True,
                    "total_plans": 0,
                    "plans": [],
                    "message": "No active plans found.",
                    "suggestion": "Use plan(action='create', title='...', description='...') to create one!",
                },
                ensure_ascii=False,
                indent=2,
            )

        # Limit results
        limited_plans = active_plans[:limit]

        plans_data = []
        for plan in limited_plans:
            completed_steps = len([s for s in plan.steps if s.completed])
            total_steps = len(plan.steps)

            plans_data.append(
                {
                    "id": plan.id,
                    "title": plan.title,
                    "description": (plan.description[:100] + "..." if len(plan.description) > 100 else plan.description),
                    "status": plan.status.value,
                    "priority": plan.priority,
                    "progress": f"{completed_steps}/{total_steps}",
                    "created_at": plan.created_at.strftime("%Y-%m-%d %H:%M"),
                    "updated_at": (plan.updated_at.strftime("%Y-%m-%d %H:%M") if plan.updated_at else None),
                }
            )

        return json.dumps(
            {
                "success": True,
                "total_plans": len(active_plans),
                "showing": len(limited_plans),
                "plans": plans_data,
                "suggestion": "Use plan(action='activate', plan_id='ID') to focus on a specific plan",
            },
            ensure_ascii=False,
            indent=2,
        )

    async def _activate_plan(self, plan_id: str | None) -> str:
        """Activate a plan to focus on it."""
        if not plan_id:
            return json.dumps(
                {"success": False, "error": "Plan ID is required for activate action"},
                ensure_ascii=False,
                indent=2,
            )

        plan = self.plan_storage.load(plan_id)
        if not plan:
            return json.dumps(
                {"success": False, "error": f"Plan {plan_id} not found"},
                ensure_ascii=False,
                indent=2,
            )

        if plan.status != PlanStatus.DRAFT:
            return json.dumps(
                {
                    "success": True,
                    "action": "plan_already_active",
                    "plan": {"id": plan.id, "title": plan.title, "status": plan.status.value},
                    "message": f"Plan '{plan.title}' is already {plan.status.value}",
                },
                ensure_ascii=False,
                indent=2,
            )

        plan.status = PlanStatus.ACTIVE
        plan.updated_at = utc_now()

        if self.plan_storage.save(plan):
            self.search_engine.index_plan(plan)

            completed_steps = len([s for s in plan.steps if s.completed])
            total_steps = len(plan.steps)

            return json.dumps(
                {
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
                                "notes": step.notes,
                            }
                            for step in plan.steps
                        ],
                    },
                    "message": f"Activated plan: {plan.title}",
                    "next_steps": "Start working on the plan steps. Use task(action='add') to create specific tasks for each step.",
                },
                ensure_ascii=False,
                indent=2,
            )
        else:
            return json.dumps({"success": False, "error": "Failed to activate plan"}, ensure_ascii=False, indent=2)

    async def _complete_plan(self, plan_id: str | None) -> str:
        """Mark a plan as completed."""
        if not plan_id:
            return json.dumps(
                {"success": False, "error": "Plan ID is required for complete action"},
                ensure_ascii=False,
                indent=2,
            )

        plan = self.plan_storage.load(plan_id)
        if not plan:
            return json.dumps(
                {"success": False, "error": f"Plan {plan_id} not found"},
                ensure_ascii=False,
                indent=2,
            )

        if plan.status == PlanStatus.COMPLETED:
            return json.dumps(
                {
                    "success": True,
                    "action": "plan_already_completed",
                    "plan": {"id": plan.id, "title": plan.title, "status": plan.status.value},
                    "message": f"Plan '{plan.title}' is already completed",
                },
                ensure_ascii=False,
                indent=2,
            )

        plan.status = PlanStatus.COMPLETED
        plan.updated_at = utc_now()

        # Mark all steps as completed
        for step in plan.steps:
            if not step.completed:
                step.completed = True
                step.completed_at = utc_now()

        if self.plan_storage.save(plan):
            self.search_engine.index_plan(plan)

            return json.dumps(
                {
                    "success": True,
                    "action": "plan_completed",
                    "plan": {
                        "id": plan.id,
                        "title": plan.title,
                        "status": plan.status.value,
                        "completed_steps": len(plan.steps),
                        "completed_at": plan.updated_at.strftime("%Y-%m-%d %H:%M"),
                    },
                    "message": f"Completed plan: {plan.title}",
                    "celebration": "🎉 Great job finishing this plan!",
                },
                ensure_ascii=False,
                indent=2,
            )
        else:
            return json.dumps({"success": False, "error": "Failed to complete plan"}, ensure_ascii=False, indent=2)

    async def _add_step(self, plan_id: str | None, step_description: str | None) -> str:
        """Add a step to a plan."""
        if not plan_id:
            return json.dumps(
                {"success": False, "error": "Plan ID is required for add_step action"},
                ensure_ascii=False,
                indent=2,
            )

        if not step_description:
            return json.dumps(
                {"success": False, "error": "Step description is required for add_step action"},
                ensure_ascii=False,
                indent=2,
            )

        plan = self.plan_storage.load(plan_id)
        if not plan:
            return json.dumps(
                {"success": False, "error": f"Plan {plan_id} not found"},
                ensure_ascii=False,
                indent=2,
            )

        # Create new step
        new_step = PlanStep(description=step_description, completed=False)

        plan.steps.append(new_step)
        plan.updated_at = utc_now()

        if self.plan_storage.save(plan):
            self.search_engine.index_plan(plan)

            return json.dumps(
                {
                    "success": True,
                    "action": "step_added",
                    "plan": {"id": plan.id, "title": plan.title, "total_steps": len(plan.steps)},
                    "step": {
                        "id": new_step.id,
                        "description": step_description,
                        "completed": False,
                    },
                    "message": f"Added step to plan '{plan.title}': {step_description}",
                },
                ensure_ascii=False,
                indent=2,
            )
        else:
            return json.dumps(
                {"success": False, "error": "Failed to add step to plan"},
                ensure_ascii=False,
                indent=2,
            )

    async def _complete_step(self, step_id: str | None) -> str:
        """Mark a plan step as completed."""
        if not step_id:
            return json.dumps(
                {"success": False, "error": "Step ID is required for complete_step action"},
                ensure_ascii=False,
                indent=2,
            )

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
            return json.dumps(
                {"success": False, "error": f"Step {step_id} not found"},
                ensure_ascii=False,
                indent=2,
            )

        if target_step.completed:
            return json.dumps(
                {
                    "success": True,
                    "action": "step_already_completed",
                    "step": {
                        "id": step_id,
                        "description": target_step.description,
                        "completed": True,
                    },
                    "message": f"Step already completed: {target_step.description}",
                },
                ensure_ascii=False,
                indent=2,
            )

        target_step.completed = True
        target_step.completed_at = utc_now()
        target_plan.updated_at = utc_now()

        if self.plan_storage.save(target_plan):
            self.search_engine.index_plan(target_plan)

            completed_steps = len([s for s in target_plan.steps if s.completed])
            total_steps = len(target_plan.steps)

            return json.dumps(
                {
                    "success": True,
                    "action": "step_completed",
                    "plan": {
                        "id": target_plan.id,
                        "title": target_plan.title,
                        "progress": f"{completed_steps}/{total_steps}",
                    },
                    "step": {
                        "id": step_id,
                        "description": target_step.description,
                        "completed_at": target_step.completed_at.strftime("%Y-%m-%d %H:%M"),
                    },
                    "message": f"Completed step: {target_step.description}",
                    "plan_status": ("Plan completed!" if completed_steps == total_steps else f"Progress: {completed_steps}/{total_steps} steps done"),
                },
                ensure_ascii=False,
                indent=2,
            )
        else:
            return json.dumps({"success": False, "error": "Failed to complete step"}, ensure_ascii=False, indent=2)

    async def _search_plans(self, query: str | None, limit: int) -> str:
        """Search plans by content."""
        if not query:
            return json.dumps(
                {"success": False, "error": "Search query is required for search action"},
                ensure_ascii=False,
                indent=2,
            )

        results = self.search_engine.search(query=query, limit=limit, doc_types=["plan"])

        if not results:
            return json.dumps(
                {
                    "success": True,
                    "query": query,
                    "total_results": 0,
                    "plans": [],
                    "message": f"No plans found for query: '{query}'",
                },
                ensure_ascii=False,
                indent=2,
            )

        plans_data = []
        for search_result in results:
            plan = self.plan_storage.load(search_result.doc_id)
            if plan:
                completed_steps = len([s for s in plan.steps if s.completed])
                total_steps = len(plan.steps)

                plans_data.append(
                    {
                        "id": plan.id,
                        "title": plan.title,
                        "description": (plan.description[:100] + "..." if len(plan.description) > 100 else plan.description),
                        "status": plan.status.value,
                        "priority": plan.priority,
                        "progress": f"{completed_steps}/{total_steps}",
                        "created_at": plan.created_at.strftime("%Y-%m-%d %H:%M"),
                        "score": search_result.score,
                    }
                )

        return json.dumps(
            {
                "success": True,
                "query": query,
                "total_results": len(plans_data),
                "plans": plans_data,
            },
            ensure_ascii=False,
            indent=2,
        )


class UnifiedCleanupTool(BaseTool):
    """Unified system cleanup tool."""

    def register(self, mcp_server) -> None:
        """Register the unified cleanup tool."""

        @mcp_server.tool
        async def cleanup(target: str = "locks", force: bool = False) -> str:
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
                        return json.dumps(
                            {
                                "success": True,
                                "message": "Successfully cleaned up stale lock files",
                                "force_used": force,
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                    else:
                        return json.dumps(
                            {
                                "success": True,
                                "message": "No stale lock files found to clean up",
                                "force_used": force,
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                else:
                    return json.dumps(
                        {
                            "success": False,
                            "error": f"Unknown cleanup target: {target}. Supported: 'locks'",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )

            except Exception as e:
                logger.error(f"Cleanup operation failed: {e}")
                return json.dumps(
                    {"success": False, "error": f"Cleanup failed: {str(e)}"},
                    ensure_ascii=False,
                    indent=2,
                )