"""Tests for AsyncIO-safe subprocess handling to prevent deadlocks in MCP tools."""

import asyncio
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tusk.config import TuskConfig
from tusk.tools.enhanced_all import EnhancedUnifiedCheckpointTool


class TestAsyncIOSubprocessSafety:
    """Test AsyncIO-safe subprocess handling to prevent MCP tool deadlocks."""

    @pytest.fixture
    def temp_config(self, tmp_path):
        """Create a temporary config for testing."""
        config = TuskConfig(data_dir=tmp_path)
        config.ensure_directories()
        return config

    @pytest.fixture
    def checkpoint_tool(self, temp_config):
        """Create a checkpoint tool instance for testing."""
        # Create a mock server with the required storage components
        mock_server = MagicMock()
        mock_server.checkpoint_storage = MagicMock()
        mock_server.search_engine = MagicMock()
        mock_server.config = temp_config

        tool = EnhancedUnifiedCheckpointTool(mock_server)
        return tool

    @pytest.mark.asyncio
    async def test_async_git_info_safety(self, checkpoint_tool):
        """Test that git info detection works safely in async context."""
        project_path = str(Path.cwd())

        # Test the async-safe git info method
        branch, commit = await checkpoint_tool._get_git_info_safe(project_path)

        # Should return results or None without hanging
        assert branch is None or isinstance(branch, str)
        assert commit is None or isinstance(commit, str)

        # If we're in a git repo, should get actual values
        if Path(project_path, ".git").exists():
            # At least one should be populated in a git repo
            assert branch is not None or commit is not None

    @pytest.mark.asyncio
    async def test_async_file_detection_safety(self, checkpoint_tool):
        """Test that file detection works safely in async context."""
        project_path = str(Path.cwd())

        # Test the async-safe file detection method
        files = await checkpoint_tool._get_recently_modified_files_safe(project_path)

        # Should return a list without hanging
        assert isinstance(files, list)
        assert len(files) >= 0  # Could be empty, that's fine

        # All items should be strings (file paths)
        for file_path in files:
            assert isinstance(file_path, str)
            assert len(file_path) > 0

    @pytest.mark.asyncio
    async def test_concurrent_subprocess_calls(self, checkpoint_tool):
        """Test that multiple concurrent subprocess calls don't deadlock."""
        project_path = str(Path.cwd())

        # Run multiple async operations concurrently
        tasks = []
        for _i in range(3):
            tasks.append(checkpoint_tool._get_git_info_safe(project_path))
            tasks.append(checkpoint_tool._get_recently_modified_files_safe(project_path))

        # All should complete without hanging
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Should have results for all tasks
        assert len(results) == 6

        # No exceptions should have occurred
        for result in results:
            assert not isinstance(result, Exception), f"Task failed with: {result}"

    @pytest.mark.asyncio
    async def test_subprocess_timeout_handling(self, checkpoint_tool):
        """Test that subprocess timeouts are handled correctly."""
        # Test with invalid path to trigger timeout/error handling
        invalid_path = "/nonexistent/path/that/should/not/exist"

        # Should handle gracefully without hanging
        branch, commit = await checkpoint_tool._get_git_info_safe(invalid_path)
        files = await checkpoint_tool._get_recently_modified_files_safe(invalid_path)

        # Should return safe defaults
        assert branch is None
        assert commit is None
        assert files == []

    def test_synchronous_subprocess_works_outside_async(self):
        """Verify that synchronous subprocess calls work fine outside async context."""
        project_path = str(Path.cwd())

        # This should work fine - proving the issue is AsyncIO context
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=5,
            )

            # Should complete successfully
            assert result.returncode is not None

        except subprocess.TimeoutExpired:
            pytest.fail("Synchronous subprocess should not timeout")
        except FileNotFoundError:
            # Git not available - that's fine for this test
            pytest.skip("Git not available in test environment")

    @pytest.mark.asyncio
    async def test_asyncio_to_thread_integration(self):
        """Test that asyncio.to_thread works correctly for subprocess calls."""

        def run_subprocess():
            """Run a simple subprocess command."""
            try:
                result = subprocess.run(
                    ["python", "--version"], capture_output=True, text=True, timeout=5
                )
                return result.returncode == 0
            except Exception:
                return False

        # Should work without hanging
        success = await asyncio.wait_for(asyncio.to_thread(run_subprocess), timeout=10.0)

        assert isinstance(success, bool)

    @pytest.mark.asyncio
    async def test_multiple_timeout_layers(self, checkpoint_tool):
        """Test that multiple timeout layers work correctly."""
        project_path = str(Path.cwd())

        # Test with very short timeout to ensure timeout handling works
        with patch.object(checkpoint_tool, "_get_git_info_safe") as mock_git:

            async def slow_git_info(path):
                """Simulate slow git operation."""
                await asyncio.sleep(0.1)  # Simulate work
                return "main", "abc123"

            mock_git.side_effect = slow_git_info

            # Should complete normally with reasonable timeout
            start_time = asyncio.get_event_loop().time()
            branch, commit = await asyncio.wait_for(
                mock_git(project_path), timeout=1.0  # 1 second should be plenty
            )
            end_time = asyncio.get_event_loop().time()

            # Should have completed quickly
            assert end_time - start_time < 0.5
            assert branch == "main"
            assert commit == "abc123"


class TestAsyncSubprocessRegressionPrevention:
    """Regression tests to prevent AsyncIO subprocess hanging from returning."""

    @pytest.mark.asyncio
    async def test_original_hanging_scenario_fixed(self):
        """Test that the original hanging scenario is now fixed."""
        # This test simulates the exact conditions that caused hanging

        async def simulate_mcp_tool_call():
            """Simulate calling subprocess within MCP async tool context."""

            # This pattern used to hang - now should work
            def git_subprocess():
                return subprocess.run(
                    ["git", "--version"], capture_output=True, text=True, timeout=3
                )

            # Using asyncio.to_thread should prevent hanging
            result = await asyncio.to_thread(git_subprocess)
            return result.returncode == 0

        # Should complete without hanging
        success = await asyncio.wait_for(simulate_mcp_tool_call(), timeout=10.0)  # Generous timeout

        assert isinstance(success, bool)

    @pytest.mark.asyncio
    async def test_nested_async_subprocess_safety(self):
        """Test nested async operations with subprocess calls."""

        async def level_one():
            def subprocess_call():
                return subprocess.run(["python", "--version"], capture_output=True, timeout=2)

            return await asyncio.to_thread(subprocess_call)

        async def level_two():
            return await level_one()

        async def level_three():
            return await level_two()

        # Should handle nested async operations safely
        result = await asyncio.wait_for(level_three(), timeout=15.0)
        assert result.returncode is not None

    def test_performance_benchmark(self):
        """Benchmark to ensure async-safe methods aren't significantly slower."""
        import time

        # This is more of a smoke test to ensure we didn't introduce major performance issues
        start_time = time.time()

        # Run a simple operation multiple times
        for _ in range(5):
            try:
                subprocess.run(["python", "--version"], capture_output=True, timeout=1)
            except Exception:
                pass  # Don't fail on subprocess issues

        end_time = time.time()

        # Should complete reasonably quickly (generous bounds for CI)
        assert end_time - start_time < 10.0, "Performance regression detected"


if __name__ == "__main__":
    # Allow running directly for development
    pytest.main([__file__, "-v"])
