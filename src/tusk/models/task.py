"""Task model for cross-session task management."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from .types import TZAwareDatetime, utc_now


def generate_task_id() -> str:
    """Generate a unique ID for tasks."""
    return str(uuid4())


class TaskStatus(str, Enum):
    """Status of a task item."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress" 
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class TaskPriority(str, Enum):
    """Priority levels for tasks."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Task(BaseModel):
    """A task item that persists across sessions."""
    
    # Identity
    id: str = Field(default_factory=generate_task_id, description="Unique task ID")
    
    workspace_id: str = Field(default="", description="ID of the workspace this task belongs to (deprecated)")
    
    # Project tracking
    project_id: str = Field(
        default="",
        description="ID of the project this task belongs to"
    )
    
    project_path: str = Field(
        default="",
        description="Full path to the project directory"
    )
    
    # Content
    content: str = Field(description="What needs to be done")
    
    active_form: str = Field(
        description="Present continuous form for when this task is in progress (e.g., 'Running tests')"
    )
    
    # Status and priority
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Current status")
    
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="Priority level")
    
    # Organization
    tags: list[str] = Field(default_factory=list, description="Tags for organization")
    
    # Relationships
    checkpoint_id: Optional[str] = Field(
        default=None,
        description="ID of the checkpoint where this task was created"
    )
    
    parent_task_id: Optional[str] = Field(
        default=None,
        description="ID of parent task if this is a subtask"
    )
    
    plan_id: Optional[str] = Field(
        default=None,
        description="ID of the plan this task belongs to"
    )
    
    # Metadata
    notes: Optional[str] = Field(
        default=None,
        description="Additional notes or context about this task"
    )
    
    estimated_duration: Optional[str] = Field(
        default=None,
        description="Estimated time to complete (e.g., '30m', '2h', '1d')"
    )
    
    # Timestamps
    created_at: TZAwareDatetime = Field(
        default_factory=utc_now,
        description="When this task was created"
    )
    
    updated_at: Optional[TZAwareDatetime] = Field(
        default=None,
        description="When this task was last updated"
    )
    
    started_at: Optional[TZAwareDatetime] = Field(
        default=None,
        description="When work on this task was started"
    )
    
    completed_at: Optional[TZAwareDatetime] = Field(
        default=None,
        description="When this task was completed"
    )
    
    due_date: Optional[TZAwareDatetime] = Field(
        default=None,
        description="When this task should be completed by"
    )
    
    def mark_in_progress(self) -> None:
        """Mark this task as in progress."""
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = utc_now()
        self.updated_at = utc_now()
    
    def mark_completed(self) -> None:
        """Mark this task as completed."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = utc_now()
        self.updated_at = utc_now()
    
    def mark_blocked(self, reason: str = "") -> None:
        """Mark this task as blocked."""
        self.status = TaskStatus.BLOCKED
        if reason and self.notes:
            self.notes += f"\nBlocked: {reason}"
        elif reason:
            self.notes = f"Blocked: {reason}"
        self.updated_at = utc_now()
    
    def add_note(self, note: str) -> None:
        """Add a note to this task."""
        if self.notes:
            self.notes += f"\n{note}"
        else:
            self.notes = note
        self.updated_at = utc_now()
    
    def is_overdue(self) -> bool:
        """Check if this task is overdue."""
        if not self.due_date:
            return False
        return utc_now() > self.due_date and self.status != TaskStatus.COMPLETED
    
    def get_display_form(self) -> str:
        """Get the appropriate form based on status."""
        if self.status == TaskStatus.IN_PROGRESS:
            return self.active_form
        return self.content
    
    def to_search_text(self) -> str:
        """Convert task to searchable text."""
        parts = [
            self.content,
            self.active_form,
            self.status.value,
            self.priority.value,
        ]
        
        parts.extend(self.tags)
        
        if self.notes:
            parts.append(self.notes)
        
        return " ".join(parts)
    
    def __str__(self) -> str:
        status_icon = {
            TaskStatus.PENDING: "⏳",
            TaskStatus.IN_PROGRESS: "🔄", 
            TaskStatus.COMPLETED: "✅",
            TaskStatus.CANCELLED: "❌",
            TaskStatus.BLOCKED: "🚫",
        }
        
        icon = status_icon.get(self.status, "❓")
        priority_marker = "!" * (list(TaskPriority).index(self.priority) + 1)
        
        return f"{icon} {priority_marker} {self.get_display_form()}"