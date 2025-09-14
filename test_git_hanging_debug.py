#!/usr/bin/env python3
"""Debug git subprocess hanging issues with detailed analysis."""

import subprocess
import sys
import time
import os
from pathlib import Path
from typing import Optional, Tuple


def test_git_command_isolation():
    """Test each git command in isolation with detailed timing and logging."""
    print("=== Git Command Isolation Test ===")

    project_path = str(Path.cwd())
    print(f"Testing in directory: {project_path}")
    print(f"Directory exists: {os.path.exists(project_path)}")
    print(f"Is git repository: {os.path.exists(os.path.join(project_path, '.git'))}")

    # Test 1: git branch --show-current
    print("\n--- Test 1: git branch --show-current ---")
    try:
        start_time = time.time()
        print("Starting git branch command...")

        result = subprocess.run(
            ['git', 'branch', '--show-current'],
            capture_output=True,
            text=True,
            cwd=project_path,
            timeout=5
        )

        end_time = time.time()
        print(f"Command completed in {end_time - start_time:.3f} seconds")
        print(f"Return code: {result.returncode}")
        print(f"Stdout: '{result.stdout.strip()}'")
        print(f"Stderr: '{result.stderr.strip()}'")

    except subprocess.TimeoutExpired as e:
        print(f"TIMEOUT after 5 seconds: {e}")
    except Exception as e:
        print(f"ERROR: {e}")

    # Test 2: git rev-parse --short=8 HEAD
    print("\n--- Test 2: git rev-parse --short=8 HEAD ---")
    try:
        start_time = time.time()
        print("Starting git rev-parse command...")

        result = subprocess.run(
            ['git', 'rev-parse', '--short=8', 'HEAD'],
            capture_output=True,
            text=True,
            cwd=project_path,
            timeout=5
        )

        end_time = time.time()
        print(f"Command completed in {end_time - start_time:.3f} seconds")
        print(f"Return code: {result.returncode}")
        print(f"Stdout: '{result.stdout.strip()}'")
        print(f"Stderr: '{result.stderr.strip()}'")

    except subprocess.TimeoutExpired as e:
        print(f"TIMEOUT after 5 seconds: {e}")
    except Exception as e:
        print(f"ERROR: {e}")


def test_git_diff_command():
    """Test the git diff command used for file detection."""
    print("\n=== Git Diff Command Test ===")

    project_path = str(Path.cwd())

    # Test git diff command
    print("\n--- Test: git diff --name-only --diff-filter=AM HEAD~1..HEAD ---")
    try:
        start_time = time.time()
        print("Starting git diff command...")

        result = subprocess.run([
            'git', 'diff', '--name-only',
            '--diff-filter=AM',  # Added or Modified
            'HEAD~1..HEAD'  # Since last commit
        ],
        capture_output=True,
        text=True,
        cwd=project_path,
        timeout=5)

        end_time = time.time()
        print(f"Command completed in {end_time - start_time:.3f} seconds")
        print(f"Return code: {result.returncode}")
        print(f"Stdout lines: {len(result.stdout.strip().split(chr(10))) if result.stdout.strip() else 0}")
        if result.stdout.strip():
            files = result.stdout.strip().split('\n')[:5]  # Show first 5 files
            print(f"Sample files: {files}")
        print(f"Stderr: '{result.stderr.strip()}'")

    except subprocess.TimeoutExpired as e:
        print(f"TIMEOUT after 5 seconds: {e}")
    except Exception as e:
        print(f"ERROR: {e}")


def test_subprocess_timeout_behavior():
    """Test if subprocess timeout is working correctly."""
    print("\n=== Subprocess Timeout Behavior Test ===")

    # Test with a command that should timeout (ping with long timeout)
    print("\n--- Test: Intentional timeout with ping ---")
    try:
        start_time = time.time()
        print("Starting ping command that should timeout...")

        # Use a command that will definitely take longer than 2 seconds
        result = subprocess.run(
            ['ping', '-n', '10', '127.0.0.1'],  # Windows ping 10 times
            capture_output=True,
            text=True,
            timeout=2  # 2 second timeout
        )

        end_time = time.time()
        print(f"Unexpectedly completed in {end_time - start_time:.3f} seconds")

    except subprocess.TimeoutExpired as e:
        end_time = time.time()
        print(f"CORRECTLY timed out after {end_time - start_time:.3f} seconds")
        print(f"Timeout exception: {e}")
    except Exception as e:
        print(f"ERROR: {e}")


def test_git_repository_state():
    """Test the state of the git repository."""
    print("\n=== Git Repository State Test ===")

    project_path = Path.cwd()

    print(f"Current working directory: {project_path}")
    print(f".git directory exists: {(project_path / '.git').exists()}")

    # Check git status
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            cwd=str(project_path),
            timeout=5
        )
        print(f"Git status return code: {result.returncode}")
        if result.returncode == 0:
            status_lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
            print(f"Git status shows {len(status_lines)} changed files")
        else:
            print(f"Git status error: {result.stderr}")
    except Exception as e:
        print(f"Git status failed: {e}")

    # Check git log to see if we have commits
    try:
        result = subprocess.run(
            ['git', 'log', '--oneline', '-5'],
            capture_output=True,
            text=True,
            cwd=str(project_path),
            timeout=5
        )
        print(f"Git log return code: {result.returncode}")
        if result.returncode == 0:
            log_lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
            print(f"Repository has {len(log_lines)} recent commits")
            if log_lines:
                print(f"Latest commit: {log_lines[0]}")
        else:
            print(f"Git log error: {result.stderr}")
    except Exception as e:
        print(f"Git log failed: {e}")


def test_original_git_info_function():
    """Test the exact implementation from the hanging method."""
    print("\n=== Original Git Info Function Test ===")

    def get_git_info_exact(project_path: str) -> Tuple[Optional[str], Optional[str]]:
        """Exact copy of the hanging method."""
        try:
            import subprocess
            import os
            if not project_path or not os.path.exists(project_path):
                return None, None

            print(f"Testing with project_path: {project_path}")

            # Get current branch
            print("Getting current branch...")
            branch_result = subprocess.run(
                ['git', 'branch', '--show-current'],
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=5
            )
            print(f"Branch result: returncode={branch_result.returncode}")

            # Get current commit hash (short)
            print("Getting current commit...")
            commit_result = subprocess.run(
                ['git', 'rev-parse', '--short=8', 'HEAD'],
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=5
            )
            print(f"Commit result: returncode={commit_result.returncode}")

            branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
            commit = commit_result.stdout.strip() if commit_result.returncode == 0 else None

            print(f"Final results: branch='{branch}', commit='{commit}'")
            return branch, commit

        except Exception as e:
            print(f"Exception in get_git_info_exact: {e}")
            return None, None

    try:
        print("Calling get_git_info_exact...")
        branch, commit = get_git_info_exact(str(Path.cwd()))
        print(f"Function returned: branch='{branch}', commit='{commit}'")
    except Exception as e:
        print(f"Function raised exception: {e}")


if __name__ == "__main__":
    print("Git Hanging Debug Test Suite")
    print("=" * 50)

    test_subprocess_timeout_behavior()
    test_git_repository_state()
    test_git_command_isolation()
    test_git_diff_command()
    test_original_git_info_function()

    print("\n" + "=" * 50)
    print("Test suite completed!")