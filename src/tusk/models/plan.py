"""Plan model for persistent cross-session planning."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from .types import TZAwareDatetime, utc_now


def generate_plan_id() -> str:
    """Generate a unique ID for plans."""
    return str(uuid4())


class PlanStatus(str, Enum):
    """Status of a plan."""

    DRAFT = "draft"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PlanStep(BaseModel):
    """A single step in a plan."""

    id: str = Field(default_factory=lambda: str(uuid4()), description="Step ID")

    description: str = Field(description="What this step involves")

    completed: bool = Field(default=False, description="Whether this step is done")

    notes: Optional[str] = Field(default=None, description="Notes about this step")

    estimated_duration: Optional[str] = Field(
        default=None, description="How long this step should take"
    )

    dependencies: list[str] = Field(
        default_factory=list, description="IDs of steps that must complete before this one"
    )

    completed_at: Optional[TZAwareDatetime] = Field(
        default=None, description="When this step was completed"
    )

    def mark_completed(self) -> None:
        """Mark this step as completed."""
        self.completed = True
        self.completed_at = utc_now()


class Plan(BaseModel):
    """A plan represents a persistent multi-step project or goal."""

    # Identity
    id: str = Field(default_factory=generate_plan_id, description="Unique plan ID")

    workspace_id: str = Field(
        default="", description="ID of the workspace this plan belongs to (deprecated)"
    )

    # Project tracking
    project_id: str = Field(default="", description="ID of the project this plan belongs to")

    project_path: str = Field(default="", description="Full path to the project directory")

    # Core content
    title: str = Field(description="Title of the plan")

    description: str = Field(description="Detailed description of what this plan achieves")

    # Goals and outcomes
    goals: list[str] = Field(
        default_factory=list, description="List of specific goals this plan should achieve"
    )

    success_criteria: list[str] = Field(
        default_factory=list, description="How to know when this plan is successfully completed"
    )

    # Steps and structure
    steps: list[PlanStep] = Field(
        default_factory=list, description="Ordered list of steps to complete this plan"
    )

    # Status and priority
    status: PlanStatus = Field(default=PlanStatus.DRAFT, description="Current plan status")

    priority: str = Field(default="medium", description="Priority level (low/medium/high/urgent)")

    # Organization
    tags: list[str] = Field(default_factory=list, description="Tags for organization")

    category: Optional[str] = Field(
        default=None, description="Category of plan (feature, bugfix, research, etc.)"
    )

    # Relationships
    related_todo_ids: list[str] = Field(
        default_factory=list, description="IDs of todos created from this plan"
    )

    related_checkpoint_ids: list[str] = Field(
        default_factory=list, description="IDs of checkpoints related to this plan"
    )

    # Metadata
    estimated_duration: Optional[str] = Field(
        default=None, description="Estimated total time to complete (e.g., '1w', '3d')"
    )

    notes: Optional[str] = Field(default=None, description="Additional notes about this plan")

    # Timestamps
    created_at: TZAwareDatetime = Field(
        default_factory=utc_now, description="When this plan was created"
    )

    updated_at: Optional[TZAwareDatetime] = Field(
        default=None, description="When this plan was last updated"
    )

    started_at: Optional[TZAwareDatetime] = Field(
        default=None, description="When work on this plan began"
    )

    completed_at: Optional[TZAwareDatetime] = Field(
        default=None, description="When this plan was completed"
    )

    target_completion: Optional[TZAwareDatetime] = Field(
        default=None, description="Target completion date"
    )

    def add_step(self, description: str, **kwargs) -> PlanStep:
        """Add a new step to the plan."""
        step = PlanStep(description=description, **kwargs)
        self.steps.append(step)
        self.updated_at = utc_now()
        return step

    def complete_step(self, step_id: str) -> bool:
        """Mark a step as completed."""
        for step in self.steps:
            if step.id == step_id:
                step.mark_completed()
                self.updated_at = utc_now()
                return True
        return False

    def get_progress(self) -> tuple[int, int]:
        """Get progress as (completed_steps, total_steps)."""
        total = len(self.steps)
        completed = sum(1 for step in self.steps if step.completed)
        return completed, total

    def get_progress_percentage(self) -> float:
        """Get progress as a percentage."""
        completed, total = self.get_progress()
        if total == 0:
            return 0.0
        return (completed / total) * 100

    def is_completed(self) -> bool:
        """Check if all steps are completed."""
        if not self.steps:
            return False
        return all(step.completed for step in self.steps)

    def get_next_steps(self, limit: int = 3) -> list[PlanStep]:
        """Get the next actionable steps (not blocked by dependencies)."""
        next_steps = []
        completed_step_ids = {step.id for step in self.steps if step.completed}

        for step in self.steps:
            if step.completed:
                continue

            # Check if all dependencies are completed
            if all(dep_id in completed_step_ids for dep_id in step.dependencies):
                next_steps.append(step)
                if len(next_steps) >= limit:
                    break

        return next_steps

    def activate(self) -> None:
        """Activate this plan."""
        self.status = PlanStatus.ACTIVE
        if not self.started_at:
            self.started_at = utc_now()
        self.updated_at = utc_now()

    def complete(self) -> None:
        """Mark this plan as completed."""
        self.status = PlanStatus.COMPLETED
        self.completed_at = utc_now()
        self.updated_at = utc_now()

    def to_search_text(self) -> str:
        """Convert plan to searchable text."""
        parts = [
            self.title,
            self.description,
            self.status.value,
            self.priority,
        ]

        parts.extend(self.goals)
        parts.extend(self.success_criteria)
        parts.extend(self.tags)

        if self.category:
            parts.append(self.category)

        if self.notes:
            parts.append(self.notes)

        # Add step descriptions
        for step in self.steps:
            parts.append(step.description)
            if step.notes:
                parts.append(step.notes)

        return " ".join(parts)

    def __str__(self) -> str:
        completed, total = self.get_progress()
        progress = f"({completed}/{total})"
        return f"[{self.status.value.upper()}] {self.title} {progress}"
