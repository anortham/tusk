#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///

"""
Tusk Pre-Compact Hook

Automatically saves a checkpoint before compaction starts to preserve context.
This prevents loss of work progress when Claude Code compacts the conversation.

Key Features:
- Quick checkpoint save before compaction
- Non-blocking execution (returns immediately)
- Works for both auto and manual compaction
- Preserves recent work state
"""

import argparse
import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


def quick_checkpoint(trigger_type: str) -> bool:
    """Create a quick checkpoint using Tusk server.
    
    Args:
        trigger_type: "auto" or "manual" compaction trigger
        
    Returns:
        bool: True if checkpoint was saved successfully
    """
    try:
        # Import here to avoid startup delays
        import asyncio
        sys.path.insert(0, str(Path.cwd() / "src"))
        
        from tusk.server import TuskServer
        from tusk.config import TuskConfig
        from tusk.models.checkpoint import Checkpoint
        
        async def save_checkpoint():
            # Quick config and server setup
            config = TuskConfig.from_env()
            server = TuskServer(config)
            
            # Create pre-compaction checkpoint
            description = f"Pre-compaction checkpoint ({trigger_type})"
            
            checkpoint = Checkpoint(
                workspace_id=config.current_workspace,
                description=description,
                work_context="Automatically saved before compaction to preserve context",
                session_id=f"pre_compact_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            )
            
            # Set shorter TTL for pre-compaction checkpoints (24 hours)
            checkpoint.set_ttl(24 * 60 * 60)  # 24 hours in seconds
            
            # Save checkpoint
            if server.checkpoint_storage.save(checkpoint):
                # Index for search
                server.search_engine.index_checkpoint(checkpoint)
                return True
            return False
        
        # Run async checkpoint save
        result = asyncio.run(save_checkpoint())
        return result
        
    except Exception as e:
        print(f"Error creating pre-compaction checkpoint: {e}", file=sys.stderr)
        return False


def main():
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description="Tusk pre-compact hook")
        parser.add_argument('--save-checkpoint', action='store_true', default=True,
                          help='Save checkpoint before compaction (default: True)')
        parser.add_argument('--verbose', action='store_true',
                          help='Print verbose output')
        args = parser.parse_args()
        
        # Read JSON input from stdin
        input_data = json.loads(sys.stdin.read())
        
        # Extract trigger type
        trigger = input_data.get('trigger', 'unknown')  # "manual" or "auto"
        session_id = input_data.get('session_id', 'unknown')
        
        if args.verbose:
            if trigger == "manual":
                print(f"📋 Manual compaction initiated (session: {session_id[:8]}...)")
            else:
                print(f"🔄 Auto-compaction triggered - context window full (session: {session_id[:8]}...)")
        
        # Save checkpoint if enabled
        if args.save_checkpoint:
            if args.verbose:
                print("📸 Saving quick checkpoint before compaction...")
            
            success = quick_checkpoint(trigger)
            
            if args.verbose:
                if success:
                    print("✅ Checkpoint saved successfully")
                else:
                    print("❌ Failed to save checkpoint")
        
        # Log the event (basic logging)
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "pre_compact",
            "trigger": trigger,
            "session_id": session_id,
            "checkpoint_saved": success if args.save_checkpoint else False
        }
        
        # Append to log file
        log_file = log_dir / 'tusk_hooks.json'
        if log_file.exists():
            with open(log_file, 'r') as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    logs = []
        else:
            logs = []
        
        logs.append(log_entry)
        
        with open(log_file, 'w') as f:
            json.dump(logs, f, indent=2)
        
        if args.verbose:
            print(f"📝 Event logged to {log_file}")
        
        # Return success (allows compaction to proceed)
        sys.exit(0)
        
    except json.JSONDecodeError:
        # Handle JSON decode errors gracefully
        print("Warning: Could not parse hook input", file=sys.stderr)
        sys.exit(0)
    except KeyboardInterrupt:
        print("Hook interrupted", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Hook error: {e}", file=sys.stderr)
        # Don't fail compaction due to hook errors
        sys.exit(0)


if __name__ == '__main__':
    main()