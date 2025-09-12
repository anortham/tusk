"""Test timezone comparison fixes."""

import pytest
from datetime import datetime, timezone, timedelta
from src.tusk.models.checkpoint import Checkpoint
from src.tusk.storage.checkpoint_store import CheckpointStorage
from src.tusk.tools.recall import RecallTool
from src.tusk.server import TuskServer
import tempfile
import json
from pathlib import Path


@pytest.mark.asyncio
async def test_mixed_timezone_checkpoint_sorting():
    """Test that checkpoints with mixed timezone formats can be sorted."""
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create fake checkpoint files with mixed timezone formats
        checkpoint_dir = temp_path / "default" / "checkpoints" / "2025-09-12"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Create timezone-naive checkpoint (old format)
        naive_checkpoint = {
            "id": "naive-checkpoint",
            "workspace_id": "default",
            "session_id": "session_1",
            "description": "Naive timezone checkpoint",
            "work_context": None,
            "active_files": [],
            "highlights": [],
            "git_branch": None,
            "git_commit": None,
            "is_global": False,
            "tags": [],
            "created_at": "2025-09-12T14:00:00.000000",  # No timezone
            "updated_at": None,
            "ttl_expiry": "2025-09-19T14:00:00.000000"
        }
        
        # Create timezone-aware checkpoint (new format)
        aware_checkpoint = {
            "id": "aware-checkpoint", 
            "workspace_id": "default",
            "session_id": "session_2",
            "description": "Timezone aware checkpoint",
            "work_context": None,
            "active_files": [],
            "highlights": [],
            "git_branch": None,
            "git_commit": None,
            "is_global": False,
            "tags": [],
            "created_at": "2025-09-12T15:00:00.000000+00:00",  # With timezone
            "updated_at": None,
            "ttl_expiry": "2025-09-19T15:00:00.000000+00:00"
        }
        
        # Save both checkpoint files
        with open(checkpoint_dir / "naive-checkpoint.json", "w") as f:
            json.dump(naive_checkpoint, f, indent=2)
            
        with open(checkpoint_dir / "aware-checkpoint.json", "w") as f:
            json.dump(aware_checkpoint, f, indent=2)
        
        # Now try to load and sort them using checkpoint storage
        from src.tusk.config import TuskConfig
        config = TuskConfig(data_dir=temp_path)
        storage = CheckpointStorage(config)
        
        # This should fail with timezone comparison error if not fixed
        checkpoints = storage.list_by_date_range(
            start_date=datetime.now(timezone.utc) - timedelta(days=1),
            end_date=datetime.now(timezone.utc)
        )
        
        # Should not raise an exception and should return both checkpoints
        assert len(checkpoints) == 2


@pytest.mark.asyncio  
async def test_recall_with_mixed_timezone_data():
    """Test that recall works with mixed timezone checkpoint data."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Set up similar mixed data as above
        checkpoint_dir = temp_path / "default" / "checkpoints" / "2025-09-12"  
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        naive_checkpoint = {
            "id": "naive-recall-test",
            "workspace_id": "default", 
            "session_id": "session_recall",
            "description": "Test naive checkpoint for recall",
            "work_context": None,
            "active_files": [],
            "highlights": [],
            "git_branch": None,
            "git_commit": None,
            "is_global": False,
            "tags": [],
            "created_at": "2025-09-12T14:30:00.000000",  # No timezone
            "updated_at": None,
            "ttl_expiry": "2025-09-19T14:30:00.000000"
        }
        
        with open(checkpoint_dir / "naive-recall-test.json", "w") as f:
            json.dump(naive_checkpoint, f, indent=2)
        
        # Create a test server with our temp directory
        from src.tusk.config import TuskConfig
        config = TuskConfig(data_dir=temp_path)
        server = TuskServer(config)
        recall_tool = RecallTool(server)
        
        # This should work without timezone comparison errors
        result = await recall_tool._build_recall_context(
            days_back=2,
            include_todos=True,
            include_plans=True, 
            include_checkpoints=True,
            session_id=None,
            git_branch=None
        )
        
        # Should successfully build context
        assert result is not None
        assert len(result["checkpoints"]) == 1