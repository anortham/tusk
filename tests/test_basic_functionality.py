"""Basic functionality tests for Tusk memory system."""

import tempfile
from pathlib import Path
from datetime import datetime

import pytest

from src.tusk.config import TuskConfig
from src.tusk.models import Checkpoint, Todo, Plan, Highlight
from src.tusk.models.highlight import HighlightCategory
from src.tusk.models.todo import TodoPriority, TodoStatus
from src.tusk.models.plan import PlanStatus
from src.tusk.storage import CheckpointStorage, TodoStorage, PlanStorage


@pytest.fixture
def temp_config():
    """Create a temporary configuration for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config = TuskConfig(
            data_dir=Path(temp_dir) / "data",
            log_dir=Path(temp_dir) / "logs",
            current_workspace="test_workspace",
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
            workspace_id="test_workspace",
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
        checkpoints = []
        for i in range(3):
            checkpoint = Checkpoint(
                workspace_id="test_workspace",
                description=f"Test checkpoint {i+1}",
            )
            checkpoints.append(checkpoint)
            storage.save(checkpoint)
        
        # List recent
        recent = storage.list_recent(limit=2)
        assert len(recent) == 2
        
        # Should be ordered by created_at, most recent first
        assert recent[0].description == "Test checkpoint 3"
        assert recent[1].description == "Test checkpoint 2"


class TestTodoStorage:
    """Test todo storage functionality."""
    
    def test_create_and_load_todo(self, temp_config):
        """Test creating and loading a todo."""
        storage = TodoStorage(temp_config)
        
        # Create todo
        todo = Todo(
            workspace_id="test_workspace",
            content="Write unit tests",
            active_form="Writing unit tests",
            priority=TodoPriority.HIGH,
            tags=["testing", "python"],
            notes="Focus on storage layer first",
        )
        
        # Save todo
        assert storage.save(todo)
        
        # Load todo
        loaded = storage.load(todo.id)
        assert loaded is not None
        assert loaded.id == todo.id
        assert loaded.content == "Write unit tests"
        assert loaded.priority == TodoPriority.HIGH
        assert "testing" in loaded.tags
        assert loaded.notes == "Focus on storage layer first"
    
    def test_todo_status_transitions(self, temp_config):
        """Test todo status transitions."""
        storage = TodoStorage(temp_config)
        
        # Create todo
        todo = Todo(
            workspace_id="test_workspace",
            content="Test status transitions",
            active_form="Testing status transitions",
        )
        
        # Initial status should be pending
        assert todo.status == TodoStatus.PENDING
        assert todo.started_at is None
        assert todo.completed_at is None
        
        # Mark in progress
        todo.mark_in_progress()
        assert todo.status == TodoStatus.IN_PROGRESS
        assert todo.started_at is not None
        
        # Mark completed
        todo.mark_completed()
        assert todo.status == TodoStatus.COMPLETED
        assert todo.completed_at is not None
        
        # Save and reload
        storage.save(todo)
        loaded = storage.load(todo.id)
        assert loaded.status == TodoStatus.COMPLETED
        assert loaded.completed_at is not None
    
    def test_find_todos_by_status(self, temp_config):
        """Test finding todos by status."""
        storage = TodoStorage(temp_config)
        
        # Create todos with different statuses
        todo1 = Todo(workspace_id="test_workspace", content="Pending task", active_form="Working on pending")
        todo2 = Todo(workspace_id="test_workspace", content="Active task", active_form="Working on active")
        todo2.mark_in_progress()
        todo3 = Todo(workspace_id="test_workspace", content="Done task", active_form="Working on done")
        todo3.mark_completed()
        
        # Save all
        storage.save(todo1)
        storage.save(todo2)
        storage.save(todo3)
        
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
            workspace_id="test_workspace",
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
            workspace_id="test_workspace",
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
            workspace_id="test_workspace",
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
            workspace_id="test",
            description="Valid checkpoint",
        )
        assert checkpoint.workspace_id == "test"
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
    
    def test_todo_validation(self):
        """Test todo model validation."""
        # Valid todo
        todo = Todo(
            workspace_id="test",
            content="Test todo",
            active_form="Testing todo",
        )
        
        assert todo.workspace_id == "test"
        assert todo.content == "Test todo"
        assert todo.status == TodoStatus.PENDING
        assert todo.priority == TodoPriority.MEDIUM
        
        # Test display forms
        assert todo.get_display_form() == "Test todo"  # Pending state
        
        todo.mark_in_progress()
        assert todo.get_display_form() == "Testing todo"  # In progress state
    
    def test_plan_validation(self):
        """Test plan model validation."""
        # Valid plan
        plan = Plan(
            workspace_id="test",
            title="Test Plan", 
            description="Test description",
        )
        
        assert plan.workspace_id == "test"
        assert plan.title == "Test Plan"
        assert plan.status == PlanStatus.DRAFT
        assert len(plan.steps) == 0
        
        # Test adding steps
        step = plan.add_step("Test step")
        assert len(plan.steps) == 1
        assert plan.steps[0].description == "Test step"
        assert not plan.steps[0].completed