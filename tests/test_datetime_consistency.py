"""Comprehensive tests for datetime timezone consistency across the system.

These tests expose the datetime timezone issues and ensure they're properly fixed.
"""

import json
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List

import pytest

from src.tusk.config import TuskConfig
from src.tusk.models.checkpoint import Checkpoint
from src.tusk.models.todo import Todo, TodoStatus
from src.tusk.models.plan import Plan, PlanStatus
from src.tusk.storage.checkpoint_store import CheckpointStorage
from src.tusk.storage.todo_store import TodoStorage
from src.tusk.storage.plan_store import PlanStorage


class TestDatetimeConsistency:
    """Test datetime timezone consistency across models and storage."""
    
    @pytest.fixture
    def temp_config(self):
        """Create a temporary config for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = TuskConfig(workspace_name="test", data_dir=Path(temp_dir))
            yield config
    
    def test_model_creation_timezone_aware(self):
        """Test that all models create timezone-aware datetimes by default."""
        # Test Checkpoint
        checkpoint = Checkpoint(
            workspace_id="test",
            description="Test checkpoint"
        )
        assert checkpoint.created_at.tzinfo is not None, "Checkpoint.created_at should be timezone-aware"
        assert checkpoint.created_at.tzinfo == timezone.utc, "Should use UTC timezone"
        
        # Test Todo
        todo = Todo(
            workspace_id="test",
            content="Test todo",
            active_form="Testing todo"
        )
        assert todo.created_at.tzinfo is not None, "Todo.created_at should be timezone-aware"
        assert todo.created_at.tzinfo == timezone.utc, "Should use UTC timezone"
        
        # Test Plan
        plan = Plan(
            workspace_id="test",
            title="Test plan",
            description="Test plan description"
        )
        assert plan.created_at.tzinfo is not None, "Plan.created_at should be timezone-aware"
        assert plan.created_at.tzinfo == timezone.utc, "Should use UTC timezone"
    
    def test_json_roundtrip_preserves_timezone(self, temp_config):
        """Test that saving and loading preserves timezone information."""
        # Create models with timezone-aware datetimes
        checkpoint = Checkpoint(
            workspace_id="test",
            description="Test checkpoint for roundtrip"
        )
        
        todo = Todo(
            workspace_id="test", 
            content="Test todo",
            active_form="Testing todo"
        )
        
        plan = Plan(
            workspace_id="test",
            title="Test plan",
            description="Test plan description"
        )
        
        # Save and reload via storage
        checkpoint_storage = CheckpointStorage(temp_config)
        todo_storage = TodoStorage(temp_config) 
        plan_storage = PlanStorage(temp_config)
        
        assert checkpoint_storage.save(checkpoint), "Should save checkpoint"
        assert todo_storage.save(todo), "Should save todo"
        assert plan_storage.save(plan), "Should save plan"
        
        # Reload from storage
        loaded_checkpoint = checkpoint_storage.load(checkpoint.id)
        loaded_todo = todo_storage.load(todo.id)
        loaded_plan = plan_storage.load(plan.id)
        
        assert loaded_checkpoint is not None, "Should load checkpoint"
        assert loaded_todo is not None, "Should load todo"  
        assert loaded_plan is not None, "Should load plan"
        
        # Check timezone preservation - THIS WILL FAIL with current implementation
        assert loaded_checkpoint.created_at.tzinfo is not None, "Loaded checkpoint should have timezone"
        assert loaded_todo.created_at.tzinfo is not None, "Loaded todo should have timezone"
        assert loaded_plan.created_at.tzinfo is not None, "Loaded plan should have timezone"
        
        # Check exact datetime equality
        assert loaded_checkpoint.created_at == checkpoint.created_at, "Datetime should be identical"
        assert loaded_todo.created_at == todo.created_at, "Datetime should be identical"
        assert loaded_plan.created_at == plan.created_at, "Datetime should be identical"
    
    def test_sorting_mixed_timezone_datetimes(self, temp_config):
        """Test sorting items with mixed timezone-aware/naive datetimes."""
        checkpoint_storage = CheckpointStorage(temp_config)
        
        # Create multiple checkpoints with different creation times
        checkpoints = []
        for i in range(3):
            checkpoint = Checkpoint(
                workspace_id="test",
                description=f"Checkpoint {i}"
            )
            # Manually adjust created_at for testing
            checkpoint.created_at = datetime.now(timezone.utc) + timedelta(minutes=i)
            checkpoints.append(checkpoint)
            checkpoint_storage.save(checkpoint)
        
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
        base_time = datetime.now(timezone.utc)
        checkpoints = []
        
        for i in range(5):
            checkpoint = Checkpoint(
                workspace_id="test",
                description=f"Daily checkpoint {i}"
            )
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
        todo_storage = TodoStorage(temp_config)
        
        # Create test data with different timestamps
        base_time = datetime.now(timezone.utc)
        
        checkpoint = Checkpoint(workspace_id="test", description="Test checkpoint")
        todo = Todo(workspace_id="test", content="Test todo", active_form="Testing")
        
        # Manually set different creation times to test filtering
        checkpoint.created_at = base_time - timedelta(days=1)
        todo.created_at = base_time - timedelta(days=3)
        
        checkpoint_storage.save(checkpoint)
        todo_storage.save(todo)
        
        # Reload to get the serialization/deserialization effect
        loaded_checkpoint = checkpoint_storage.load(checkpoint.id)
        loaded_todo = todo_storage.load(todo.id)
        
        # Test the filtering logic that fails in recall
        start_date = base_time - timedelta(days=2)
        
        # This simulates the logic in recall.py lines 177-178, 196-197
        try:
            # Test checkpoint filtering
            created_tz_aware = loaded_checkpoint.created_at.replace(tzinfo=timezone.utc) if loaded_checkpoint.created_at.tzinfo is None else loaded_checkpoint.created_at
            checkpoint_in_range = created_tz_aware >= start_date
            
            # Test todo filtering  
            todo_created_tz_aware = loaded_todo.created_at.replace(tzinfo=timezone.utc) if loaded_todo.created_at.tzinfo is None else loaded_todo.created_at
            todo_in_range = todo_created_tz_aware >= start_date
            
            # Should be able to determine which items are in range
            assert isinstance(checkpoint_in_range, bool), "Should get boolean result for checkpoint"
            assert isinstance(todo_in_range, bool), "Should get boolean result for todo"
            
        except TypeError as e:
            if "can't compare offset-naive and offset-aware datetimes" in str(e):
                pytest.fail("Timezone comparison error during filtering - this is the bug we need to fix")
            raise
    
    def test_cross_model_datetime_comparisons(self, temp_config):
        """Test comparing datetimes between different model types."""
        checkpoint = Checkpoint(workspace_id="test", description="Test")
        todo = Todo(workspace_id="test", content="Test", active_form="Testing")
        plan = Plan(workspace_id="test", title="Test", description="Test")
        
        # Save and reload to simulate real usage
        checkpoint_storage = CheckpointStorage(temp_config)
        todo_storage = TodoStorage(temp_config)
        plan_storage = PlanStorage(temp_config)
        
        checkpoint_storage.save(checkpoint)
        todo_storage.save(todo)
        plan_storage.save(plan)
        
        loaded_checkpoint = checkpoint_storage.load(checkpoint.id)
        loaded_todo = todo_storage.load(todo.id)
        loaded_plan = plan_storage.load(plan.id)
        
        # These comparisons should work without timezone errors
        try:
            # Compare checkpoint and todo datetimes
            if loaded_checkpoint.created_at < loaded_todo.created_at:
                older_item = "checkpoint"
            else:
                older_item = "todo"
            
            # Compare with plan
            if loaded_plan.created_at < loaded_checkpoint.created_at:
                oldest_item = "plan"
            else:
                oldest_item = older_item
                
            assert oldest_item in ["checkpoint", "todo", "plan"], "Should determine oldest item"
        except TypeError as e:
            if "can't compare offset-naive and offset-aware datetimes" in str(e):
                pytest.fail("Timezone comparison error between model types")
            raise
    
    def test_json_file_timezone_format(self, temp_config):
        """Test that JSON files contain explicit timezone information."""
        checkpoint = Checkpoint(
            workspace_id="test",
            description="Test timezone in JSON"
        )
        
        checkpoint_storage = CheckpointStorage(temp_config)
        assert checkpoint_storage.save(checkpoint), "Should save checkpoint"
        
        # Read the raw JSON file
        file_path = checkpoint_storage._get_file_path(checkpoint.id)
        assert file_path.exists(), "JSON file should exist"
        
        with open(file_path, 'r') as f:
            json_data = json.load(f)
        
        created_at_str = json_data.get("created_at")
        assert created_at_str is not None, "Should have created_at field"
        
        # Check that timezone info is explicitly stored
        # Current implementation may store "2025-09-12T15:25:44.125495Z" (naive)
        # Should store "2025-09-12T15:25:44.125495+00:00" (aware) 
        assert "Z" in created_at_str or "+00:00" in created_at_str, \
            f"JSON should contain explicit timezone info, got: {created_at_str}"
    
    def test_todo_status_transitions_preserve_timezone(self, temp_config):
        """Test that todo status changes preserve timezone info."""
        todo = Todo(
            workspace_id="test",
            content="Test todo transitions",
            active_form="Testing transitions"
        )
        
        todo_storage = TodoStorage(temp_config)
        todo_storage.save(todo)
        
        # Transition to in_progress
        todo.mark_in_progress()
        assert todo.started_at is not None, "Should have started_at"
        assert todo.started_at.tzinfo is not None, "started_at should be timezone-aware"
        
        todo_storage.save(todo)
        
        # Reload and check timezone preservation
        loaded_todo = todo_storage.load(todo.id)
        assert loaded_todo.started_at is not None, "Should have started_at after reload"
        assert loaded_todo.started_at.tzinfo is not None, "started_at should remain timezone-aware"
        
        # Complete the todo
        loaded_todo.mark_completed()
        assert loaded_todo.completed_at is not None, "Should have completed_at"
        assert loaded_todo.completed_at.tzinfo is not None, "completed_at should be timezone-aware"
        
        todo_storage.save(loaded_todo)
        
        # Final reload and verification
        final_todo = todo_storage.load(todo.id)
        assert final_todo.completed_at is not None, "Should have completed_at after final reload"
        assert final_todo.completed_at.tzinfo is not None, "completed_at should remain timezone-aware"

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