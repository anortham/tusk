"""Storage for task data in a single JSON file per workspace."""

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
        tasks_dir = self.data_dir / "tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)

    def _get_tasks_file(self) -> Path:
        """Get the tasks file path."""
        return self.data_dir / "tasks" / "tasks.json"

    def _load_tasks_file(self) -> Dict[str, Dict]:
        """Load all tasks from the JSON file."""
        tasks_file = self._get_tasks_file()

        if not tasks_file.exists():
            return {}

        try:
            with open(tasks_file, "r", encoding="utf-8") as f:
                portalocker.lock(f, portalocker.LOCK_SH)
                try:
                    return json.load(f)
                finally:
                    portalocker.unlock(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error reading tasks file: {e}")
            return {}

    def _save_tasks_file(self, tasks_data: Dict[str, Dict]) -> bool:
        """Save all tasks to the JSON file."""
        tasks_file = self._get_tasks_file()

        try:
            with open(tasks_file, "w", encoding="utf-8") as f:
                portalocker.lock(f, portalocker.LOCK_EX)
                try:
                    json.dump(
                        tasks_data, f, indent=2, ensure_ascii=False, default=self._json_serializer
                    )
                finally:
                    portalocker.unlock(f)
            return True
        except IOError as e:
            logger.error(f"Error writing tasks file: {e}")
            return False

    def _json_serializer(self, obj):
        """Custom JSON serializer for datetime objects."""
        from datetime import datetime

        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    def load(self, task_id: str) -> Optional[Task]:
        """Load a task by ID."""
        tasks_data = self._load_tasks_file()

        if task_id not in tasks_data:
            return None

        try:
            return Task.model_validate(tasks_data[task_id])
        except Exception as e:
            logger.error(f"Error deserializing task {task_id}: {e}")
            return None

    def save(self, task: Task) -> bool:
        """Save a task."""
        tasks_data = self._load_tasks_file()

        try:
            tasks_data[task.id] = task.model_dump(mode="json")
            success = self._save_tasks_file(tasks_data)

            if success:
                logger.debug(f"Saved task {task.id}")
            else:
                logger.error(f"Failed to save task {task.id}")

            return success
        except Exception as e:
            logger.error(f"Error saving task: {e}")
            return False

    def delete(self, task_id: str) -> bool:
        """Delete a task by ID."""
        tasks_data = self._load_tasks_file()

        if task_id not in tasks_data:
            return True  # Already deleted

        try:
            del tasks_data[task_id]
            success = self._save_tasks_file(tasks_data)

            if success:
                logger.debug(f"Deleted task {task_id}")
            else:
                logger.error(f"Failed to delete task {task_id}")

            return success
        except Exception as e:
            logger.error(f"Error deleting task {task_id}: {e}")
            return False

    def exists(self, task_id: str) -> bool:
        """Check if a task exists."""
        tasks_data = self._load_tasks_file()
        return task_id in tasks_data

    def load_all(self) -> List[Task]:
        """Load all tasks."""
        tasks_data = self._load_tasks_file()
        tasks = []

        for task_id, task_data in tasks_data.items():
            try:
                task = Task.model_validate(task_data)
                tasks.append(task)
            except Exception as e:
                logger.error(f"Error deserializing task {task_id}: {e}")

        return tasks

    def list_ids(self) -> List[str]:
        """List all task IDs."""
        tasks_data = self._load_tasks_file()
        return sorted(tasks_data.keys())

    def count(self) -> int:
        """Count the number of tasks."""
        return len(self.list_ids())

    def find_by_status(self, status: TaskStatus) -> List[Task]:
        """Find tasks by status."""
        all_tasks = self.load_all()
        return [task for task in all_tasks if task.status == status]

    def find_pending(self) -> List[Task]:
        """Find all pending tasks."""
        return self.find_by_status(TaskStatus.PENDING)

    def find_in_progress(self) -> List[Task]:
        """Find all in-progress tasks."""
        return self.find_by_status(TaskStatus.IN_PROGRESS)

    def find_completed(self) -> List[Task]:
        """Find all completed tasks."""
        return self.find_by_status(TaskStatus.COMPLETED)

    def find_by_checkpoint(self, checkpoint_id: str) -> List[Task]:
        """Find tasks linked to a specific checkpoint."""
        all_tasks = self.load_all()
        return [task for task in all_tasks if task.checkpoint_id == checkpoint_id]

    def find_by_plan(self, plan_id: str) -> List[Task]:
        """Find tasks linked to a specific plan."""
        all_tasks = self.load_all()
        return [task for task in all_tasks if task.plan_id == plan_id]

    def find_by_tags(self, tags: List[str]) -> List[Task]:
        """Find tasks that have any of the specified tags."""
        all_tasks = self.load_all()
        matching_tasks = []

        for task in all_tasks:
            if any(tag in task.tags for tag in tags):
                matching_tasks.append(task)

        return matching_tasks

    def find_overdue(self) -> List[Task]:
        """Find tasks that are overdue."""
        all_tasks = self.load_all()
        return [task for task in all_tasks if task.is_overdue()]

    def get_active_tasks(self) -> List[Task]:
        """Get tasks that are pending or in progress."""
        all_tasks = self.load_all()
        return [
            task
            for task in all_tasks
            if task.status in [TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
        ]

    def get_summary_stats(self) -> Dict[str, int]:
        """Get summary statistics about tasks."""
        all_tasks = self.load_all()

        stats = {
            "total": len(all_tasks),
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "blocked": 0,
            "cancelled": 0,
            "overdue": 0,
        }

        for task in all_tasks:
            stats[task.status.value] = stats.get(task.status.value, 0) + 1
            if task.is_overdue():
                stats["overdue"] += 1

        return stats

    def bulk_update_status(self, task_ids: List[str], new_status: TaskStatus) -> int:
        """Update status for multiple tasks. Returns count of updated tasks."""
        updated_count = 0
        tasks_data = self._load_tasks_file()

        for task_id in task_ids:
            if task_id in tasks_data:
                try:
                    task = Task.model_validate(tasks_data[task_id])

                    # Update status using the appropriate method
                    if new_status == TaskStatus.IN_PROGRESS:
                        task.mark_in_progress()
                    elif new_status == TaskStatus.COMPLETED:
                        task.mark_completed()
                    elif new_status == TaskStatus.BLOCKED:
                        task.mark_blocked()
                    else:
                        task.status = new_status
                        task.updated_at = datetime.now(timezone.utc)

                    tasks_data[task_id] = task.model_dump(mode="json")
                    updated_count += 1
                except Exception as e:
                    logger.error(f"Error updating task {task_id}: {e}")

        if updated_count > 0:
            self._save_tasks_file(tasks_data)
            logger.info(f"Bulk updated {updated_count} tasks to status {new_status}")

        return updated_count
