"""Tests for directory creation behavior and cross-project usage."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.tusk.config import TuskConfig


class TestDirectoryCreation:
    """Test directory creation behavior for cross-project usage."""
    
    def test_coa_created_in_current_working_directory(self):
        """Test that .coa is created in the current working directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Change to temp directory and create config with local storage mode
            with patch('pathlib.Path.cwd', return_value=temp_path):
                config = TuskConfig(storage_mode="local")
                
                # Should be relative to the "current" working directory
                expected_path = temp_path / ".coa" / "tusk" / "data"
                assert config.get_data_dir() == expected_path
                
                # Create directories
                config.ensure_directories()
                
                # Check that .coa was created in the temp directory
                assert (temp_path / ".coa").exists()
                assert (temp_path / ".coa" / "tusk").exists()
                assert (temp_path / ".coa" / "tusk" / "data").exists()
    
    def test_multiple_projects_isolated_with_explicit_paths(self):
        """Test that different projects can have isolated .coa directories when using explicit paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project1_dir = Path(temp_dir) / "project1" / ".coa" / "tusk" / "data"
            project2_dir = Path(temp_dir) / "project2" / ".coa" / "tusk" / "data"
            
            # Create configs with explicit data directories for true isolation
            config1 = TuskConfig(storage_mode="local", data_dir=project1_dir)
            config2 = TuskConfig(storage_mode="local", data_dir=project2_dir)
            
            config1.ensure_directories()
            config2.ensure_directories()
            
            # Create some test data
            (config1.get_data_dir() / "test_file1.json").write_text('{"project": 1}')
            (config2.get_data_dir() / "test_file2.json").write_text('{"project": 2}')
            
            # Verify isolation
            assert config1.get_data_dir() != config2.get_data_dir()
            assert (config1.get_data_dir() / "test_file1.json").exists()
            assert (config2.get_data_dir() / "test_file2.json").exists()
            assert not (config1.get_data_dir() / "test_file2.json").exists()
            assert not (config2.get_data_dir() / "test_file1.json").exists()
    
    def test_environment_variable_override(self):
        """Test that TUSK_DATA_DIR environment variable overrides default behavior."""
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_data_dir = Path(temp_dir) / "custom_tusk_location"
            
            with patch.dict(os.environ, {"TUSK_DATA_DIR": str(custom_data_dir)}):
                config = TuskConfig.from_env()
                
                # Should use the environment variable, not current working directory
                assert config.get_data_dir() == custom_data_dir
                
                config.ensure_directories()
                
                # Should create at the custom location
                assert custom_data_dir.exists()
                assert (custom_data_dir / "checkpoints").exists()
    
    def test_explicit_data_dir_is_persistent(self):
        """Test that explicit data directory is persistent regardless of working directory changes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            initial_dir = Path(temp_dir) / "initial"
            changed_dir = Path(temp_dir) / "changed"
            explicit_data_dir = Path(temp_dir) / "explicit" / ".coa" / "tusk" / "data"
            
            initial_dir.mkdir()
            changed_dir.mkdir()
            
            # Create config with explicit data directory
            with patch('pathlib.Path.cwd', return_value=initial_dir):
                config = TuskConfig(storage_mode="local", data_dir=explicit_data_dir)
                initial_data_dir = config.get_data_dir()
            
            # Change working directory
            with patch('pathlib.Path.cwd', return_value=changed_dir):
                # Config should still point to explicit directory
                assert config.get_data_dir() == initial_data_dir
                assert config.get_data_dir() == explicit_data_dir
                
                # Config behavior is consistent
                assert config.get_data_dir() == config.get_data_dir()
    
    def test_deep_project_structure_handling(self):
        """Test behavior in deeply nested project structures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Simulate a deeply nested project structure
            deep_project = Path(temp_dir) / "repo" / "backend" / "services" / "api"
            deep_project.mkdir(parents=True)
            
            with patch('pathlib.Path.cwd', return_value=deep_project):
                config = TuskConfig(storage_mode="local")
                
                # .coa should be created at the current working directory level
                expected_coa = deep_project / ".coa"
                assert config.get_data_dir() == expected_coa / "tusk" / "data"
                
                config.ensure_directories()
                
                # Verify structure is created at the correct level
                assert expected_coa.exists()
                assert (expected_coa / "tusk" / "data").exists()
                
                # Should NOT create .coa in parent directories
                assert not (deep_project.parent / ".coa").exists()
                assert not (Path(temp_dir) / "repo" / ".coa").exists()
    
    def test_permission_handling(self):
        """Test behavior when directory creation fails due to permissions."""
        # Create a read-only directory to simulate permission issues
        with tempfile.TemporaryDirectory() as temp_dir:
            readonly_dir = Path(temp_dir) / "readonly"
            readonly_dir.mkdir()
            
            # Make it read-only (this is platform-dependent)
            try:
                readonly_dir.chmod(0o444)  # Read-only
                
                with patch('pathlib.Path.cwd', return_value=readonly_dir):
                    config = TuskConfig(storage_mode="local")
                    
                    # ensure_directories should handle the error gracefully
                    # This might raise an exception or handle it internally
                    # The exact behavior depends on implementation
                    try:
                        config.ensure_directories()
                        # If it succeeds, check if directories were created elsewhere
                        # or if the operation was skipped
                    except (PermissionError, OSError):
                        # Expected behavior - should fail gracefully
                        pass
                        
            finally:
                # Restore permissions for cleanup
                readonly_dir.chmod(0o755)
    
    def test_existing_coa_directory_reuse(self):
        """Test that existing .coa directories are reused properly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / "project"
            project_dir.mkdir()
            
            with patch('pathlib.Path.cwd', return_value=project_dir):
                # First config instance
                config1 = TuskConfig(storage_mode="local")
                config1.ensure_directories()
                
                # Create some data
                test_file = config1.get_data_dir() / "existing_data.json"
                test_file.write_text('{"existing": true}')
                
                # Second config instance (simulating restart)
                config2 = TuskConfig(storage_mode="local")
                config2.ensure_directories()
                
                # Should reuse the same directory
                assert config1.get_data_dir() == config2.get_data_dir()
                
                # Existing data should be preserved
                assert test_file.exists()
                assert '{"existing": true}' in test_file.read_text()
    
    def test_cross_project_data_isolation_verification(self):
        """Comprehensive test that different projects cannot access each other's data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create two separate project directories
            proj_a = Path(temp_dir) / "project_a"
            proj_b = Path(temp_dir) / "project_b"
            proj_a.mkdir()
            proj_b.mkdir()
            
            # Project A: Create config and data
            with patch('pathlib.Path.cwd', return_value=proj_a):
                config_a = TuskConfig(storage_mode="local")
                config_a.ensure_directories()
                data_dir_a = config_a.get_data_dir()
                
                # Simulate creating project-specific data
                (data_dir_a / "todos" / "project_a_todos.json").parent.mkdir(exist_ok=True)
                (data_dir_a / "todos" / "project_a_todos.json").write_text('{"project": "A"}')
            
            # Project B: Create config and data
            with patch('pathlib.Path.cwd', return_value=proj_b):
                config_b = TuskConfig(storage_mode="local")
                config_b.ensure_directories()
                data_dir_b = config_b.get_data_dir()
                
                # Simulate creating different project-specific data
                (data_dir_b / "todos" / "project_b_todos.json").parent.mkdir(exist_ok=True)
                (data_dir_b / "todos" / "project_b_todos.json").write_text('{"project": "B"}')
            
            # Verify complete isolation
            assert data_dir_a != data_dir_b
            assert str(proj_a) in str(data_dir_a)
            assert str(proj_b) in str(data_dir_b)
            
            # Verify A's data exists only in A
            assert (data_dir_a / "todos" / "project_a_todos.json").exists()
            assert not (data_dir_b / "todos" / "project_a_todos.json").exists()
            
            # Verify B's data exists only in B
            assert (data_dir_b / "todos" / "project_b_todos.json").exists()
            assert not (data_dir_a / "todos" / "project_b_todos.json").exists()
            
            # Verify content isolation
            a_content = (data_dir_a / "todos" / "project_a_todos.json").read_text()
            b_content = (data_dir_b / "todos" / "project_b_todos.json").read_text()
            assert '"project": "A"' in a_content
            assert '"project": "B"' in b_content


class TestDirectoryCreationEdgeCases:
    """Test edge cases in directory creation."""
    
    def test_relative_vs_absolute_paths(self):
        """Test behavior with relative vs absolute paths in working directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            abs_path = Path(temp_dir).resolve()
            
            with patch('pathlib.Path.cwd', return_value=abs_path):
                config = TuskConfig(storage_mode="local")
                
                # Should work with absolute paths
                assert config.get_data_dir().is_absolute()
                assert config.get_data_dir() == abs_path / ".coa" / "tusk" / "data"
    
    def test_special_characters_in_path(self):
        """Test handling of special characters in working directory path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create directory with special characters (where supported)
            special_dir = Path(temp_dir) / "project with spaces"
            special_dir.mkdir()
            
            with patch('pathlib.Path.cwd', return_value=special_dir):
                config = TuskConfig(storage_mode="local")
                config.ensure_directories()
                
                # Should handle special characters gracefully
                assert config.get_data_dir().exists()
                assert "project with spaces" in str(config.get_data_dir())
    
    def test_very_long_path_handling(self):
        """Test behavior with very long directory paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a very long path (within OS limits)
            long_components = ["very"] * 10 + ["long"] * 10 + ["path"] * 5
            long_path = Path(temp_dir)
            for component in long_components:
                long_path = long_path / component
            
            try:
                long_path.mkdir(parents=True)
                
                with patch('pathlib.Path.cwd', return_value=long_path):
                    config = TuskConfig(storage_mode="local")
                    
                    # Should handle long paths appropriately
                    # This might fail on some systems due to path length limits
                    try:
                        config.ensure_directories()
                        assert config.get_data_dir().exists()
                    except OSError:
                        # Expected on systems with path length limitations
                        pytest.skip("Path too long for this system")
                        
            except OSError:
                pytest.skip("Cannot create test path on this system")