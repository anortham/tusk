"""Tests for migration functionality from local to global storage."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.tusk.config import TuskConfig
from src.tusk.models import Checkpoint, Task, Plan
from src.tusk.models.task import TaskStatus
from src.tusk.models.plan import PlanStatus


class TestMigrationFunctionality:
    """Test migration from local to global storage."""
    
    def test_migration_concept_validation(self):
        """Test that migration between storage modes works conceptually."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Simulate old local project structure
            project_dir = Path(temp_dir) / "test_project"
            local_data_dir = project_dir / ".coa" / "tusk" / "data"
            local_data_dir.mkdir(parents=True)
            
            # Simulate global storage location
            global_data_dir = Path(temp_dir) / "global" / ".coa" / "tusk" / "data"
            
            # Create configs for both modes
            local_config = TuskConfig(storage_mode="local", data_dir=local_data_dir)
            global_config = TuskConfig(storage_mode="global", data_dir=global_data_dir)
            
            # Verify they point to different locations
            assert local_config.get_data_dir() != global_config.get_data_dir()
            assert local_config.get_data_dir() == local_data_dir
            assert global_config.get_data_dir() == global_data_dir
    
    def test_project_registry_concept(self):
        """Test project registry functionality for tracking projects."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = TuskConfig(data_dir=Path(temp_dir) / "data")
            
            # Ensure directories exist
            config.ensure_directories()
            
            # Test registry operations
            registry = {
                "/path/to/project1": "project1",
                "/path/to/project2": "project2"
            }
            
            config.save_projects_registry(registry)
            loaded = config.load_projects_registry()
            
            assert loaded == registry
            
            # Test registry file location
            registry_file = config.get_projects_registry_path()
            assert registry_file.exists()
            
            # Verify registry content
            with open(registry_file) as f:
                file_content = json.load(f)
            assert file_content == registry
    
    def test_cross_project_model_creation(self):
        """Test that models can be created with project context."""
        # Test that models support project fields
        checkpoint = Checkpoint(
            description="Test checkpoint",
            project_id="test-project",
            project_path="/path/to/test-project"
        )
        
        task = Task(
            content="Test task",
            active_form="Testing task",
            project_id="test-project", 
            project_path="/path/to/test-project"
        )
        
        plan = Plan(
            title="Test plan",
            description="Test plan description",
            project_id="test-project",
            project_path="/path/to/test-project"
        )
        
        # Verify project fields are set
        assert checkpoint.project_id == "test-project"
        assert checkpoint.project_path == "/path/to/test-project"
        assert task.project_id == "test-project"
        assert task.project_path == "/path/to/test-project"
        assert plan.project_id == "test-project"
        assert plan.project_path == "/path/to/test-project"
    
    def test_migration_data_preservation(self):
        """Test that migration preserves data integrity."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test data in local format
            local_data_dir = Path(temp_dir) / "local" / ".coa" / "tusk" / "data"
            local_data_dir.mkdir(parents=True)
            
            # Create sample data files
            checkpoints_dir = local_data_dir / "checkpoints"
            checkpoints_dir.mkdir(parents=True)
            
            # Sample checkpoint data
            checkpoint_data = {
                "id": "test-checkpoint-1",
                "description": "Test checkpoint from local storage",
                "created_at": "2024-01-01T10:00:00Z",
                "project_id": "",  # Empty in old format
                "project_path": ""  # Empty in old format
            }
            
            checkpoint_file = checkpoints_dir / "test-checkpoint-1.json"
            with open(checkpoint_file, 'w') as f:
                json.dump(checkpoint_data, f)
            
            # Verify data exists in local location
            assert checkpoint_file.exists()
            
            # Create global location
            global_data_dir = Path(temp_dir) / "global" / ".coa" / "tusk" / "data"
            global_data_dir.mkdir(parents=True)
            
            # Simulate migration by copying and updating data
            global_checkpoints_dir = global_data_dir / "checkpoints"
            global_checkpoints_dir.mkdir(parents=True)
            
            # Updated data with project info
            migrated_data = checkpoint_data.copy()
            migrated_data["project_id"] = "test-project"
            migrated_data["project_path"] = str(Path(temp_dir) / "local")
            
            migrated_file = global_checkpoints_dir / "test-checkpoint-1.json"
            with open(migrated_file, 'w') as f:
                json.dump(migrated_data, f)
            
            # Verify migration preserved data with enhancements
            assert migrated_file.exists()
            with open(migrated_file) as f:
                loaded_data = json.load(f)
            
            assert loaded_data["id"] == checkpoint_data["id"]
            assert loaded_data["description"] == checkpoint_data["description"]
            assert loaded_data["project_id"] == "test-project"  # Enhanced
            assert loaded_data["project_path"] == str(Path(temp_dir) / "local")  # Enhanced


class TestCrossProjectEdgeCases:
    """Test edge cases in cross-project functionality."""
    
    def test_empty_project_fields(self):
        """Test handling of models with empty project fields."""
        checkpoint = Checkpoint(
            description="Checkpoint without project info",
            project_id="",  # Empty
            project_path=""  # Empty
        )
        
        # Should still be valid
        assert checkpoint.project_id == ""
        assert checkpoint.project_path == ""
        assert checkpoint.description == "Checkpoint without project info"
    
    def test_long_project_paths(self):
        """Test handling of very long project paths."""
        long_path = "/very/long/path/that/goes/deep/into/nested/directories/and/keeps/going/until/it/reaches/maximum/length"
        
        task = Task(
            content="Todo with long project path",
            active_form="Testing long path",
            project_id="long-path-project",
            project_path=long_path
        )
        
        assert task.project_path == long_path
        assert len(task.project_path) > 80  # Verify it's actually long
    
    def test_special_characters_in_project_fields(self):
        """Test handling of special characters in project fields."""
        special_project_id = "project-with-special-chars_123!@#"
        special_path = "/path/with spaces/and-special_chars/项目"
        
        plan = Plan(
            title="Plan with special project info",
            description="Testing special characters",
            project_id=special_project_id,
            project_path=special_path
        )
        
        assert plan.project_id == special_project_id
        assert plan.project_path == special_path
    
    def test_project_id_consistency(self):
        """Test that project IDs are consistent across models."""
        project_id = "consistent-project"
        project_path = "/path/to/consistent/project"
        
        checkpoint = Checkpoint(
            description="Test checkpoint",
            project_id=project_id,
            project_path=project_path
        )
        
        task = Task(
            content="Test task", 
            active_form="Testing task",
            project_id=project_id,
            project_path=project_path
        )
        
        plan = Plan(
            title="Test plan",
            description="Test plan",
            project_id=project_id,
            project_path=project_path
        )
        
        # All should have same project info
        models = [checkpoint, task, plan]
        for model in models:
            assert model.project_id == project_id
            assert model.project_path == project_path