"""Comprehensive tests for datetime timezone consistency across the system.

These tests expose the datetime timezone issues and ensure they're properly fixed.
"""

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.tusk.config import TuskConfig
from src.tusk.models.checkpoint import Checkpoint
from src.tusk.models.plan import Plan
from src.tusk.models.task import Task
from src.tusk.storage.checkpoint_store import CheckpointStorage
from src.tusk.storage.plan_store import PlanStorage
from src.tusk.storage.task_store import TaskStorage


class TestDatetimeConsistency:
    """Test datetime timezone consistency across models and storage."""

    @pytest.fixture
    def temp_config(self):
        """Create a temporary config for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = TuskConfig(data_dir=Path(temp_dir) / "data", log_dir=Path(temp_dir) / "logs")
            config.ensure_directories()
            yield config

    def test_model_creation_timezone_aware(self):
        """Test that all models create timezone-aware datetimes by default."""
        # Test Checkpoint
        checkpoint = Checkpoint(description="Test checkpoint")
        assert checkpoint.created_at.tzinfo is not None, "Checkpoint.created_at should be timezone-aware"
        assert checkpoint.created_at.tzinfo == UTC, "Should use UTC timezone"

        # Test Todo
        task = Task(content="Test task", active_form="Testing task")
        assert task.created_at.tzinfo is not None, "Todo.created_at should be timezone-aware"
        assert task.created_at.tzinfo == UTC, "Should use UTC timezone"

        # Test Plan
        plan = Plan(title="Test plan", description="Test plan description")
        assert plan.created_at.tzinfo is not None, "Plan.created_at should be timezone-aware"
        assert plan.created_at.tzinfo == UTC, "Should use UTC timezone"

    def test_json_roundtrip_preserves_timezone(self, temp_config):
        """Test that saving and loading preserves timezone information."""
        # Create models with timezone-aware datetimes
        checkpoint = Checkpoint(description="Test checkpoint for roundtrip")

        task = Task(content="Test task", active_form="Testing task")

        plan = Plan(title="Test plan", description="Test plan description")

        # Save and reload via storage
        checkpoint_storage = CheckpointStorage(temp_config)
        task_storage = TaskStorage(temp_config)
        plan_storage = PlanStorage(temp_config)

        assert checkpoint_storage.save(checkpoint), "Should save checkpoint"
        assert task_storage.save(task), "Should save task"
        assert plan_storage.save(plan), "Should save plan"

        # Reload from storage
        loaded_checkpoint = checkpoint_storage.load(checkpoint.id)
        loaded_task = task_storage.load(task.id)
        loaded_plan = plan_storage.load(plan.id)

        assert loaded_checkpoint is not None, "Should load checkpoint"
        assert loaded_task is not None, "Should load task"
        assert loaded_plan is not None, "Should load plan"

        # Check timezone preservation - THIS WILL FAIL with current implementation
        assert loaded_checkpoint.created_at.tzinfo is not None, "Loaded checkpoint should have timezone"
        assert loaded_task.created_at.tzinfo is not None, "Loaded task should have timezone"
        assert loaded_plan.created_at.tzinfo is not None, "Loaded plan should have timezone"

        # Check exact datetime equality
        assert loaded_checkpoint.created_at == checkpoint.created_at, "Datetime should be identical"
        assert loaded_task.created_at == task.created_at, "Datetime should be identical"
        assert loaded_plan.created_at == plan.created_at, "Datetime should be identical"

    def test_sorting_mixed_timezone_datetimes(self, temp_config):
        """Test sorting items with mixed timezone-aware/naive datetimes."""
        checkpoint_storage = CheckpointStorage(temp_config)

        # Create multiple checkpoints with different creation times
        import time

        checkpoints = []
        for i in range(3):
            checkpoint = Checkpoint(description=f"Checkpoint {i}")
            # Manually adjust created_at for testing
            checkpoint.created_at = datetime.now(UTC) + timedelta(minutes=i)
            checkpoints.append(checkpoint)
            checkpoint_storage.save(checkpoint)
            # Small delay to ensure unique timestamp-based IDs
            time.sleep(0.001)

        # Load all and attempt sorting - THIS WILL FAIL if timezone info is lost
        loaded_checkpoints = checkpoint_storage.load_all()

        # This should work without timezone comparison errors
        try:
            sorted_checkpoints = sorted(loaded_checkpoints, key=lambda c: c.created_at, reverse=True)
            assert len(sorted_checkpoints) == 3, "Should have all checkpoints"
        except TypeError as e:
            if "can't compare offset-naive and offset-aware datetimes" in str(e):
                pytest.fail("Timezone comparison error during sorting")
            raise

    def test_date_range_filtering(self, temp_config):
        """Test filtering by date range with mixed timezone datetimes."""
        checkpoint_storage = CheckpointStorage(temp_config)

        # Create checkpoints across different days
        base_time = datetime.now(UTC)
        checkpoints = []

        for i in range(5):
            checkpoint = Checkpoint(description=f"Daily checkpoint {i}")
            checkpoint.created_at = base_time - timedelta(days=i)
            checkpoints.append(checkpoint)
            checkpoint_storage.save(checkpoint)

        # Test date range filtering - THIS WILL FAIL with timezone issues
        start_date = base_time - timedelta(days=2)
        end_date = base_time + timedelta(days=1)

        try:
            filtered_checkpoints = checkpoint_storage.list_by_date_range(start_date, end_date)
            # Should get checkpoints from last 3 days
            assert len(filtered_checkpoints) >= 3, f"Should get at least 3 checkpoints, got {len(filtered_checkpoints)}"
        except TypeError as e:
            if "can't compare offset-naive and offset-aware datetimes" in str(e):
                pytest.fail("Timezone comparison error during date filtering")
            raise

    def test_recall_datetime_filtering(self, temp_config):
        """Test recall functionality datetime filtering logic directly."""
        # This test simulates the actual recall error scenario by testing the filtering logic

        # Create mixed timezone data
        checkpoint_storage = CheckpointStorage(temp_config)
        task_storage = TaskStorage(temp_config)

        # Create test data with different timestamps
        base_time = datetime.now(UTC)

        checkpoint = Checkpoint(description="Test checkpoint")
        task = Task(content="Test task", active_form="Testing")

        # Manually set different creation times to test filtering
        checkpoint.created_at = base_time - timedelta(days=1)
        task.created_at = base_time - timedelta(days=3)

        checkpoint_storage.save(checkpoint)
        task_storage.save(task)

        # Reload to get the serialization/deserialization effect
        loaded_checkpoint = checkpoint_storage.load(checkpoint.id)
        loaded_task = task_storage.load(task.id)

        # Test the filtering logic that fails in recall
        start_date = base_time - timedelta(days=2)

        # This simulates the logic in recall.py lines 177-178, 196-197
        try:
            # Test checkpoint filtering
            created_tz_aware = loaded_checkpoint.created_at.replace(tzinfo=UTC) if loaded_checkpoint.created_at.tzinfo is None else loaded_checkpoint.created_at
            checkpoint_in_range = created_tz_aware >= start_date

            # Test task filtering
            task_created_tz_aware = loaded_task.created_at.replace(tzinfo=UTC) if loaded_task.created_at.tzinfo is None else loaded_task.created_at
            task_in_range = task_created_tz_aware >= start_date

            # Should be able to determine which items are in range
            assert isinstance(checkpoint_in_range, bool), "Should get boolean result for checkpoint"
            assert isinstance(task_in_range, bool), "Should get boolean result for task"

        except TypeError as e:
            if "can't compare offset-naive and offset-aware datetimes" in str(e):
                pytest.fail("Timezone comparison error during filtering - this is the bug we need to fix")
            raise

    def test_cross_model_datetime_comparisons(self, temp_config):
        """Test comparing datetimes between different model types."""
        checkpoint = Checkpoint(description="Test")
        task = Task(content="Test", active_form="Testing")
        plan = Plan(title="Test", description="Test")

        # Save and reload to simulate real usage
        checkpoint_storage = CheckpointStorage(temp_config)
        task_storage = TaskStorage(temp_config)
        plan_storage = PlanStorage(temp_config)

        checkpoint_storage.save(checkpoint)
        task_storage.save(task)
        plan_storage.save(plan)

        loaded_checkpoint = checkpoint_storage.load(checkpoint.id)
        loaded_task = task_storage.load(task.id)
        loaded_plan = plan_storage.load(plan.id)

        # These comparisons should work without timezone errors
        try:
            # Compare checkpoint and task datetimes
            if loaded_checkpoint.created_at < loaded_task.created_at:
                older_item = "checkpoint"
            else:
                older_item = "task"

            # Compare with plan
            if loaded_plan.created_at < loaded_checkpoint.created_at:
                oldest_item = "plan"
            else:
                oldest_item = older_item

            assert oldest_item in ["checkpoint", "task", "plan"], "Should determine oldest item"
        except TypeError as e:
            if "can't compare offset-naive and offset-aware datetimes" in str(e):
                pytest.fail("Timezone comparison error between model types")
            raise

    def test_json_file_timezone_format(self, temp_config):
        """Test that JSON files contain explicit timezone information."""
        checkpoint = Checkpoint(description="Test timezone in JSON")

        checkpoint_storage = CheckpointStorage(temp_config)
        assert checkpoint_storage.save(checkpoint), "Should save checkpoint"

        # Read the raw JSON file
        file_path = checkpoint_storage._get_file_path(checkpoint.id)
        assert file_path.exists(), "JSON file should exist"

        with open(file_path) as f:
            json_data = json.load(f)

        created_at_str = json_data.get("created_at")
        assert created_at_str is not None, "Should have created_at field"

        # Check that timezone info is explicitly stored
        # Current implementation may store "2025-09-12T15:25:44.125495Z" (naive)
        # Should store "2025-09-12T15:25:44.125495+00:00" (aware)
        assert "Z" in created_at_str or "+00:00" in created_at_str, f"JSON should contain explicit timezone info, got: {created_at_str}"

    def test_task_status_transitions_preserve_timezone(self, temp_config):
        """Test that task status changes preserve timezone info."""
        task = Task(content="Test task transitions", active_form="Testing transitions")

        task_storage = TaskStorage(temp_config)
        task_storage.save(task)

        # Transition to in_progress
        task.mark_in_progress()
        assert task.started_at is not None, "Should have started_at"
        assert task.started_at.tzinfo is not None, "started_at should be timezone-aware"

        task_storage.save(task)

        # Reload and check timezone preservation
        loaded_task = task_storage.load(task.id)
        assert loaded_task.started_at is not None, "Should have started_at after reload"
        assert loaded_task.started_at.tzinfo is not None, "started_at should remain timezone-aware"

        # Complete the task
        loaded_task.mark_completed()
        assert loaded_task.completed_at is not None, "Should have completed_at"
        assert loaded_task.completed_at.tzinfo is not None, "completed_at should be timezone-aware"

        task_storage.save(loaded_task)

        # Final reload and verification
        final_task = task_storage.load(task.id)
        assert final_task.completed_at is not None, "Should have completed_at after final reload"
        assert final_task.completed_at.tzinfo is not None, "completed_at should remain timezone-aware"

    def test_mixed_timezone_data_sorting_fails(self):
        """Test that demonstrates the actual error with mixed timezone data."""
        # This test uses the actual production data directory to demonstrate the bug
        from src.tusk.config import TuskConfig
        from src.tusk.storage.checkpoint_store import CheckpointStorage

        config = TuskConfig()  # Use real data directory
        storage = CheckpointStorage(config)

        try:
            # Load existing checkpoints that have mixed timezone formats
            checkpoints = storage.load_all()

            if len(checkpoints) == 0:
                pytest.skip("No existing checkpoints found to test mixed timezone issue")

            # Check if we actually have mixed timezone data
            timezone_aware = [c for c in checkpoints if c.created_at.tzinfo is not None]
            timezone_naive = [c for c in checkpoints if c.created_at.tzinfo is None]

            if len(timezone_aware) == 0 or len(timezone_naive) == 0:
                pytest.skip("No mixed timezone data found")

            print(f"Found {len(timezone_aware)} timezone-aware and {len(timezone_naive)} timezone-naive checkpoints")

            # Try to sort them - this should fail with timezone comparison error
            try:
                sorted_checkpoints = sorted(checkpoints, key=lambda c: c.created_at, reverse=True)
                # If we get here, the sort succeeded despite mixed timezones
                print("Sort succeeded - this means the safe_created_at bandaid is working")
                assert len(sorted_checkpoints) == len(checkpoints), "Should have all checkpoints"
            except TypeError as e:
                if "can't compare offset-naive and offset-aware datetimes" in str(e):
                    pytest.fail("EXPECTED: Timezone comparison error during sorting - this demonstrates the bug")
                raise

        except Exception as e:
            print(f"Error during mixed timezone test: {e}")
            raise
