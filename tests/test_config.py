"""Tests for Tusk configuration management."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.tusk.config import TuskConfig


class TestTuskConfig:
    """Test configuration management functionality."""

    def test_default_config_creation(self):
        """Test creating config with default values."""
        config = TuskConfig()

        assert config.server_name == "Tusk"
        assert config.search_enabled is True
        assert config.max_search_results == 50
        assert config.default_checkpoint_ttl == "7d"
        assert config.max_highlights_per_checkpoint == 10
        assert config.enable_transformations is True
        assert config.log_level == "INFO"

        # Check that default paths are set (using new global storage mode)
        assert config.storage_mode == "global"
        assert config.get_data_dir() == Path.home() / ".coa" / "tusk" / "data"
        assert config.get_log_dir() == Path.home() / ".coa" / "tusk" / "logs"

    def test_custom_config_creation(self):
        """Test creating config with custom values."""
        custom_data_dir = Path("/custom/data")
        custom_log_dir = Path("/custom/logs")

        config = TuskConfig(
            server_name="CustomTusk",
            data_dir=custom_data_dir,
            log_dir=custom_log_dir,
            search_enabled=False,
            max_search_results=100,
            default_checkpoint_ttl="14d",
            max_highlights_per_checkpoint=20,
            enable_transformations=False,
            log_level="DEBUG",
        )

        assert config.server_name == "CustomTusk"
        assert config.get_data_dir() == custom_data_dir
        assert config.get_log_dir() == custom_log_dir
        assert config.search_enabled is False
        assert config.max_search_results == 100
        assert config.default_checkpoint_ttl == "14d"
        assert config.max_highlights_per_checkpoint == 20
        assert config.enable_transformations is False
        assert config.log_level == "DEBUG"

    def test_config_from_env_defaults(self):
        """Test creating config from environment with no env vars set."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove tusk-specific env vars if they exist
            env_keys_to_clear = [
                "TUSK_SERVER_NAME",
                "TUSK_DATA_DIR",
                "TUSK_SEARCH_ENABLED",
                "TUSK_MAX_SEARCH_RESULTS",
                "TUSK_DEFAULT_TTL",
                "TUSK_MAX_HIGHLIGHTS",
                "TUSK_TRANSFORMATIONS",
                "TUSK_LOG_LEVEL",
                "TUSK_LOG_DIR",
            ]
            for key in env_keys_to_clear:
                os.environ.pop(key, None)

            config = TuskConfig.from_env()

            # Should match default values
            assert config.server_name == "Tusk"
            assert config.search_enabled is True
            assert config.max_search_results == 50
            assert config.default_checkpoint_ttl == "7d"
            assert config.max_highlights_per_checkpoint == 10
            assert config.enable_transformations is True
            assert config.log_level == "INFO"

    def test_config_from_env_custom_values(self):
        """Test creating config from environment with custom env vars."""
        env_vars = {
            "TUSK_SERVER_NAME": "EnvTusk",
            "TUSK_DATA_DIR": "/env/data",
            "TUSK_SEARCH_ENABLED": "false",
            "TUSK_MAX_SEARCH_RESULTS": "200",
            "TUSK_DEFAULT_TTL": "30d",
            "TUSK_MAX_HIGHLIGHTS": "5",
            "TUSK_TRANSFORMATIONS": "false",
            "TUSK_LOG_LEVEL": "WARNING",
            "TUSK_LOG_DIR": "/env/logs",
        }

        with patch.dict(os.environ, env_vars):
            config = TuskConfig.from_env()

            assert config.server_name == "EnvTusk"
            assert config.get_data_dir() == Path("/env/data")
            assert config.search_enabled is False
            assert config.max_search_results == 200
            assert config.default_checkpoint_ttl == "30d"
            assert config.max_highlights_per_checkpoint == 5
            assert config.enable_transformations is False
            assert config.log_level == "WARNING"
            assert config.log_dir == Path("/env/logs")

    def test_config_boolean_env_parsing(self):
        """Test that boolean environment variables are parsed correctly."""
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("1", False),  # Only "true" (case insensitive) should be True
            ("yes", False),
            ("", False),
        ]

        for env_value, expected in test_cases:
            with patch.dict(os.environ, {"TUSK_SEARCH_ENABLED": env_value}):
                config = TuskConfig.from_env()
                assert config.search_enabled is expected, f"Failed for env_value: {env_value}"

    def test_config_integer_env_parsing(self):
        """Test that integer environment variables are parsed correctly."""
        with patch.dict(os.environ, {"TUSK_MAX_SEARCH_RESULTS": "75", "TUSK_MAX_HIGHLIGHTS": "15"}):
            config = TuskConfig.from_env()
            assert config.max_search_results == 75
            assert config.max_highlights_per_checkpoint == 15

    def test_ensure_directories_creates_structure(self):
        """Test that ensure_directories creates the expected directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            log_dir = Path(temp_dir) / "logs"

            config = TuskConfig(data_dir=data_dir, log_dir=log_dir)
            config.ensure_directories()

            # Check main directories
            assert data_dir.exists()
            assert log_dir.exists()

            # Check subdirectories
            assert (data_dir / "checkpoints").exists()
            assert (data_dir / "todos").exists()
            assert (data_dir / "plans").exists()
            assert (data_dir / "index").exists()

    def test_ensure_directories_handles_existing_dirs(self):
        """Test that ensure_directories works when directories already exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            log_dir = Path(temp_dir) / "logs"

            # Pre-create some directories
            data_dir.mkdir(parents=True)
            (data_dir / "checkpoints").mkdir()

            config = TuskConfig(data_dir=data_dir, log_dir=log_dir)

            # Should not raise an error
            config.ensure_directories()

            # All directories should still exist
            assert data_dir.exists()
            assert log_dir.exists()
            assert (data_dir / "checkpoints").exists()
            assert (data_dir / "todos").exists()
            assert (data_dir / "plans").exists()
            assert (data_dir / "index").exists()

    def test_get_data_dir(self):
        """Test get_data_dir method returns the correct path."""
        custom_path = Path("/custom/path")
        config = TuskConfig(data_dir=custom_path)

        assert config.get_data_dir() == custom_path

    def test_config_validation_log_level(self):
        """Test that invalid log levels raise validation errors."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]

        # Test valid levels
        for level in valid_levels:
            config = TuskConfig(log_level=level)
            assert config.log_level == level

        # Test invalid level should raise validation error
        with pytest.raises(ValueError):
            TuskConfig(log_level="INVALID")

    def test_config_field_descriptions(self):
        """Test that all fields have proper descriptions for MCP introspection."""
        # Check that model has fields with descriptions
        fields = TuskConfig.model_fields

        # Spot check a few important fields
        assert "server_name" in fields
        assert fields["server_name"].description is not None
        assert "data_dir" in fields
        assert fields["data_dir"].description is not None
        assert "search_enabled" in fields
        assert fields["search_enabled"].description is not None

    def test_config_workspace_concept_removed(self):
        """Test that workspace-related functionality is properly removed."""
        config = TuskConfig()

        # Should not have workspace-related fields
        fields = TuskConfig.model_fields
        workspace_fields = [field for field in fields if "workspace" in field.lower()]
        assert len(workspace_fields) == 0, f"Found workspace fields: {workspace_fields}"

        # Data directory should be project-based, not workspace-based
        data_dir = config.get_data_dir()
        assert "workspace" not in str(data_dir).lower()
        assert data_dir.name == "data"  # Direct data directory, not workspace/data
