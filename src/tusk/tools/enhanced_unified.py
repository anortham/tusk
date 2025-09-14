"""Enhanced unified tools for Tusk with rich parameter descriptions."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List
from uuid import uuid4

from ..models.todo import Todo, TodoStatus, TodoPriority
from ..models.checkpoint import Checkpoint
from ..models.plan import Plan, PlanStatus, PlanStep
from .base import BaseTool
from .enhancement import ToolEnhancer

logger = logging.getLogger(__name__)


class EnhancedUnifiedTodoTool(BaseTool):
    """Enhanced unified todo tool with rich parameter descriptions."""

    def register(self, mcp_server) -> None:
        """Register the enhanced unified todo tool."""

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

            This tool provides comprehensive task management capabilities across sessions.
            Use this for all task-related operations to maintain persistent todo lists
            that survive context resets and session changes.

            Args:
                action: The operation to perform. Valid values are "add" (create new task),
                    "list" (show active tasks), "start" (mark task in progress),
                    "complete" (mark task finished), "update" (change task status),
                    "search" (find tasks by content). This parameter is required.
                task: The task description when adding new tasks. Should be clear and
                    actionable (e.g., "Fix authentication bug in login.py"). Only required
                    for action="add".
                task_id: The unique identifier of the task to operate on. Required for
                    "start", "complete", and "update" actions. Use action="list" to see
                    task IDs.
                status: New status when updating tasks. Valid values are "pending"
                    (not started), "in_progress" (actively working), "completed" (finished).
                    Only used with action="update".
                query: Search query text for finding tasks. Searches task content and
                    descriptions. Use specific keywords for better results. Only used
                    with action="search".
                limit: Maximum number of results to return for "list" and "search" actions.
                    Default 10, maximum recommended 50 to avoid overwhelming output.

            Returns:
                JSON response with operation results, task details, and status information.
                Success responses include task data, counts, and helpful suggestions.
                Error responses include specific error messages and corrective guidance.

            Examples:
                todo(action="add", task="Fix the bug in login system")
                todo(action="list")
                todo(action="start", task_id="abc123")
                todo(action="complete", task_id="abc123")
                todo(action="update", task_id="abc123", status="in_progress")
                todo(action="search", query="bug", limit=5)
            """
            # After registration, enhance the tool with parameter descriptions
            if hasattr(mcp_server, '_tool_manager') and hasattr(mcp_server._tool_manager, '_tools'):
                if 'todo' in mcp_server._tool_manager._tools:
                    tool = mcp_server._tool_manager._tools['todo']

                    # Enhance parameters
                    if hasattr(tool, 'parameters'):
                        tool.parameters = ToolEnhancer.enhance_tool_parameters(todo, tool.parameters)

                    # Enhance description
                    if hasattr(tool, 'description'):
                        tool.description = ToolEnhancer.enhance_tool_description(todo, tool.description or "")

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

        if self.todo_storage.save(todo):
            self.search_engine.index_todo(todo)
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
        active_todos = self.todo_storage.get_active_todos()[:limit]

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

        todo = self.todo_storage.load(task_id)
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

        if self.todo_storage.save(todo):
            self.search_engine.index_todo(todo)
            logger.info(f"Started todo {todo.id}")

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
                "message": f"Started: {todo.get_display_form()}"
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

        todo = self.todo_storage.load(task_id)
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
                "message": f"Already completed: {todo.content}"
            }, ensure_ascii=False, indent=2)

        todo.mark_completed()

        if self.todo_storage.save(todo):
            self.search_engine.index_todo(todo)
            logger.info(f"Completed todo {todo.id}")

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
            new_status = TodoStatus(status)
        except ValueError:
            return json.dumps({
                "success": False,
                "error": f"Invalid status: {status}. Use: pending, in_progress, completed"
            }, ensure_ascii=False, indent=2)

        todo = self.todo_storage.load(task_id)
        if not todo:
            return json.dumps({
                "success": False,
                "error": f"Task {task_id} not found"
            }, ensure_ascii=False, indent=2)

        old_status = todo.status

        # Update status
        if new_status == TodoStatus.IN_PROGRESS:
            todo.mark_in_progress()
        elif new_status == TodoStatus.COMPLETED:
            todo.mark_completed()
        elif new_status == TodoStatus.PENDING:
            todo.status = TodoStatus.PENDING
            todo.started_at = None
            todo.completed_at = None

        if self.todo_storage.save(todo):
            self.search_engine.index_todo(todo)
            logger.info(f"Updated todo {todo.id} status: {old_status.value} -> {new_status.value}")

            return json.dumps({
                "success": True,
                "action": "task_updated",
                "task": {
                    "id": todo.id,
                    "content": todo.content,
                    "old_status": old_status.value,
                    "new_status": new_status.value,
                    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
                },
                "message": f"Updated {todo.content}: {old_status.value} -> {new_status.value}"
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

        # Search todos
        search_results = self.search_engine.search_todos(query, limit=limit)

        if not search_results:
            return json.dumps({
                "success": True,
                "query": query,
                "total_results": 0,
                "message": f"No tasks found matching '{query}'",
                "suggestion": "Try broader search terms or use todo(action='list') to see all tasks"
            }, ensure_ascii=False, indent=2)

        # Format results
        formatted_results = []
        for result in search_results:
            todo_data = {
                "id": result.id,
                "content": result.content,
                "status": result.status.value,
                "priority": result.priority.value,
                "created_at": result.created_at.strftime("%Y-%m-%d %H:%M"),
                "project_id": result.project_id,
                "relevance": "High"  # Could add scoring later
            }

            if result.status == TodoStatus.IN_PROGRESS and result.started_at:
                todo_data["started_at"] = result.started_at.strftime("%Y-%m-%d %H:%M")
                todo_data["active_form"] = result.active_form

            if result.status == TodoStatus.COMPLETED and result.completed_at:
                todo_data["completed_at"] = result.completed_at.strftime("%Y-%m-%d %H:%M")

            formatted_results.append(todo_data)

        return json.dumps({
            "success": True,
            "query": query,
            "total_results": len(formatted_results),
            "tasks": formatted_results,
            "message": f"Found {len(formatted_results)} tasks matching '{query}'",
            "suggestion": "Use task ID with other actions to start, complete, or update tasks"
        }, ensure_ascii=False, indent=2)