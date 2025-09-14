#!/usr/bin/env python3
"""Test async checkpoint functionality to debug hanging issue."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from tusk.models.checkpoint import Checkpoint
from tusk.config import TuskConfig
from tusk.storage.checkpoint_store import CheckpointStorage
from tusk.storage.search import SearchEngine
from datetime import datetime, timezone


async def test_async_checkpoint():
    """Test async checkpoint creation."""
    print("Starting async checkpoint test...")

    config = TuskConfig()
    checkpoint_storage = CheckpointStorage(config)
    search_engine = SearchEngine(config)

    # Create checkpoint
    checkpoint = Checkpoint(
        workspace_id="",
        project_id="async-test",
        project_path=str(Path.cwd()),
        description="Async test checkpoint",
        session_id=f"session_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        git_branch=None,
        git_commit=None,
        work_context="Async test context",
        active_files=[]
    )

    print(f"Created checkpoint: {checkpoint.id}")

    # Test each step that could hang
    print("1. Saving to storage...")
    saved = checkpoint_storage.save(checkpoint)
    print(f"   Storage save result: {saved}")

    print("2. Indexing in search engine...")
    search_engine.index_checkpoint(checkpoint)
    print("   Search indexing completed")

    print("3. Creating JSON response...")
    import json
    response = {
        "success": True,
        "action": "progress_saved",
        "checkpoint": {
            "id": checkpoint.id,
            "description": checkpoint.description,
            "created_at": checkpoint.created_at.strftime("%Y-%m-%d %H:%M"),
        }
    }
    json_response = json.dumps(response, ensure_ascii=False, indent=2)
    print(f"   JSON response length: {len(json_response)}")

    print("Async checkpoint test completed successfully!")
    return json_response


if __name__ == "__main__":
    result = asyncio.run(test_async_checkpoint())
    print(f"Final result: {result[:100]}...")