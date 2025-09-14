"""Basic functionality tests for Tusk memory system."""

import tempfile
from pathlib import Path
from datetime import datetime

import pytest

from src.tusk.config import TuskConfig
from src.tusk.models import Checkpoint, Task, Plan, Highlight
from src.tusk.models.highlight import HighlightCategory
from src.tusk.models.task import TaskPriority, TaskStatus
from src.tusk.models.plan import PlanStatus
from src.tusk.storage import CheckpointStorage, TaskStorage, PlanStorage


@pytest.fixture
def temp_config():
    """Create a temporary configuration for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config = TuskConfig(
            data_dir=Path(temp_dir) / "data",
            log_dir=Path(temp_dir) / "logs",
        )
        config.ensure_directories()
        yield config


class TestCheckpointStorage:
    """Test checkpoint storage functionality."""

    def test_create_and_load_checkpoint(self, temp_config):
        """Test creating and loading a checkpoint."""
        storage = CheckpointStorage(temp_config)

        # Create checkpoint
        checkpoint = Checkpoint(
            description="Test checkpoint",
            work_context="Working on unit tests",
            active_files=["test_file.py"],
        )

        # Add highlight
        highlight = Highlight(
            content="Implemented basic test structure",
            category=HighlightCategory.COMPLETION,
        )
        checkpoint.add_highlight(highlight)

        # Save checkpoint
        assert storage.save(checkpoint)

        # Load checkpoint
        loaded = storage.load(checkpoint.id)
        assert loaded is not None
        assert loaded.id == checkpoint.id
        assert loaded.description == "Test checkpoint"
        assert loaded.work_context == "Working on unit tests"
        assert len(loaded.active_files) == 1
        assert loaded.active_files[0] == "test_file.py"
        assert len(loaded.highlights) == 1
        assert loaded.highlights[0].content == "Implemented basic test structure"

    def test_list_recent_checkpoints(self, temp_config):
        """Test listing recent checkpoints."""
        storage = CheckpointStorage(temp_config)

        # Create multiple checkpoints
        import time

        checkpoints = []
        for i in range(3):
            checkpoint = Checkpoint(
                description=f"Test checkpoint {i+1}",
            )
            checkpoints.append(checkpoint)
            storage.save(checkpoint)
            # Small delay to ensure unique timestamp-based IDs
            time.sleep(0.001)

        # List recent
        recent = storage.list_recent(limit=2)
        assert len(recent) == 2

        # Should be ordered by created_at, most recent first
        assert recent[0].description == "Test checkpoint 3"
        assert recent[1].description == "Test checkpoint 2"


class TestTaskStorage:
    """Test task storage functionality."""

    def test_create_and_load_task(self, temp_config):
        """Test creating and loading a task."""
        storage = TaskStorage(temp_config)

        # Create task
        task = Task(
            content="Write unit tests",
            active_form="Writing unit tests",
            priority=TaskPriority.HIGH,
            tags=["testing", "python"],
            notes="Focus on storage layer first",
        )

        # Save task
        assert storage.save(task)

        # Load task
        loaded = storage.load(task.id)
        assert loaded is not None
        assert loaded.id == task.id
        assert loaded.content == "Write unit tests"
        assert loaded.priority == TaskPriority.HIGH
        assert "testing" in loaded.tags
        assert loaded.notes == "Focus on storage layer first"

    def test_task_status_transitions(self, temp_config):
        """Test task status transitions."""
        storage = TaskStorage(temp_config)

        # Create task
        task = Task(
            content="Test status transitions",
            active_form="Testing status transitions",
        )

        # Initial status should be pending
        assert task.status == TaskStatus.PENDING
        assert task.started_at is None
        assert task.completed_at is None

        # Mark in progress
        task.mark_in_progress()
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.started_at is not None

        # Mark completed
        task.mark_completed()
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None

        # Save and reload
        storage.save(task)
        loaded = storage.load(task.id)
        assert loaded.status == TaskStatus.COMPLETED
        assert loaded.completed_at is not None

    def test_find_tasks_by_status(self, temp_config):
        """Test finding tasks by status."""
        storage = TaskStorage(temp_config)

        # Create tasks with different statuses
        task1 = Task(content="Pending task", active_form="Working on pending")
        task2 = Task(content="Active task", active_form="Working on active")
        task2.mark_in_progress()
        task3 = Task(content="Done task", active_form="Working on done")
        task3.mark_completed()

        # Save all
        storage.save(task1)
        storage.save(task2)
        storage.save(task3)

        # Find by status
        pending = storage.find_pending()
        in_progress = storage.find_in_progress()
        completed = storage.find_completed()

        assert len(pending) == 1
        assert pending[0].content == "Pending task"

        assert len(in_progress) == 1
        assert in_progress[0].content == "Active task"

        assert len(completed) == 1
        assert completed[0].content == "Done task"


class TestPlanStorage:
    """Test plan storage functionality."""

    def test_create_and_load_plan(self, temp_config):
        """Test creating and loading a plan."""
        storage = PlanStorage(temp_config)

        # Create plan
        plan = Plan(
            title="Test Plan",
            description="A plan for testing the plan storage",
            goals=["Goal 1", "Goal 2"],
            tags=["testing", "storage"],
        )

        # Add steps
        plan.add_step("Step 1: Setup")
        plan.add_step("Step 2: Execute")
        plan.add_step("Step 3: Verify")

        # Save plan
        assert storage.save(plan)

        # Load plan
        loaded = storage.load(plan.id)
        assert loaded is not None
        assert loaded.id == plan.id
        assert loaded.title == "Test Plan"
        assert len(loaded.goals) == 2
        assert len(loaded.steps) == 3
        assert loaded.steps[0].description == "Step 1: Setup"

    def test_plan_progress(self, temp_config):
        """Test plan progress tracking."""
        storage = PlanStorage(temp_config)

        # Create plan with steps
        plan = Plan(
            title="Progress Test Plan",
            description="Testing progress calculation",
        )

        step1 = plan.add_step("First step")
        step2 = plan.add_step("Second step")
        step3 = plan.add_step("Third step")

        # Initially no progress
        completed, total = plan.get_progress()
        assert completed == 0
        assert total == 3
        assert plan.get_progress_percentage() == 0.0

        # Complete first step
        plan.complete_step(step1.id)
        completed, total = plan.get_progress()
        assert completed == 1
        assert total == 3
        assert plan.get_progress_percentage() == pytest.approx(33.33, rel=1e-2)

        # Complete remaining steps
        plan.complete_step(step2.id)
        plan.complete_step(step3.id)

        completed, total = plan.get_progress()
        assert completed == 3
        assert total == 3
        assert plan.get_progress_percentage() == 100.0
        assert plan.is_completed()

    def test_plan_activation(self, temp_config):
        """Test plan activation."""
        storage = PlanStorage(temp_config)

        # Create draft plan
        plan = Plan(
            title="Activation Test Plan",
            description="Testing plan activation",
        )

        assert plan.status == PlanStatus.DRAFT
        assert plan.started_at is None

        # Activate plan
        plan.activate()
        assert plan.status == PlanStatus.ACTIVE
        assert plan.started_at is not None

        # Save and reload
        storage.save(plan)
        loaded = storage.load(plan.id)
        assert loaded.status == PlanStatus.ACTIVE
        assert loaded.started_at is not None


class TestModelValidation:
    """Test Pydantic model validation."""

    def test_checkpoint_validation(self):
        """Test checkpoint model validation."""
        # Valid checkpoint
        checkpoint = Checkpoint(
            workspace_id="",
            description="Valid checkpoint",
        )
        assert checkpoint.workspace_id == ""
        assert checkpoint.description == "Valid checkpoint"
        assert len(checkpoint.highlights) == 0
        assert len(checkpoint.active_files) == 0
        assert len(checkpoint.tags) == 0

        # Test TTL parsing
        checkpoint.set_ttl("3d")
        assert checkpoint.ttl_expiry is not None

        # Test adding highlights
        highlight = Highlight(content="Test highlight")
        checkpoint.add_highlight(highlight)
        assert len(checkpoint.highlights) == 1

    def test_task_validation(self):
        """Test task model validation."""
        # Valid task
        task = Task(
            workspace_id="",
            content="Test task",
            active_form="Testing task",
        )

        assert task.workspace_id == ""
        assert task.content == "Test task"
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.MEDIUM

        # Test display forms
        assert task.get_display_form() == "Test task"  # Pending state

        task.mark_in_progress()
        assert task.get_display_form() == "Testing task"  # In progress state

    def test_plan_validation(self):
        """Test plan model validation."""
        # Valid plan
        plan = Plan(
            workspace_id="",
            title="Test Plan",
            description="Test description",
        )

        assert plan.workspace_id == ""
        assert plan.title == "Test Plan"
        assert plan.status == PlanStatus.DRAFT
        assert len(plan.steps) == 0

        # Test adding steps
        step = plan.add_step("Test step")
        assert len(plan.steps) == 1
        assert plan.steps[0].description == "Test step"
        assert not plan.steps[0].completed
