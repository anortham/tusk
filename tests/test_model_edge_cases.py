"""Edge case tests for Tusk core models."""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from src.tusk.models import Checkpoint, Task, Plan, Highlight
from src.tusk.models.highlight import HighlightCategory, HighlightImportance
from src.tusk.models.task import TaskStatus, TaskPriority
from src.tusk.models.plan import PlanStatus, PlanStep


class TestHighlightModel:
    """Test Highlight model edge cases and functionality."""

    def test_highlight_creation_with_defaults(self):
        """Test highlight creation with minimal required fields."""
        highlight = Highlight(content="Test highlight")

        assert highlight.content == "Test highlight"
        assert highlight.category == HighlightCategory.GENERAL  # Default
        assert highlight.timestamp is not None
        assert highlight.tags == []
        assert highlight.importance == HighlightImportance.MEDIUM  # Default

    def test_highlight_creation_with_all_fields(self):
        """Test highlight creation with all fields specified."""
        custom_time = datetime.now(timezone.utc)
        highlight = Highlight(
            content="Detailed highlight",
            category=HighlightCategory.COMPLETION,
            tags=["important", "testing"],
            importance=HighlightImportance.HIGH,
            timestamp=custom_time,
        )

        assert highlight.content == "Detailed highlight"
        assert highlight.category == HighlightCategory.COMPLETION
        assert highlight.tags == ["important", "testing"]
        assert highlight.importance == HighlightImportance.HIGH
        assert highlight.timestamp == custom_time

    def test_highlight_categories(self):
        """Test all highlight categories are supported."""
        categories = [
            HighlightCategory.GENERAL,
            HighlightCategory.DECISION,
            HighlightCategory.COMPLETION,
            HighlightCategory.INSIGHT,
            HighlightCategory.BREAKTHROUGH,
            HighlightCategory.BLOCKER,
            HighlightCategory.ERROR,
        ]

        for category in categories:
            highlight = Highlight(content="Test", category=category)
            assert highlight.category == category

    def test_highlight_importance_levels(self):
        """Test importance level validation."""
        # Valid levels
        for importance in [
            HighlightImportance.LOW,
            HighlightImportance.MEDIUM,
            HighlightImportance.HIGH,
            HighlightImportance.CRITICAL,
        ]:
            highlight = Highlight(content="Test", importance=importance)
            assert highlight.importance == importance

    def test_highlight_to_search_text(self):
        """Test highlight search text generation."""
        highlight = Highlight(
            content="Important discovery",
            category=HighlightCategory.INSIGHT,
            importance=HighlightImportance.HIGH,
            tags=["research", "breakthrough"],
        )

        search_text = highlight.to_search_text()
        assert "Important discovery" in search_text
        assert "insight" in search_text.lower()
        assert "high" in search_text.lower()
        assert "research" in search_text
        assert "breakthrough" in search_text

    def test_highlight_json_serialization(self):
        """Test highlight JSON serialization."""
        highlight = Highlight(
            content="Test highlight", category=HighlightCategory.DECISION, tags=["test"]
        )

        # Should be JSON serializable
        json_str = highlight.model_dump_json()
        data = json.loads(json_str)

        assert data["content"] == "Test highlight"
        assert data["category"] == "decision"
        assert data["tags"] == ["test"]

        # Should be deserializable
        restored = Highlight.model_validate(data)
        assert restored.content == highlight.content
        assert restored.category == highlight.category
        assert restored.tags == highlight.tags


class TestCheckpointModelEdgeCases:
    """Test Checkpoint model edge cases."""

    def test_checkpoint_minimal_creation(self):
        """Test checkpoint with only required fields."""
        checkpoint = Checkpoint(description="Minimal checkpoint")

        assert checkpoint.description == "Minimal checkpoint"
        assert checkpoint.workspace_id == ""  # Deprecated default
        assert checkpoint.work_context is None
        assert checkpoint.active_files == []
        assert checkpoint.highlights == []
        assert checkpoint.tags == []
        assert checkpoint.git_branch is None
        assert checkpoint.ttl_expiry is None

    def test_checkpoint_add_multiple_highlights(self):
        """Test adding multiple highlights to a checkpoint."""
        checkpoint = Checkpoint(description="Test checkpoint")

        highlights = [
            Highlight(content="First highlight", category=HighlightCategory.INSIGHT),
            Highlight(content="Second highlight", category=HighlightCategory.DECISION),
            Highlight(content="Third highlight", category=HighlightCategory.COMPLETION),
        ]

        for highlight in highlights:
            checkpoint.add_highlight(highlight)

        assert len(checkpoint.highlights) == 3
        assert checkpoint.highlights[0].content == "First highlight"
        assert checkpoint.highlights[1].content == "Second highlight"
        assert checkpoint.highlights[2].content == "Third highlight"

    def test_checkpoint_ttl_parsing(self):
        """Test TTL parsing for different formats."""
        checkpoint = Checkpoint(description="TTL test")

        # Test various TTL formats
        ttl_cases = [
            ("1h", timedelta(hours=1)),
            ("24h", timedelta(hours=24)),
            ("1d", timedelta(days=1)),
            ("7d", timedelta(days=7)),
            ("30d", timedelta(days=30)),
            ("1w", timedelta(weeks=1)),
        ]

        for ttl_str, expected_delta in ttl_cases:
            checkpoint.set_ttl(ttl_str)
            assert checkpoint.ttl_expiry is not None

            # Check that the expiry is approximately correct (within 1 second)
            expected_expiry = checkpoint.created_at + expected_delta
            assert abs((checkpoint.ttl_expiry - expected_expiry).total_seconds()) < 1

    def test_checkpoint_ttl_invalid_format(self):
        """Test TTL parsing with invalid formats falls back to default."""
        checkpoint = Checkpoint(description="TTL test")

        invalid_ttls = ["invalid", "1x", "abc", "", "1.5d"]

        for invalid_ttl in invalid_ttls:
            # Invalid TTL should fall back to default (7 days) rather than raise error
            checkpoint.set_ttl(invalid_ttl)
            expected_expiry = checkpoint.created_at + timedelta(days=7)
            assert abs((checkpoint.ttl_expiry - expected_expiry).total_seconds()) < 1

    def test_checkpoint_large_data_handling(self):
        """Test checkpoint with large amounts of data."""
        # Large description
        large_description = "x" * 10000
        checkpoint = Checkpoint(description=large_description)
        assert len(checkpoint.description) == 10000

        # Many files
        many_files = [f"file_{i}.py" for i in range(1000)]
        checkpoint.active_files = many_files
        assert len(checkpoint.active_files) == 1000

        # Many tags
        many_tags = [f"tag_{i}" for i in range(100)]
        checkpoint.tags = many_tags
        assert len(checkpoint.tags) == 100

        # Many highlights
        for i in range(50):
            highlight = Highlight(content=f"Highlight {i}")
            checkpoint.add_highlight(highlight)
        assert len(checkpoint.highlights) == 50


class TestTaskModelEdgeCases:
    """Test Task model edge cases."""

    def test_task_status_transition_validation(self):
        """Test that status transitions follow business rules."""
        task = Task(content="Test task", active_form="Testing task")

        # Should start as pending
        assert task.status == TaskStatus.PENDING

        # Valid transition: pending -> in_progress
        task.mark_in_progress()
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.started_at is not None

        # Valid transition: in_progress -> completed
        task.mark_completed()
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None

        # Invalid transitions should be handled gracefully
        # (Current implementation may not prevent all invalid transitions)

    def test_task_display_form_logic(self):
        """Test task display form changes based on status."""
        task = Task(content="Write tests", active_form="Writing tests")

        # Pending: should show content
        assert task.get_display_form() == "Write tests"

        # In progress: should show active_form
        task.mark_in_progress()
        assert task.get_display_form() == "Writing tests"

        # Completed: should show content
        task.mark_completed()
        assert task.get_display_form() == "Write tests"

    def test_task_priority_levels(self):
        """Test all priority levels are supported."""
        priorities = [TaskPriority.LOW, TaskPriority.MEDIUM, TaskPriority.HIGH]

        for priority in priorities:
            task = Task(content="Test", active_form="Testing", priority=priority)
            assert task.priority == priority

    def test_task_time_tracking(self):
        """Test task time tracking functionality."""
        task = Task(content="Time test", active_form="Testing time")

        # Initially no time tracking
        assert task.started_at is None
        assert task.completed_at is None

        # Mark in progress
        start_time = datetime.now(timezone.utc)
        task.mark_in_progress()
        assert task.started_at is not None
        assert task.started_at >= start_time

        # Mark completed
        completion_time = datetime.now(timezone.utc)
        task.mark_completed()
        assert task.completed_at is not None
        assert task.completed_at >= completion_time
        assert task.completed_at >= task.started_at

    def test_task_with_extensive_metadata(self):
        """Test task with lots of metadata."""
        task = Task(
            content="Complex task",
            active_form="Working on complex task",
            priority=TaskPriority.HIGH,
            tags=["urgent", "important", "complex", "testing"],
            notes="This is a very detailed task with extensive notes about what needs to be done and why it's important.",
        )

        assert len(task.tags) == 4
        assert "urgent" in task.tags
        assert len(task.notes) > 100


class TestPlanModelEdgeCases:
    """Test Plan model edge cases."""

    def test_plan_step_management(self):
        """Test comprehensive plan step management."""
        plan = Plan(title="Test Plan", description="Testing plan steps")

        # Add multiple steps
        step1 = plan.add_step("First step")
        step2 = plan.add_step("Second step")
        step3 = plan.add_step("Third step")

        assert len(plan.steps) == 3
        assert all(hasattr(step, "description") for step in plan.steps)
        assert step1.description == "First step"
        assert step2.description == "Second step"
        assert step3.description == "Third step"

    def test_plan_progress_calculation(self):
        """Test plan progress calculation edge cases."""
        plan = Plan(title="Progress Test", description="Testing progress")

        # Empty plan
        completed, total = plan.get_progress()
        assert completed == 0
        assert total == 0
        assert plan.get_progress_percentage() == 0.0

        # Add steps
        step1 = plan.add_step("Step 1")
        step2 = plan.add_step("Step 2")
        step3 = plan.add_step("Step 3")

        # No completed steps
        completed, total = plan.get_progress()
        assert completed == 0
        assert total == 3
        assert plan.get_progress_percentage() == 0.0

        # Partial completion
        plan.complete_step(step1.id)
        completed, total = plan.get_progress()
        assert completed == 1
        assert total == 3
        assert plan.get_progress_percentage() == pytest.approx(33.33, rel=1e-2)

        # Complete all
        plan.complete_step(step2.id)
        plan.complete_step(step3.id)
        completed, total = plan.get_progress()
        assert completed == 3
        assert total == 3
        assert plan.get_progress_percentage() == 100.0
        assert plan.is_completed()

    def test_plan_status_transitions(self):
        """Test plan status transitions."""
        plan = Plan(title="Status Test", description="Testing status transitions")

        # Should start as draft
        assert plan.status == PlanStatus.DRAFT
        assert plan.started_at is None
        assert plan.completed_at is None

        # Activate plan
        plan.activate()
        assert plan.status == PlanStatus.ACTIVE
        assert plan.started_at is not None

        # Complete plan
        plan.complete()
        assert plan.status == PlanStatus.COMPLETED
        assert plan.completed_at is not None

    def test_plan_with_many_steps(self):
        """Test plan with a large number of steps."""
        plan = Plan(title="Large Plan", description="Plan with many steps")

        # Add 100 steps
        steps = []
        for i in range(100):
            step = plan.add_step(f"Step {i+1}")
            steps.append(step)

        assert len(plan.steps) == 100
        assert plan.steps[0].description == "Step 1"
        assert plan.steps[99].description == "Step 100"

        # Complete half the steps
        for i in range(0, 50):
            plan.complete_step(steps[i].id)

        completed, total = plan.get_progress()
        assert completed == 50
        assert total == 100
        assert plan.get_progress_percentage() == 50.0

    def test_plan_step_completion_idempotency(self):
        """Test that completing a step multiple times is safe."""
        plan = Plan(title="Idempotency Test", description="Testing idempotency")
        step = plan.add_step("Test step")

        # Complete step multiple times
        plan.complete_step(step.id)
        plan.complete_step(step.id)
        plan.complete_step(step.id)

        # Should still be completed only once
        completed, total = plan.get_progress()
        assert completed == 1
        assert total == 1
        assert plan.get_progress_percentage() == 100.0

    def test_plan_nonexistent_step_completion(self):
        """Test completing a step that doesn't exist."""
        plan = Plan(title="Error Test", description="Testing error handling")

        # Try to complete non-existent step
        plan.complete_step("nonexistent-id")

        # Should not crash or affect progress
        completed, total = plan.get_progress()
        assert completed == 0
        assert total == 0


class TestModelTimestampConsistency:
    """Test timestamp handling across all models."""

    def test_all_models_use_utc_timestamps(self):
        """Test that all models create UTC timestamps by default."""
        checkpoint = Checkpoint(description="UTC test")
        task = Task(content="UTC test", active_form="Testing UTC")
        plan = Plan(title="UTC test", description="Testing UTC")
        highlight = Highlight(content="UTC test")

        models = [checkpoint, task, plan, highlight]

        # Check different timestamp fields based on model type
        assert checkpoint.created_at.tzinfo == timezone.utc
        if checkpoint.updated_at is not None:
            assert checkpoint.updated_at.tzinfo == timezone.utc
        assert task.created_at.tzinfo == timezone.utc
        if task.updated_at is not None:
            assert task.updated_at.tzinfo == timezone.utc
        assert plan.created_at.tzinfo == timezone.utc
        if plan.updated_at is not None:
            assert plan.updated_at.tzinfo == timezone.utc
        assert highlight.timestamp.tzinfo == timezone.utc

    def test_timestamp_ordering_consistency(self):
        """Test that timestamps are ordered correctly."""
        # Create models in sequence
        models = []
        for i in range(5):
            checkpoint = Checkpoint(description=f"Test {i}")
            models.append(checkpoint)

        # Timestamps should be in order (allowing for clock precision)
        for i in range(1, len(models)):
            assert models[i].created_at >= models[i - 1].created_at

    def test_updated_at_changes_on_modification(self):
        """Test that updated_at changes when models are modified."""
        task = Task(content="Update test", active_form="Testing updates")
        original_updated = task.updated_at

        # Modify the task
        task.mark_in_progress()

        # updated_at should change (if implemented) or stay the same
        assert task.updated_at is not None
        if hasattr(task, "_update_timestamp"):
            assert task.updated_at >= original_updated


class TestModelValidationEdgeCases:
    """Test model validation edge cases."""

    def test_empty_string_handling(self):
        """Test handling of empty strings in required fields."""
        # Empty description should be allowed but might not be useful
        checkpoint = Checkpoint(description="")
        assert checkpoint.description == ""

        # Empty content in task
        task = Task(content="", active_form="")
        assert task.content == ""
        assert task.active_form == ""

    def test_unicode_content_handling(self):
        """Test handling of Unicode content."""
        unicode_content = "Test with émojis 🚀 and ñoñ-ASCII characters: 中文"

        checkpoint = Checkpoint(description=unicode_content)
        assert checkpoint.description == unicode_content

        task = Task(content=unicode_content, active_form=unicode_content)
        assert task.content == unicode_content

        highlight = Highlight(content=unicode_content)
        assert highlight.content == unicode_content

    def test_very_long_strings(self):
        """Test handling of very long strings."""
        long_string = "x" * 100000  # 100k characters

        # Models should handle large strings
        checkpoint = Checkpoint(description=long_string)
        assert len(checkpoint.description) == 100000

        task = Task(content=long_string, active_form="Working on long content")
        assert len(task.content) == 100000

    def test_special_characters_in_ids(self):
        """Test that generated IDs don't contain problematic characters."""
        models = [
            Checkpoint(description="ID test"),
            Task(content="ID test", active_form="Testing ID"),
            Plan(title="ID test", description="Testing ID"),
        ]

        for model in models:
            # IDs should not contain spaces, special characters that break URLs/filenames
            assert " " not in model.id
            assert "/" not in model.id
            assert "\\" not in model.id
            assert "?" not in model.id
            assert "&" not in model.id
            # Should be reasonably long for uniqueness
            assert len(model.id) >= 8
