#!/usr/bin/env python3
"""Debug file detection hanging issues."""

import subprocess
import sys
import time
import os
from pathlib import Path
from typing import Optional, List


def test_exact_file_detection_method():
    """Test the exact file detection method that's hanging."""
    print("=== Exact File Detection Method Test ===")

    def get_recently_modified_files_exact(project_path: str, max_files: int = 20) -> List[str]:
        """Exact copy of the hanging method."""
        try:
            import subprocess
            import os
            if not project_path or not os.path.exists(project_path):
                print(f"Project path invalid: {project_path}")
                return []

            print(f"Testing file detection in: {project_path}")
            print(f"Max files: {max_files}")

            # Get files modified in last 24 hours, sorted by modification time
            cmd = [
                'git', 'diff', '--name-only',
                '--diff-filter=AM',  # Added or Modified
                'HEAD~1..HEAD'  # Since last commit
            ]

            print(f"Running command: {' '.join(cmd)}")
            start_time = time.time()

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=5
            )

            end_time = time.time()
            print(f"Git diff completed in {end_time - start_time:.3f} seconds")
            print(f"Return code: {result.returncode}")
            print(f"Stderr: '{result.stderr.strip()}'")

            if result.returncode == 0 and result.stdout.strip():
                files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
                print(f"Found {len(files)} files from git diff")
                print(f"Sample files: {files[:5]}")
                return files[:max_files]

            # Fallback: skip file detection to avoid hanging on large directories
            print("Git diff failed, skipping file detection fallback")
            return []

        except subprocess.TimeoutExpired as e:
            print(f"TIMEOUT in file detection: {e}")
            return []
        except Exception as e:
            print(f"ERROR in file detection: {e}")
            return []

    try:
        print("Calling get_recently_modified_files_exact...")
        files = get_recently_modified_files_exact(str(Path.cwd()))
        print(f"Method returned {len(files)} files: {files[:3]}")
    except Exception as e:
        print(f"Method raised exception: {e}")


def test_mcp_context_simulation():
    """Simulate calling git commands in the context similar to MCP server."""
    print("\n=== MCP Context Simulation Test ===")

    # Simulate the full checkpoint flow without actual storage
    def simulate_checkpoint_save(description: str):
        """Simulate the checkpoint save process."""
        print(f"Simulating checkpoint save: '{description}'")

        try:
            # Step 1: Get project context (this works)
            project_path = str(Path.cwd())
            print(f"1. Project path: {project_path}")

            # Step 2: Get git info (test this in sequence)
            print("2. Getting git info...")
            start_time = time.time()

            branch_result = subprocess.run(
                ['git', 'branch', '--show-current'],
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=5
            )

            commit_result = subprocess.run(
                ['git', 'rev-parse', '--short=8', 'HEAD'],
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=5
            )

            end_time = time.time()
            print(f"   Git info completed in {end_time - start_time:.3f} seconds")

            branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
            commit = commit_result.stdout.strip() if commit_result.returncode == 0 else None
            print(f"   Results: branch='{branch}', commit='{commit}'")

            # Step 3: Get files (test this in sequence)
            print("3. Getting recently modified files...")
            start_time = time.time()

            files_result = subprocess.run([
                'git', 'diff', '--name-only',
                '--diff-filter=AM',
                'HEAD~1..HEAD'
            ],
            capture_output=True,
            text=True,
            cwd=project_path,
            timeout=5)

            end_time = time.time()
            print(f"   File detection completed in {end_time - start_time:.3f} seconds")

            files = []
            if files_result.returncode == 0 and files_result.stdout.strip():
                files = [f.strip() for f in files_result.stdout.strip().split('\n') if f.strip()][:20]

            print(f"   Found {len(files)} files")

            # Step 4: Build work context
            print("4. Building work context...")
            context_parts = [f"Progress: {description}"]
            if branch:
                context_parts.append(f"Branch: {branch}")
            if commit:
                context_parts.append(f"Commit: {commit}")
            if files:
                files_str = ", ".join(files[:5])
                if len(files) > 5:
                    files_str += f" (and {len(files) - 5} more)"
                context_parts.append(f"Active files: {files_str}")

            work_context = "\n".join(context_parts)
            print(f"   Context: {len(work_context)} chars")

            print("5. Simulation completed successfully!")
            return {
                "success": True,
                "branch": branch,
                "commit": commit,
                "files_count": len(files),
                "context_length": len(work_context)
            }

        except subprocess.TimeoutExpired as e:
            print(f"TIMEOUT in simulation: {e}")
            return {"success": False, "error": "timeout"}
        except Exception as e:
            print(f"ERROR in simulation: {e}")
            return {"success": False, "error": str(e)}

    # Run the simulation
    result = simulate_checkpoint_save("Test simulation")
    print(f"Simulation result: {result}")


def test_concurrent_git_calls():
    """Test if multiple concurrent git calls cause issues."""
    print("\n=== Concurrent Git Calls Test ===")

    import threading
    import time

    results = []
    errors = []

    def run_git_command(command_name, cmd):
        """Run a git command and record results."""
        try:
            start_time = time.time()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(Path.cwd()),
                timeout=10
            )
            end_time = time.time()
            results.append({
                "command": command_name,
                "duration": end_time - start_time,
                "returncode": result.returncode,
                "success": True
            })
            print(f"{command_name} completed in {end_time - start_time:.3f}s")
        except Exception as e:
            errors.append({
                "command": command_name,
                "error": str(e)
            })
            print(f"{command_name} failed: {e}")

    # Start multiple git commands concurrently
    threads = []
    commands = [
        ("branch", ['git', 'branch', '--show-current']),
        ("commit", ['git', 'rev-parse', '--short=8', 'HEAD']),
        ("diff", ['git', 'diff', '--name-only', '--diff-filter=AM', 'HEAD~1..HEAD']),
        ("status", ['git', 'status', '--porcelain'])
    ]

    print("Starting concurrent git commands...")
    start_time = time.time()

    for cmd_name, cmd in commands:
        thread = threading.Thread(target=run_git_command, args=(cmd_name, cmd))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join(timeout=15)  # 15 second timeout per thread

    end_time = time.time()
    print(f"All concurrent commands completed in {end_time - start_time:.3f}s")
    print(f"Successful commands: {len(results)}")
    print(f"Failed commands: {len(errors)}")

    if errors:
        print("Errors:")
        for error in errors:
            print(f"  {error['command']}: {error['error']}")


if __name__ == "__main__":
    print("File Detection Hanging Debug Test Suite")
    print("=" * 60)

    test_exact_file_detection_method()
    test_mcp_context_simulation()
    test_concurrent_git_calls()

    print("\n" + "=" * 60)
    print("File detection test suite completed!")