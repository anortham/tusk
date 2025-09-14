"""Regression tests to prevent checkpoint hanging issues from returning."""

import asyncio
import pytest
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tusk.config import TuskConfig
from tusk.storage.checkpoint_store import CheckpointStorage
from tusk.storage.search import SearchEngine
from tusk.tools.enhanced_all import EnhancedUnifiedCheckpointTool
from tusk.models.checkpoint import Checkpoint


class TestCheckpointHangingRegression:
    """Regression tests to ensure checkpoint operations never hang."""

    @pytest.fixture
    def temp_config(self, tmp_path):
        """Create a temporary config for testing."""
        config = TuskConfig(data_dir=tmp_path)
        config.ensure_directories()
        return config

    @pytest.fixture
    def mock_server(self, temp_config):
        """Create a mock server with real storage components."""
        server = MagicMock()
        server.config = temp_config
        server.checkpoint_storage = CheckpointStorage(temp_config)
        server.search_engine = SearchEngine(temp_config)
        # SearchEngine initializes automatically in __init__
        return server

    @pytest.fixture
    def checkpoint_tool(self, mock_server):
        """Create a checkpoint tool instance."""
        return EnhancedUnifiedCheckpointTool(mock_server)

    @pytest.mark.asyncio
    async def test_checkpoint_save_never_hangs(self, checkpoint_tool):
        """Test that checkpoint save operations complete within reasonable time."""
        start_time = time.time()

        try:
            # This operation used to hang - should now complete quickly
            result = await asyncio.wait_for(
                checkpoint_tool._save_checkpoint("Test checkpoint for hanging regression"),
                timeout=30.0,  # Generous timeout for CI environments
            )

            end_time = time.time()
            duration = end_time - start_time

            # Should complete in reasonable time
            assert duration < 25.0, f"Checkpoint save took too long: {duration}s"

            # Should return valid JSON result
            import json

            parsed = json.loads(result)
            assert parsed["success"] is True
            assert "checkpoint" in parsed
            assert "id" in parsed["checkpoint"]

        except asyncio.TimeoutError:
            pytest.fail("Checkpoint save operation timed out - hanging regression detected!")

    @pytest.mark.asyncio
    async def test_multiple_concurrent_checkpoints(self, checkpoint_tool):
        """Test that multiple concurrent checkpoint operations don't deadlock."""
        descriptions = [
            "Concurrent checkpoint test 1",
            "Concurrent checkpoint test 2",
            "Concurrent checkpoint test 3",
        ]

        start_time = time.time()

        try:
            # Run multiple checkpoint saves concurrently
            tasks = [checkpoint_tool._save_checkpoint(desc) for desc in descriptions]

            results = await asyncio.wait_for(
                asyncio.gather(*tasks), timeout=60.0  # Generous timeout for multiple operations
            )

            end_time = time.time()
            duration = end_time - start_time

            # Should complete all operations in reasonable time
            assert duration < 50.0, f"Concurrent checkpoints took too long: {duration}s"

            # All should succeed
            assert len(results) == 3
            for result in results:
                import json

                parsed = json.loads(result)
                assert parsed["success"] is True

        except asyncio.TimeoutError:
            pytest.fail(
                "Concurrent checkpoint operations timed out - deadlock regression detected!"
            )

    @pytest.mark.asyncio
    async def test_git_operations_dont_hang(self, checkpoint_tool):
        """Test that git operations specifically don't hang."""
        project_path = str(Path.cwd())

        start_time = time.time()

        try:
            # Test git info operation
            branch, commit = await asyncio.wait_for(
                checkpoint_tool._get_git_info_safe(project_path), timeout=15.0
            )

            # Test file detection operation
            files = await asyncio.wait_for(
                checkpoint_tool._get_recently_modified_files_safe(project_path), timeout=15.0
            )

            end_time = time.time()
            duration = end_time - start_time

            # Should complete quickly
            assert duration < 12.0, f"Git operations took too long: {duration}s"

            # Results should be valid types
            assert branch is None or isinstance(branch, str)
            assert commit is None or isinstance(commit, str)
            assert isinstance(files, list)

        except asyncio.TimeoutError:
            pytest.fail("Git operations timed out - subprocess hanging regression detected!")

    @pytest.mark.asyncio
    async def test_full_checkpoint_workflow_timing(self, checkpoint_tool):
        """Test the complete checkpoint workflow completes in reasonable time."""
        start_time = time.time()

        # Mock the storage operations to focus on the hanging issue
        checkpoint_tool.checkpoint_storage.save = MagicMock(return_value=True)
        checkpoint_tool.search_engine.index_checkpoint = MagicMock()

        try:
            # Test the full save checkpoint workflow
            result = await asyncio.wait_for(
                checkpoint_tool._save_checkpoint("Full workflow timing test"), timeout=20.0
            )

            end_time = time.time()
            duration = end_time - start_time

            # Should complete in reasonable time even with git operations
            assert duration < 15.0, f"Full checkpoint workflow took too long: {duration}s"

            # Should succeed
            import json

            parsed = json.loads(result)
            assert parsed["success"] is True

        except asyncio.TimeoutError:
            pytest.fail("Full checkpoint workflow timed out - workflow regression detected!")

    @pytest.mark.asyncio
    async def test_checkpoint_tool_registration_handling(self, mock_server):
        """Test that checkpoint tool registration doesn't cause hanging."""
        # Mock the FastMCP server registration
        mock_mcp = MagicMock()
        mock_mcp.tool = lambda func: func  # Simple decorator that returns the function

        start_time = time.time()

        try:
            # Test tool registration
            tool = EnhancedUnifiedCheckpointTool(mock_server)

            # This registration process used to hang
            await asyncio.wait_for(asyncio.to_thread(tool.register, mock_mcp), timeout=10.0)

            end_time = time.time()
            duration = end_time - start_time

            # Should register quickly
            assert duration < 8.0, f"Tool registration took too long: {duration}s"

        except asyncio.TimeoutError:
            pytest.fail("Tool registration timed out - registration hanging regression detected!")

    @pytest.mark.asyncio
    async def test_error_conditions_dont_hang(self, checkpoint_tool):
        """Test that error conditions don't cause hanging."""
        start_time = time.time()

        try:
            # Test with invalid inputs that should fail gracefully
            result1 = await asyncio.wait_for(
                checkpoint_tool._save_checkpoint(None), timeout=10.0  # Invalid description
            )

            result2 = await asyncio.wait_for(
                checkpoint_tool._get_git_info_safe(""), timeout=10.0  # Invalid path
            )

            result3 = await asyncio.wait_for(
                checkpoint_tool._get_recently_modified_files_safe("/invalid/path"), timeout=10.0
            )

            end_time = time.time()
            duration = end_time - start_time

            # Should handle errors quickly
            assert duration < 8.0, f"Error handling took too long: {duration}s"

            # Should return proper error responses/defaults
            import json

            parsed1 = json.loads(result1)
            assert parsed1["success"] is False

            assert result2 == (None, None)
            assert result3 == []

        except asyncio.TimeoutError:
            pytest.fail("Error handling timed out - error condition hanging regression detected!")

    def test_memory_usage_during_operations(self, checkpoint_tool):
        """Test that operations don't cause memory issues that could lead to hanging."""
        try:
            import psutil
            import os
        except ImportError:
            pytest.skip("psutil not available for memory testing")

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Run multiple operations
        async def run_operations():
            for i in range(10):
                await checkpoint_tool._save_checkpoint(f"Memory test checkpoint {i}")
                await checkpoint_tool._get_git_info_safe(str(Path.cwd()))
                await checkpoint_tool._get_recently_modified_files_safe(str(Path.cwd()))

        # Run the operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(asyncio.wait_for(run_operations(), timeout=120.0))
        finally:
            loop.close()

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Should not have excessive memory growth (allow some reasonable increase)
        max_allowed_increase = 100 * 1024 * 1024  # 100MB
        assert (
            memory_increase < max_allowed_increase
        ), f"Excessive memory usage: {memory_increase} bytes"

    @pytest.mark.asyncio
    async def test_rapid_sequential_operations(self, checkpoint_tool):
        """Test rapid sequential operations don't cause resource exhaustion."""
        start_time = time.time()

        try:
            # Rapid sequential operations
            for i in range(20):
                result = await asyncio.wait_for(
                    checkpoint_tool._get_git_info_safe(str(Path.cwd())), timeout=5.0
                )

                # Quick validation
                assert isinstance(result, tuple)
                assert len(result) == 2

            end_time = time.time()
            duration = end_time - start_time

            # Should complete all operations in reasonable time
            assert duration < 30.0, f"Rapid sequential operations took too long: {duration}s"

        except asyncio.TimeoutError:
            pytest.fail(
                "Rapid sequential operations timed out - resource exhaustion regression detected!"
            )

    @pytest.mark.asyncio
    async def test_stress_test_concurrent_mixed_operations(self, checkpoint_tool):
        """Stress test with mixed concurrent operations."""
        start_time = time.time()

        try:
            # Mix of different operations
            tasks = []

            # Add checkpoint saves
            for i in range(3):
                tasks.append(checkpoint_tool._save_checkpoint(f"Stress test checkpoint {i}"))

            # Add git operations
            for i in range(5):
                tasks.append(checkpoint_tool._get_git_info_safe(str(Path.cwd())))

            # Add file detection
            for i in range(5):
                tasks.append(checkpoint_tool._get_recently_modified_files_safe(str(Path.cwd())))

            # Run all concurrently
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=90.0,  # Generous timeout for stress test
            )

            end_time = time.time()
            duration = end_time - start_time

            # Should complete all operations
            assert duration < 75.0, f"Stress test took too long: {duration}s"

            # Check that we got results (some may be exceptions, that's ok)
            assert len(results) == 13

            # No operation should have hung (would cause TimeoutError)
            timeout_errors = [r for r in results if isinstance(r, asyncio.TimeoutError)]
            assert (
                len(timeout_errors) == 0
            ), f"Found {len(timeout_errors)} timeout errors in stress test"

        except asyncio.TimeoutError:
            pytest.fail(
                "Stress test timed out - concurrent operations hanging regression detected!"
            )


if __name__ == "__main__":
    # Allow running directly for development
    pytest.main([__file__, "-v"])
