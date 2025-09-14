"""Storage for todo data in a single JSON file per workspace."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import portalocker

from ..config import TuskConfig
from ..models.task import Task, TaskStatus

logger = logging.getLogger(__name__)


class TaskStorage:
    """Storage for tasks using a single JSON file per workspace."""
    
    def __init__(self, config: TuskConfig):
        self.config = config
        self.data_dir = config.get_data_dir()
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """Ensure storage directories exist."""
        todos_dir = self.data_dir / "todos"
        todos_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_todos_file(self) -> Path:
        """Get the todos file path."""
        return self.data_dir / "todos" / "todos.json"
    
    def _load_todos_file(self) -> Dict[str, Dict]:
        """Load all todos from the JSON file."""
        todos_file = self._get_todos_file()
        
        if not todos_file.exists():
            return {}
        
        try:
            with open(todos_file, 'r', encoding='utf-8') as f:
                portalocker.lock(f, portalocker.LOCK_SH)
                try:
                    return json.load(f)
                finally:
                    portalocker.unlock(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error reading todos file: {e}")
            return {}
    
    def _save_todos_file(self, todos_data: Dict[str, Dict]) -> bool:
        """Save all todos to the JSON file."""
        todos_file = self._get_todos_file()
        
        try:
            with open(todos_file, 'w', encoding='utf-8') as f:
                portalocker.lock(f, portalocker.LOCK_EX)
                try:
                    json.dump(todos_data, f, indent=2, ensure_ascii=False, default=self._json_serializer)
                finally:
                    portalocker.unlock(f)
            return True
        except IOError as e:
            logger.error(f"Error writing todos file: {e}")
            return False
    
    def _json_serializer(self, obj):
        """Custom JSON serializer for datetime objects."""
        from datetime import datetime
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    def load(self, todo_id: str) -> Optional[Task]:
        """Load a todo by ID."""
        todos_data = self._load_todos_file()
        
        if todo_id not in todos_data:
            return None
        
        try:
            return Task.model_validate(todos_data[todo_id])
        except Exception as e:
            logger.error(f"Error deserializing todo {todo_id}: {e}")
            return None
    
    def save(self, todo: Task) -> bool:
        """Save a todo."""
        todos_data = self._load_todos_file()
        
        try:
            todos_data[todo.id] = todo.model_dump(mode='json')
            success = self._save_todos_file(todos_data)
            
            if success:
                logger.debug(f"Saved todo {todo.id}")
            else:
                logger.error(f"Failed to save todo {todo.id}")
            
            return success
        except Exception as e:
            logger.error(f"Error saving todo: {e}")
            return False
    
    def delete(self, todo_id: str) -> bool:
        """Delete a todo by ID."""
        todos_data = self._load_todos_file()
        
        if todo_id not in todos_data:
            return True  # Already deleted
        
        try:
            del todos_data[todo_id]
            success = self._save_todos_file(todos_data)
            
            if success:
                logger.debug(f"Deleted todo {todo_id}")
            else:
                logger.error(f"Failed to delete todo {todo_id}")
            
            return success
        except Exception as e:
            logger.error(f"Error deleting todo {todo_id}: {e}")
            return False
    
    def exists(self, todo_id: str) -> bool:
        """Check if a todo exists."""
        todos_data = self._load_todos_file()
        return todo_id in todos_data
    
    def load_all(self) -> List[Task]:
        """Load all todos."""
        todos_data = self._load_todos_file()
        todos = []
        
        for todo_id, todo_data in todos_data.items():
            try:
                todo = Task.model_validate(todo_data)
                todos.append(todo)
            except Exception as e:
                logger.error(f"Error deserializing todo {todo_id}: {e}")
        
        return todos
    
    def list_ids(self) -> List[str]:
        """List all todo IDs."""
        todos_data = self._load_todos_file()
        return sorted(todos_data.keys())
    
    def count(self) -> int:
        """Count the number of todos."""
        return len(self.list_ids())
    
    def find_by_status(self, status: TaskStatus) -> List[Task]:
        """Find todos by status."""
        all_todos = self.load_all()
        return [todo for todo in all_todos if todo.status == status]
    
    def find_pending(self) -> List[Task]:
        """Find all pending todos."""
        return self.find_by_status(TaskStatus.PENDING)
    
    def find_in_progress(self) -> List[Task]:
        """Find all in-progress todos."""
        return self.find_by_status(TaskStatus.IN_PROGRESS)
    
    def find_completed(self) -> List[Task]:
        """Find all completed todos."""
        return self.find_by_status(TaskStatus.COMPLETED)
    
    def find_by_checkpoint(self, checkpoint_id: str) -> List[Task]:
        """Find todos linked to a specific checkpoint."""
        all_todos = self.load_all()
        return [todo for todo in all_todos if todo.checkpoint_id == checkpoint_id]
    
    def find_by_plan(self, plan_id: str) -> List[Task]:
        """Find todos linked to a specific plan."""
        all_todos = self.load_all()
        return [todo for todo in all_todos if todo.plan_id == plan_id]
    
    def find_by_tags(self, tags: List[str]) -> List[Task]:
        """Find todos that have any of the specified tags."""
        all_todos = self.load_all()
        matching_todos = []
        
        for todo in all_todos:
            if any(tag in todo.tags for tag in tags):
                matching_todos.append(todo)
        
        return matching_todos
    
    def find_overdue(self) -> List[Task]:
        """Find todos that are overdue."""
        all_todos = self.load_all()
        return [todo for todo in all_todos if todo.is_overdue()]
    
    def get_active_tasks(self) -> List[Task]:
        """Get todos that are pending or in progress."""
        all_todos = self.load_all()
        return [
            todo for todo in all_todos 
            if todo.status in [TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
        ]
    
    def get_summary_stats(self) -> Dict[str, int]:
        """Get summary statistics about todos."""
        all_todos = self.load_all()
        
        stats = {
            "total": len(all_todos),
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "blocked": 0,
            "cancelled": 0,
            "overdue": 0,
        }
        
        for todo in all_todos:
            stats[todo.status.value] = stats.get(todo.status.value, 0) + 1
            if todo.is_overdue():
                stats["overdue"] += 1
        
        return stats
    
    def bulk_update_status(self, todo_ids: List[str], new_status: TaskStatus) -> int:
        """Update status for multiple todos. Returns count of updated todos."""
        updated_count = 0
        todos_data = self._load_todos_file()
        
        for todo_id in todo_ids:
            if todo_id in todos_data:
                try:
                    todo = Task.model_validate(todos_data[todo_id])
                    
                    # Update status using the appropriate method
                    if new_status == TaskStatus.IN_PROGRESS:
                        todo.mark_in_progress()
                    elif new_status == TaskStatus.COMPLETED:
                        todo.mark_completed()
                    elif new_status == TaskStatus.BLOCKED:
                        todo.mark_blocked()
                    else:
                        todo.status = new_status
                        todo.updated_at = datetime.now(timezone.utc)
                    
                    todos_data[todo_id] = todo.model_dump(mode='json')
                    updated_count += 1
                except Exception as e:
                    logger.error(f"Error updating todo {todo_id}: {e}")
        
        if updated_count > 0:
            self._save_todos_file(todos_data)
            logger.info(f"Bulk updated {updated_count} todos to status {new_status}")
        
        return updated_count