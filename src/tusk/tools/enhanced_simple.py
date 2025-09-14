"""Enhanced unified tools using the enhanced base class."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from ..models.task import Task, TaskStatus, TaskPriority
from ..models.checkpoint import Checkpoint
from ..models.plan import Plan, PlanStatus, PlanStep
from .enhanced_base import EnhancedBaseTool

logger = logging.getLogger(__name__)


class EnhancedUnifiedTaskTool(EnhancedBaseTool):
    """Enhanced unified task tool with rich parameter descriptions."""

    def register(self, mcp_server) -> None:
        """Register the enhanced unified task tool."""

        @mcp_server.tool
        async def task(
            action: str,
            task: str | None = None,
            task_id: str | None = None,
            status: str | None = None,
            query: str | None = None,
            limit: int = 10
        ) -> str:
            """Manage tasks efficiently with one simple tool.

            Provides persistent task management across sessions for task lists that survive context resets.

            Args:
                action: Required. Operations: "add" (new task), "list" (active tasks),
                    "start" (mark in progress), "complete" (mark finished), "update" (change status), "search" (find by content)
                task: Task description for "add" action. Example: "Fix auth bug in login.py"
                task_id: Task ID for "start"/"complete"/"update" actions. Get from "list" action
                status: New status for "update": "pending"/"in_progress"/"completed"
                query: Search text for "search" action. Searches task content
                limit: Max results for "list"/"search" (default 10, max 50)

            Returns:
                JSON with operation results, task details, and status info.
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
                logger.error(f"Task operation failed: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e)
                }, ensure_ascii=False, indent=2)

        # After registration, enhance the tool with rich parameter descriptions
        self.enhance_registered_tools(mcp_server, ['task'])

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

        task = Task(
            workspace_id="",
            project_id=project_id,
            project_path=project_path,
            content=task,
            active_form=f"Working on {task.lower()}",
            priority=TaskPriority.MEDIUM,
            status=TaskStatus.PENDING,
        )

        if self.task_storage.save(task):
            self.search_engine.index_task(task)
            logger.info(f"Created task {task.id}")

            return json.dumps({
                "success": True,
                "action": "task_added",
                "task": {
                    "id": task.id,
                    "content": task,
                    "priority": task.priority.value,
                    "status": task.status.value,
                    "created_at": task.created_at.strftime("%Y-%m-%d %H:%M")
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
        active_tasks = self.task_storage.get_active_tasks()[:limit]

        if not active_tasks:
            return json.dumps({
                "success": True,
                "total_tasks": 0,
                "message": "No active tasks",
                "suggestion": "Use task(action='add', task='your task') to create one!"
            }, ensure_ascii=False, indent=2)

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
                        "started_at": task.started_at.strftime("%Y-%m-%d %H:%M") if task.started_at else None
                    }
                    for task in in_progress
                ],
                "pending": [
                    {
                        "id": task.id,
                        "content": task.content,
                        "priority": task.priority.value,
                        "created_at": task.created_at.strftime("%Y-%m-%d %H:%M")
                    }
                    for task in pending
                ]
            },
            "counts": {
                "in_progress": len(in_progress),
                "pending": len(pending)
            },
            "suggestion": "Use task(action='start', task_id='ID') or task(action='complete', task_id='ID')"
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _start_task(self, task_id: Optional[str]) -> str:
        """Start working on a task."""
        if not task_id:
            return json.dumps({
                "success": False,
                "error": "Task ID is required for start action"
            }, ensure_ascii=False, indent=2)

        task = self.task_storage.load(task_id)
        if not task:
            return json.dumps({
                "success": False,
                "error": f"Task {task_id} not found"
            }, ensure_ascii=False, indent=2)

        if task.status == TaskStatus.IN_PROGRESS:
            return json.dumps({
                "success": True,
                "action": "task_already_started",
                "task": {
                    "id": task.id,
                    "content": task.content,
                    "active_form": task.active_form,
                    "status": task.status.value
                },
                "message": f"Already working on: {task.get_display_form()}"
            }, ensure_ascii=False, indent=2)

        task.mark_in_progress()

        if self.task_storage.save(task):
            self.search_engine.index_task(task)
            logger.info(f"Started task {task.id}")

            return json.dumps({
                "success": True,
                "action": "task_started",
                "task": {
                    "id": task.id,
                    "content": task.content,
                    "active_form": task.active_form,
                    "status": task.status.value,
                    "started_at": task.started_at.strftime("%Y-%m-%d %H:%M") if task.started_at else None
                },
                "message": f"Started: {task.get_display_form()}"
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "success": False,
                "error": "Failed to start task"
            }, ensure_ascii=False, indent=2)

    async def _complete_task(self, task_id: Optional[str]) -> str:
        """Complete a task."""
        if not task_id:
            return json.dumps({
                "success": False,
                "error": "Task ID is required for complete action"
            }, ensure_ascii=False, indent=2)

        task = self.task_storage.load(task_id)
        if not task:
            return json.dumps({
                "success": False,
                "error": f"Task {task_id} not found"
            }, ensure_ascii=False, indent=2)

        if task.status == TaskStatus.COMPLETED:
            return json.dumps({
                "success": True,
                "action": "task_already_completed",
                "task": {
                    "id": task.id,
                    "content": task.content,
                    "status": task.status.value
                },
                "message": f"Already completed: {task.content}"
            }, ensure_ascii=False, indent=2)

        task.mark_completed()

        if self.task_storage.save(task):
            self.search_engine.index_task(task)
            logger.info(f"Completed task {task.id}")

            return json.dumps({
                "success": True,
                "action": "task_completed",
                "task": {
                    "id": task.id,
                    "content": task.content,
                    "status": task.status.value,
                    "completed_at": task.completed_at.strftime("%Y-%m-%d %H:%M") if task.completed_at else None
                },
                "message": f"Completed: {task.content}",
                "celebration": "🎉 Great work!"
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "success": False,
                "error": "Failed to complete task"
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
        try:
            new_status = TaskStatus(status)
        except ValueError:
            return json.dumps({
                "success": False,
                "error": f"Invalid status: {status}. Use: pending, in_progress, completed"
            }, ensure_ascii=False, indent=2)

        task = self.task_storage.load(task_id)
        if not task:
            return json.dumps({
                "success": False,
                "error": f"Task {task_id} not found"
            }, ensure_ascii=False, indent=2)

        old_status = task.status

        # Update status
        if new_status == TaskStatus.IN_PROGRESS:
            task.mark_in_progress()
        elif new_status == TaskStatus.COMPLETED:
            task.mark_completed()
        elif new_status == TaskStatus.PENDING:
            task.status = TaskStatus.PENDING
            task.started_at = None
            task.completed_at = None

        if self.task_storage.save(task):
            self.search_engine.index_task(task)
            logger.info(f"Updated task {task.id} status: {old_status.value} -> {new_status.value}")

            return json.dumps({
                "success": True,
                "action": "task_updated",
                "task": {
                    "id": task.id,
                    "content": task.content,
                    "old_status": old_status.value,
                    "new_status": new_status.value,
                    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
                },
                "message": f"Updated {task.content}: {old_status.value} -> {new_status.value}"
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "success": False,
                "error": "Failed to update task"
            }, ensure_ascii=False, indent=2)

    async def _search_tasks(self, query: Optional[str], limit: int) -> str:
        """Search for tasks by query."""
        if not query:
            return json.dumps({
                "success": False,
                "error": "Query is required for search action"
            }, ensure_ascii=False, indent=2)

        # Search tasks
        search_results = self.search_engine.search_tasks(query, limit=limit)

        if not search_results:
            return json.dumps({
                "success": True,
                "query": query,
                "total_results": 0,
                "message": f"No tasks found matching '{query}'",
                "suggestion": "Try broader search terms or use task(action='list') to see all tasks"
            }, ensure_ascii=False, indent=2)

        # Format results
        formatted_results = []
        for result in search_results:
            task_data = {
                "id": result.id,
                "content": result.content,
                "status": result.status.value,
                "priority": result.priority.value,
                "created_at": result.created_at.strftime("%Y-%m-%d %H:%M"),
                "project_id": result.project_id,
                "relevance": "High"  # Could add scoring later
            }

            if result.status == TaskStatus.IN_PROGRESS and result.started_at:
                task_data["started_at"] = result.started_at.strftime("%Y-%m-%d %H:%M")
                task_data["active_form"] = result.active_form

            if result.status == TaskStatus.COMPLETED and result.completed_at:
                task_data["completed_at"] = result.completed_at.strftime("%Y-%m-%d %H:%M")

            formatted_results.append(task_data)

        return json.dumps({
            "success": True,
            "query": query,
            "total_results": len(formatted_results),
            "tasks": formatted_results,
            "message": f"Found {len(formatted_results)} tasks matching '{query}'",
            "suggestion": "Use task ID with other actions to start, complete, or update tasks"
        }, ensure_ascii=False, indent=2)