#!/usr/bin/env python3
"""Mimic the exact checkpoint tool flow to identify hanging point."""

import asyncio
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from tusk.models.checkpoint import Checkpoint
from tusk.config import TuskConfig
from tusk.storage.checkpoint_store import CheckpointStorage
from tusk.storage.search import SearchEngine


def get_git_info(project_path: str) -> tuple[Optional[str], Optional[str]]:
    """Get current git branch and commit hash - same as tool implementation."""
    try:
        import os
        if not project_path or not os.path.exists(project_path):
            return None, None

        print(f"  Getting git info for: {project_path}")

        # Get current branch
        print("  Running git branch --show-current...")
        branch_result = subprocess.run(
            ['git', 'branch', '--show-current'],
            capture_output=True,
            text=True,
            cwd=project_path,
            timeout=5
        )
        print(f"  Branch command result: {branch_result.returncode}")

        # Get current commit hash (short)
        print("  Running git rev-parse --short=8 HEAD...")
        commit_result = subprocess.run(
            ['git', 'rev-parse', '--short=8', 'HEAD'],
            capture_output=True,
            text=True,
            cwd=project_path,
            timeout=5
        )
        print(f"  Commit command result: {commit_result.returncode}")

        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
        commit = commit_result.stdout.strip() if commit_result.returncode == 0 else None

        print(f"  Git info: branch={branch}, commit={commit}")
        return branch, commit

    except Exception as e:
        print(f"  Git info error: {e}")
        return None, None


def get_recently_modified_files(project_path: str, max_files: int = 20) -> list[str]:
    """Get recently modified files - same as tool implementation."""
    try:
        import os
        if not project_path or not os.path.exists(project_path):
            return []

        print(f"  Getting recent files for: {project_path}")

        # Try git diff first
        print("  Running git diff --name-only...")
        cmd = [
            'git', 'diff', '--name-only',
            '--diff-filter=AM',  # Added or Modified
            'HEAD~1..HEAD'  # Since last commit
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=project_path,
            timeout=5
        )
        print(f"  Git diff result: {result.returncode}")

        if result.returncode == 0 and result.stdout.strip():
            files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
            print(f"  Found {len(files)} files from git diff")
            return files[:max_files]

        # Fallback: get recently modified files using Python (cross-platform)
        print("  Using Python pathlib fallback...")
        import time

        current_time = time.time()
        one_day_ago = current_time - (24 * 60 * 60)  # 24 hours ago
        recent_files = []

        project_pathlib = Path(project_path)

        # Walk through all files in the project
        for file_path in project_pathlib.rglob('*'):
            if file_path.is_file() and not str(file_path).startswith(str(project_pathlib / '.git')):
                try:
                    if file_path.stat().st_mtime > one_day_ago:
                        relative_path = file_path.relative_to(project_pathlib)
                        recent_files.append(str(relative_path))
                except (OSError, ValueError):
                    continue  # Skip files we can't access

        print(f"  Found {len(recent_files)} recent files")

        # Sort by modification time (newest first)
        try:
            recent_files.sort(key=lambda f: (Path(project_path) / f).stat().st_mtime,
                            reverse=True)
            print("  Files sorted by modification time")
        except (OSError, ValueError):
            # If sorting fails, just return the files as-is
            print("  Sorting failed, using unsorted list")
            pass

        return recent_files[:max_files]

    except Exception as e:
        print(f"  Recent files error: {e}")
        return []


async def test_checkpoint_tool_flow():
    """Test the exact flow used by the checkpoint tool."""
    print("Testing checkpoint tool flow...")

    description = "Test checkpoint using exact tool flow"

    # Step 1: Initialize storage
    print("1. Initializing storage...")
    config = TuskConfig()
    checkpoint_storage = CheckpointStorage(config)
    search_engine = SearchEngine(config)
    print("   Storage initialized")

    # Step 2: Get current project context
    print("2. Getting project context...")
    project_id = config.get_current_project_id()
    project_path = config.get_current_project_path()
    print(f"   Project ID: {project_id}")
    print(f"   Project path: {project_path}")

    # Step 3: Get git context (this might hang)
    print("3. Getting git context...")
    git_branch, git_commit = get_git_info(project_path)
    print("   Git context retrieved")

    # Step 4: Get recently modified files (this might hang)
    print("4. Getting recently modified files...")
    active_files = get_recently_modified_files(project_path)
    print(f"   Found {len(active_files)} active files")

    # Step 5: Build work context
    print("5. Building work context...")
    context_parts = [f"Progress: {description}"]
    if git_branch:
        context_parts.append(f"Branch: {git_branch}")
    if git_commit:
        context_parts.append(f"Commit: {git_commit}")
    if active_files:
        files_str = ", ".join(active_files[:5])
        if len(active_files) > 5:
            files_str += f" (and {len(active_files) - 5} more)"
        context_parts.append(f"Active files: {files_str}")
    work_context = "\n".join(context_parts)
    print("   Work context built")

    # Step 6: Create checkpoint
    print("6. Creating checkpoint...")
    checkpoint = Checkpoint(
        workspace_id="",
        project_id=project_id,
        project_path=project_path,
        description=description,
        session_id=f"session_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        git_branch=git_branch,
        git_commit=git_commit,
        work_context=work_context,
        active_files=active_files[:10],  # Limit to top 10 files
    )
    print(f"   Checkpoint created: {checkpoint.id}")

    # Step 7: Save checkpoint
    print("7. Saving checkpoint...")
    saved = checkpoint_storage.save(checkpoint)
    print(f"   Saved: {saved}")

    # Step 8: Index checkpoint
    print("8. Indexing checkpoint...")
    search_engine.index_checkpoint(checkpoint)
    print("   Indexed")

    # Step 9: Create response
    print("9. Creating JSON response...")
    response = {
        "success": True,
        "action": "progress_saved",
        "checkpoint": {
            "id": checkpoint.id,
            "description": description,
            "project_id": checkpoint.project_id,
            "created_at": checkpoint.created_at.strftime("%Y-%m-%d %H:%M"),
            "session_id": checkpoint.session_id
        }
    }
    json_response = json.dumps(response, ensure_ascii=False, indent=2)
    print(f"   Response created: {len(json_response)} chars")

    print("Checkpoint tool flow completed successfully!")
    return json_response


if __name__ == "__main__":
    result = asyncio.run(test_checkpoint_tool_flow())
    print(f"\nFinal result:\n{result}")