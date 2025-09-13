"""Todo model for cross-session task management."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from .types import TZAwareDatetime, utc_now


def generate_todo_id() -> str:
    """Generate a unique ID for todos."""
    return str(uuid4())


class TodoStatus(str, Enum):
    """Status of a todo item."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress" 
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class TodoPriority(str, Enum):
    """Priority levels for todos."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Todo(BaseModel):
    """A todo item that persists across sessions."""
    
    # Identity
    id: str = Field(default_factory=generate_todo_id, description="Unique todo ID")
    
    workspace_id: str = Field(default="", description="ID of the workspace this todo belongs to (deprecated)")
    
    # Project tracking
    project_id: str = Field(
        default="",
        description="ID of the project this todo belongs to"
    )
    
    project_path: str = Field(
        default="",
        description="Full path to the project directory"
    )
    
    # Content
    content: str = Field(description="What needs to be done")
    
    active_form: str = Field(
        description="Present continuous form for when this todo is in progress (e.g., 'Running tests')"
    )
    
    # Status and priority
    status: TodoStatus = Field(default=TodoStatus.PENDING, description="Current status")
    
    priority: TodoPriority = Field(default=TodoPriority.MEDIUM, description="Priority level")
    
    # Organization
    tags: list[str] = Field(default_factory=list, description="Tags for organization")
    
    # Relationships
    checkpoint_id: Optional[str] = Field(
        default=None,
        description="ID of the checkpoint where this todo was created"
    )
    
    parent_todo_id: Optional[str] = Field(
        default=None,
        description="ID of parent todo if this is a subtask"
    )
    
    plan_id: Optional[str] = Field(
        default=None,
        description="ID of the plan this todo belongs to"
    )
    
    # Metadata
    notes: Optional[str] = Field(
        default=None,
        description="Additional notes or context about this todo"
    )
    
    estimated_duration: Optional[str] = Field(
        default=None,
        description="Estimated time to complete (e.g., '30m', '2h', '1d')"
    )
    
    # Timestamps
    created_at: TZAwareDatetime = Field(
        default_factory=utc_now,
        description="When this todo was created"
    )
    
    updated_at: Optional[TZAwareDatetime] = Field(
        default=None,
        description="When this todo was last updated"
    )
    
    started_at: Optional[TZAwareDatetime] = Field(
        default=None,
        description="When work on this todo was started"
    )
    
    completed_at: Optional[TZAwareDatetime] = Field(
        default=None,
        description="When this todo was completed"
    )
    
    due_date: Optional[TZAwareDatetime] = Field(
        default=None,
        description="When this todo should be completed by"
    )
    
    def mark_in_progress(self) -> None:
        """Mark this todo as in progress."""
        self.status = TodoStatus.IN_PROGRESS
        self.started_at = utc_now()
        self.updated_at = utc_now()
    
    def mark_completed(self) -> None:
        """Mark this todo as completed."""
        self.status = TodoStatus.COMPLETED
        self.completed_at = utc_now()
        self.updated_at = utc_now()
    
    def mark_blocked(self, reason: str = "") -> None:
        """Mark this todo as blocked."""
        self.status = TodoStatus.BLOCKED
        if reason and self.notes:
            self.notes += f"\nBlocked: {reason}"
        elif reason:
            self.notes = f"Blocked: {reason}"
        self.updated_at = utc_now()
    
    def add_note(self, note: str) -> None:
        """Add a note to this todo."""
        if self.notes:
            self.notes += f"\n{note}"
        else:
            self.notes = note
        self.updated_at = utc_now()
    
    def is_overdue(self) -> bool:
        """Check if this todo is overdue."""
        if not self.due_date:
            return False
        return utc_now() > self.due_date and self.status != TodoStatus.COMPLETED
    
    def get_display_form(self) -> str:
        """Get the appropriate form based on status."""
        if self.status == TodoStatus.IN_PROGRESS:
            return self.active_form
        return self.content
    
    def to_search_text(self) -> str:
        """Convert todo to searchable text."""
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
            TodoStatus.PENDING: "⏳",
            TodoStatus.IN_PROGRESS: "🔄", 
            TodoStatus.COMPLETED: "✅",
            TodoStatus.CANCELLED: "❌",
            TodoStatus.BLOCKED: "🚫",
        }
        
        icon = status_icon.get(self.status, "❓")
        priority_marker = "!" * (list(TodoPriority).index(self.priority) + 1)
        
        return f"{icon} {priority_marker} {self.get_display_form()}"