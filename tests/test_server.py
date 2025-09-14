"""Tests for server functionality and MCP integration."""

import pytest
from unittest.mock import Mock, patch

from src.tusk.server import TuskServer, main
from src.tusk.config import TuskConfig


class TestServerConfiguration:
    """Test server configuration and setup."""

    def test_server_class_exists(self):
        """Test that the TuskServer class is configured."""
        config = TuskConfig()
        server = TuskServer(config)

        # Verify the server object exists and has expected attributes
        assert server is not None
        assert hasattr(server, "config")
        assert server.config.server_name == "Tusk"

    def test_server_config_integration(self):
        """Test that server integrates with TuskConfig."""
        config = TuskConfig()

        # Verify config has server-related settings
        assert config.server_name == "Tusk"
        assert config.log_level in ["DEBUG", "INFO", "WARNING", "ERROR"]
        assert isinstance(config.search_enabled, bool)
        assert isinstance(config.enable_transformations, bool)

    def test_server_tools_registration(self):
        """Test that server tools are properly registered."""
        # Test that the server can be created and has storage components
        config = TuskConfig()
        server = TuskServer(config)

        # Verify server has storage components
        assert hasattr(server, "checkpoint_storage")
        assert hasattr(server, "task_storage")
        assert hasattr(server, "plan_storage")
        assert hasattr(server, "search_engine")

        # Note: More detailed testing would require actually starting the server
        # which is complex in a test environment


class TestServerErrorHandling:
    """Test server error handling scenarios."""

    def test_config_validation_errors(self):
        """Test that server handles config validation errors."""
        # Test invalid log level
        with pytest.raises(ValueError):
            TuskConfig(log_level="INVALID")

    def test_directory_creation_handling(self):
        """Test that server handles directory creation gracefully."""
        config = TuskConfig()

        # Should be able to call ensure_directories multiple times
        config.ensure_directories()
        config.ensure_directories()  # Should not raise error

        # Verify directories exist
        data_dir = config.get_data_dir()
        log_dir = config.get_log_dir()

        assert data_dir.exists()
        assert log_dir.exists()


class TestMCPIntegration:
    """Test MCP (Model Context Protocol) integration."""

    def test_mcp_server_structure(self):
        """Test that MCP server follows expected structure."""
        config = TuskConfig()
        server = TuskServer(config)

        # Verify server structure
        assert hasattr(server, "config")
        assert server.config.server_name == "Tusk"

        # Test that importing server doesn't raise errors
        assert server is not None

    def test_tools_import_successfully(self):
        """Test that all tools can be imported without errors."""
        try:
            from src.tusk.tools.unified import (
                UnifiedTaskTool,
                UnifiedCheckpointTool,
                UnifiedRecallTool,
                UnifiedStandupTool,
                UnifiedPlanTool,
            )

            # All tools imported successfully
            tools = [
                UnifiedTaskTool,
                UnifiedCheckpointTool,
                UnifiedRecallTool,
                UnifiedStandupTool,
                UnifiedPlanTool,
            ]

            for tool_class in tools:
                assert tool_class is not None
                assert callable(tool_class)

        except ImportError as e:
            pytest.fail(f"Failed to import tools: {e}")

    def test_config_from_environment(self):
        """Test that server can be configured from environment variables."""
        import os

        # Test with environment variables
        test_env = {
            "TUSK_SERVER_NAME": "TestTusk",
            "TUSK_LOG_LEVEL": "DEBUG",
            "TUSK_SEARCH_ENABLED": "false",
        }

        with patch.dict(os.environ, test_env):
            config = TuskConfig.from_env()

            assert config.server_name == "TestTusk"
            assert config.log_level == "DEBUG"
            assert config.search_enabled is False


class TestServerStartupSequence:
    """Test server startup and initialization sequence."""

    def test_config_initialization_order(self):
        """Test that config initialization happens in correct order."""
        config = TuskConfig()

        # Config should be valid immediately after creation
        assert config.server_name == "Tusk"
        assert config.get_data_dir() is not None
        assert config.get_log_dir() is not None

        # Directories should be creatable
        config.ensure_directories()

        assert config.get_data_dir().exists()
        assert config.get_log_dir().exists()

    def test_storage_initialization(self):
        """Test that storage components can be initialized."""
        config = TuskConfig()
        config.ensure_directories()

        # Test that storage classes can be imported and initialized
        from src.tusk.storage import CheckpointStorage, TaskStorage, PlanStorage
        from src.tusk.storage.search import SearchEngine

        # Should be able to create storage instances
        checkpoint_storage = CheckpointStorage(config)
        task_storage = TaskStorage(config)
        plan_storage = PlanStorage(config)
        search_engine = SearchEngine(config)

        # All should be properly initialized
        assert checkpoint_storage is not None
        assert task_storage is not None
        assert plan_storage is not None
        assert search_engine is not None

    def test_project_detection_integration(self):
        """Test that project detection works with server config."""
        config = TuskConfig(auto_detect_project=True)

        project_id = config.get_current_project_id()
        project_path = config.get_current_project_path()

        # Should return valid project information
        assert isinstance(project_id, str)
        assert len(project_id) > 0
        assert isinstance(project_path, str)
        assert len(project_path) > 0

        # When in tusk directory, should detect tusk
        if "tusk" in project_path.lower():
            assert project_id == "tusk"
