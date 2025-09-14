"""Tests for git integration functionality."""

import pytest
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tusk.config import TuskConfig
from tusk.tools.enhanced_all import EnhancedUnifiedCheckpointTool


class TestGitIntegration:
    """Test git integration features in tools."""

    @pytest.fixture
    def temp_config(self, tmp_path):
        """Create a temporary config for testing."""
        config = TuskConfig(data_dir=tmp_path)
        config.ensure_directories()
        return config

    @pytest.fixture
    def checkpoint_tool(self, temp_config):
        """Create a checkpoint tool instance for testing."""
        mock_server = MagicMock()
        mock_server.checkpoint_storage = MagicMock()
        mock_server.search_engine = MagicMock()
        mock_server.config = temp_config

        tool = EnhancedUnifiedCheckpointTool(mock_server)
        return tool

    def test_git_availability(self):
        """Test if git is available in the test environment."""
        try:
            result = subprocess.run(
                ['git', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            git_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            git_available = False

        # Record git availability for other tests
        pytest.git_available = git_available

        # This test always passes - it's just for information
        assert True, f"Git available: {git_available}"

    def test_git_repository_detection(self):
        """Test detection of git repository."""
        current_dir = Path.cwd()
        git_dir = current_dir / '.git'

        is_git_repo = git_dir.exists()
        pytest.is_git_repo = is_git_repo

        # This test always passes - it's informational
        assert True, f"Current directory is git repo: {is_git_repo}"

    @pytest.mark.asyncio
    async def test_git_branch_detection(self, checkpoint_tool):
        """Test git branch detection functionality."""
        project_path = str(Path.cwd())

        branch, commit = await checkpoint_tool._get_git_info_safe(project_path)

        # If we're in a git repo and git is available, should get results
        if getattr(pytest, 'git_available', False) and getattr(pytest, 'is_git_repo', False):
            assert branch is not None, "Should detect git branch in git repository"
            assert commit is not None, "Should detect git commit in git repository"
            assert isinstance(branch, str), "Branch should be a string"
            assert isinstance(commit, str), "Commit should be a string"
            assert len(branch) > 0, "Branch name should not be empty"
            assert len(commit) > 0, "Commit hash should not be empty"
        else:
            # Outside git repo or git not available - should return None gracefully
            assert branch is None, "Should return None outside git repo"
            assert commit is None, "Should return None outside git repo"

    @pytest.mark.asyncio
    async def test_git_file_detection(self, checkpoint_tool):
        """Test git-based file detection."""
        project_path = str(Path.cwd())

        files = await checkpoint_tool._get_recently_modified_files_safe(project_path)

        # Should always return a list
        assert isinstance(files, list), "Should return list of files"

        # If in git repo, might have files
        if getattr(pytest, 'git_available', False) and getattr(pytest, 'is_git_repo', False):
            # Files should be valid paths if any are returned
            for file_path in files:
                assert isinstance(file_path, str), "File paths should be strings"
                assert len(file_path) > 0, "File paths should not be empty"
                assert not file_path.startswith('/'), "Should be relative paths"

    def test_git_command_compatibility(self):
        """Test compatibility of git commands across different git versions."""
        if not getattr(pytest, 'git_available', False):
            pytest.skip("Git not available")

        project_path = str(Path.cwd())

        # Test git branch command
        try:
            branch_result = subprocess.run(
                ['git', 'branch', '--show-current'],
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=5
            )
            branch_works = branch_result.returncode == 0
        except subprocess.TimeoutExpired:
            branch_works = False

        # Test git rev-parse command
        try:
            commit_result = subprocess.run(
                ['git', 'rev-parse', '--short=8', 'HEAD'],
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=5
            )
            commit_works = commit_result.returncode == 0
        except subprocess.TimeoutExpired:
            commit_works = False

        # Test git diff command
        try:
            diff_result = subprocess.run(
                ['git', 'diff', '--name-only', '--diff-filter=AM', 'HEAD~1..HEAD'],
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=5
            )
            diff_works = diff_result.returncode == 0
        except subprocess.TimeoutExpired:
            diff_works = False

        # At least basic git functionality should work
        if getattr(pytest, 'is_git_repo', False):
            assert branch_works or commit_works, "At least one git command should work in git repo"

        # Record results for debugging
        print(f"Git commands compatibility: branch={branch_works}, commit={commit_works}, diff={diff_works}")

    @pytest.mark.asyncio
    async def test_git_error_handling(self, checkpoint_tool):
        """Test proper error handling for git operations."""
        # Test with invalid directory
        invalid_path = "/this/path/should/not/exist"

        branch, commit = await checkpoint_tool._get_git_info_safe(invalid_path)
        files = await checkpoint_tool._get_recently_modified_files_safe(invalid_path)

        # Should handle errors gracefully
        assert branch is None, "Should return None for invalid path"
        assert commit is None, "Should return None for invalid path"
        assert files == [], "Should return empty list for invalid path"

    @pytest.mark.asyncio
    async def test_git_timeout_handling(self, checkpoint_tool):
        """Test that git operations respect timeouts."""
        project_path = str(Path.cwd())

        # Test with reasonable timeout
        import time
        start_time = time.time()

        branch, commit = await checkpoint_tool._get_git_info_safe(project_path)
        files = await checkpoint_tool._get_recently_modified_files_safe(project_path)

        end_time = time.time()
        duration = end_time - start_time

        # Should complete within reasonable time (generous for CI environments)
        assert duration < 30.0, f"Git operations took too long: {duration}s"

        # Results should be valid types regardless of git availability
        assert branch is None or isinstance(branch, str)
        assert commit is None or isinstance(commit, str)
        assert isinstance(files, list)

    def test_git_version_info(self):
        """Test and record git version information for debugging."""
        if not getattr(pytest, 'git_available', False):
            pytest.skip("Git not available")

        try:
            result = subprocess.run(
                ['git', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                version_info = result.stdout.strip()
                print(f"Git version: {version_info}")

                # Extract version number for compatibility testing
                import re
                version_match = re.search(r'git version (\d+)\.(\d+)\.(\d+)', version_info)
                if version_match:
                    major, minor, patch = map(int, version_match.groups())

                    # Git 2.23+ has --show-current, older versions need different approach
                    supports_show_current = (major > 2) or (major == 2 and minor >= 23)
                    print(f"Git supports --show-current: {supports_show_current}")

            assert True, "Git version info collected"

        except Exception as e:
            pytest.skip(f"Could not get git version: {e}")


class TestGitEdgeCases:
    """Test git integration edge cases."""

    @pytest.mark.asyncio
    async def test_empty_repository(self):
        """Test behavior in empty git repository."""
        # This would need a temporary git repo setup
        # For now, just test that our methods handle edge cases

        # Create a temporary directory structure for testing
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Initialize empty git repo
            try:
                subprocess.run(['git', 'init'], cwd=tmp_dir, check=True, capture_output=True)
                subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_dir, check=True)
                subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_dir, check=True)

                # Test our methods with empty repo
                config = TuskConfig()
                mock_server = MagicMock()
                mock_server.config = config
                tool = EnhancedUnifiedCheckpointTool(mock_server)

                branch, commit = await tool._get_git_info_safe(tmp_dir)
                files = await tool._get_recently_modified_files_safe(tmp_dir)

                # In empty repo, might not have branch or commits
                # Should handle gracefully without errors
                assert branch is None or isinstance(branch, str)
                assert commit is None or isinstance(commit, str)
                assert isinstance(files, list)

            except (subprocess.CalledProcessError, FileNotFoundError):
                pytest.skip("Cannot create test git repository")

    def test_git_performance_benchmarks(self):
        """Benchmark git operations for performance monitoring."""
        if not getattr(pytest, 'git_available', False) or not getattr(pytest, 'is_git_repo', False):
            pytest.skip("Git repository not available for benchmarking")

        import time
        project_path = str(Path.cwd())

        # Benchmark individual git operations
        operations = []

        # Test git branch
        start = time.time()
        try:
            subprocess.run(['git', 'branch', '--show-current'],
                         cwd=project_path, capture_output=True, timeout=5)
            operations.append(('branch', time.time() - start))
        except Exception:
            pass

        # Test git commit
        start = time.time()
        try:
            subprocess.run(['git', 'rev-parse', '--short=8', 'HEAD'],
                         cwd=project_path, capture_output=True, timeout=5)
            operations.append(('commit', time.time() - start))
        except Exception:
            pass

        # Test git diff
        start = time.time()
        try:
            subprocess.run(['git', 'diff', '--name-only', '--diff-filter=AM', 'HEAD~1..HEAD'],
                         cwd=project_path, capture_output=True, timeout=5)
            operations.append(('diff', time.time() - start))
        except Exception:
            pass

        # Log performance results
        for operation, duration in operations:
            print(f"Git {operation} operation: {duration:.3f}s")
            # Ensure operations complete in reasonable time
            assert duration < 10.0, f"Git {operation} took too long: {duration}s"

        assert len(operations) > 0, "At least one git operation should succeed for benchmarking"


if __name__ == "__main__":
    # Allow running directly for development
    pytest.main([__file__, "-v"])