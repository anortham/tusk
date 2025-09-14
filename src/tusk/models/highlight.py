"""Highlight model for important moments and decisions."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class HighlightCategory(str, Enum):
    """Categories for highlights to help with organization."""

    DECISION = "decision"
    BREAKTHROUGH = "breakthrough"
    BLOCKER = "blocker"
    COMPLETION = "completion"
    INSIGHT = "insight"
    ERROR = "error"
    REFACTOR = "refactor"
    TASK = "task"
    PLAN_STEP = "plan_step"
    DISCOVERY = "discovery"
    GENERAL = "general"


class HighlightImportance(str, Enum):
    """Importance levels for highlights."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Highlight(BaseModel):
    """A highlight represents an important moment or decision."""

    content: str = Field(description="The highlight content - what happened or was decided")

    category: HighlightCategory = Field(
        default=HighlightCategory.GENERAL, description="Category of the highlight"
    )

    importance: HighlightImportance = Field(
        default=HighlightImportance.MEDIUM, description="How important this highlight is"
    )

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this highlight occurred",
    )

    context: Optional[str] = Field(
        default=None, description="Additional context about the highlight"
    )

    tags: list[str] = Field(default_factory=list, description="Tags for organization and search")

    # Relationships
    related_files: list[str] = Field(
        default_factory=list, description="Files related to this highlight"
    )

    related_task_id: Optional[str] = Field(default=None, description="ID of related task item")

    def __str__(self) -> str:
        return f"[{self.category.value.upper()}] {self.content[:100]}..."

    def to_search_text(self) -> str:
        """Convert highlight to searchable text."""
        parts = [
            self.content,
            self.category.value,
            self.importance.value,
        ]

        if self.context:
            parts.append(self.context)

        parts.extend(self.tags)
        parts.extend(self.related_files)

        return " ".join(parts)
