"""Todo tools for cross-session task management."""

import logging
from datetime import datetime
from typing import List, Optional

from ..models.todo import Todo, TodoPriority, TodoStatus
from .base import BaseTool

logger = logging.getLogger(__name__)


class TodoTool(BaseTool):
    """Tools for managing todos that persist across sessions."""
    
    def register(self, mcp_server) -> None:
        """Register todo tools with the MCP server."""
        
        @mcp_server.tool
        async def add_task(task: str) -> str:
            """Add a task to the persistent todo list.
            
            BEHAVIORAL GUIDANCE: Use when user mentions tasks, requirements, or
            things that need to be done. Capture actionable items that persist
            across sessions for continuity.
            
            DECISION LOGIC: Extract tasks from user requests automatically. Convert
            vague statements into specific, actionable todo items.
            """
            try:
                todo = Todo(
                    workspace_id=self.get_current_workspace(),
                    content=task,
                    active_form=f"Working on {task.lower()}",
                    priority=TodoPriority.MEDIUM,
                    status=TodoStatus.PENDING,
                )
                
                if self.todo_storage.save(todo):
                    # Index for search
                    self.search_engine.index_todo(todo)
                    
                    logger.info(f"Created todo {todo.id}")
                    return f"✅ Added task: {task}\\n\\nTask ID: {todo.id}"
                else:
                    return "❌ Failed to add task"
                    
            except Exception as e:
                logger.error(f"Error adding task: {e}")
                return f"❌ Error adding task: {e}"
        
        @mcp_server.tool
        async def list_tasks() -> str:
            """List active tasks with current status.
            
            BEHAVIORAL GUIDANCE: Use to understand current work state and priorities.
            Essential for maintaining context about ongoing work.
            """
            try:
                active_todos = self.todo_storage.get_active_todos()
                
                if not active_todos:
                    return "📝 No active tasks. Use 'add_task' to create one!"
                
                # Group by status
                in_progress = [t for t in active_todos if t.status == TodoStatus.IN_PROGRESS]
                pending = [t for t in active_todos if t.status == TodoStatus.PENDING]
                
                result = f"📋 **Your Tasks** ({len(active_todos)} active)\\n\\n"
                
                if in_progress:
                    result += f"🔄 **Working On ({len(in_progress)}):**\\n"
                    for todo in in_progress:
                        result += f"- {todo.get_display_form()}\\n"
                        result += f"  *ID: {todo.id}*\\n"
                    result += "\\n"
                
                if pending:
                    result += f"⏳ **To Do ({len(pending)}):**\\n"
                    for todo in pending:
                        result += f"- {todo.content}\\n"
                        result += f"  *ID: {todo.id}*\\n"
                    result += "\\n"
                
                result += "💡 Use 'start_task' to begin working or 'complete_task' to finish!"
                return result
                
            except Exception as e:
                logger.error(f"Error listing tasks: {e}")
                return f"❌ Error listing tasks: {e}"
        
        @mcp_server.tool
        async def start_task(task_id: str) -> str:
            """Mark a task as in-progress.
            
            BEHAVIORAL GUIDANCE: Use when beginning work on a specific task.
            Important for tracking active work state across sessions.
            """
            try:
                todo = self.todo_storage.load(task_id)
                if not todo:
                    return f"❌ Task {task_id} not found"
                
                if todo.status == TodoStatus.IN_PROGRESS:
                    return f"✋ Already working on: {todo.get_display_form()}"
                
                todo.mark_in_progress()
                
                if self.todo_storage.save(todo):
                    # Update search index
                    self.search_engine.index_todo(todo)
                    
                    return f"🔄 Started working on: {todo.get_display_form()}"
                else:
                    return "❌ Failed to update task"
                    
            except Exception as e:
                logger.error(f"Error starting task: {e}")
                return f"❌ Error starting task: {e}"
        
        @mcp_server.tool
        async def complete_task(task_id: str) -> str:
            """Mark a task as completed.
            
            BEHAVIORAL GUIDANCE: Use when task is fully accomplished. Creates
            closure and maintains accurate state for future sessions.
            
            DECISION LOGIC: Automatically trigger when user indicates task completion
            or when evidence shows task was finished.
            """
            try:
                todo = self.todo_storage.load(task_id)
                if not todo:
                    return f"❌ Task {task_id} not found"
                
                if todo.status == TodoStatus.COMPLETED:
                    return f"✅ Task already completed: {todo.content}"
                
                todo.mark_completed()
                
                if self.todo_storage.save(todo):
                    # Update search index
                    self.search_engine.index_todo(todo)
                    
                    return f"🎉 Completed: {todo.content}\\n\\nGreat job! The task is now done."
                else:
                    return "❌ Failed to update task"
                    
            except Exception as e:
                logger.error(f"Error completing task: {e}")
                return f"❌ Error completing task: {e}"
        
        @mcp_server.tool
        async def search_todos(query: str, limit: int = 10) -> str:
            """Search todos by content using full-text search.
            
            BEHAVIORAL GUIDANCE: Use when user asks about specific tasks or
            when you need to find related work items from history.
            """
            try:
                results = self.search_engine.search(
                    query=query,
                    limit=limit,
                    doc_types=["todo"]
                )
                
                if not results:
                    return f"No todos found for query: '{query}'"
                
                result = f"🔍 **Todo Search Results** for '{query}' ({len(results)} found)\\n\\n"
                
                for i, search_result in enumerate(results, 1):
                    todo = self.todo_storage.load(search_result.doc_id)
                    if todo:
                        status_icon = {
                            TodoStatus.PENDING: "⏳",
                            TodoStatus.IN_PROGRESS: "🔄",
                            TodoStatus.COMPLETED: "✅",
                            TodoStatus.BLOCKED: "🚫",
                            TodoStatus.CANCELLED: "❌",
                        }.get(todo.status, "❓")
                        
                        result += f"**{i}. {status_icon} {todo.content}** (score: {search_result.score:.2f})\\n"
                        result += f"   ID: `{todo.id}`\\n"
                        result += f"   Status: {todo.status.value} | Priority: {todo.priority.value}\\n\\n"
                
                return result
                
            except Exception as e:
                logger.error(f"Error searching todos: {e}")
                return f"❌ Error searching todos: {e}"