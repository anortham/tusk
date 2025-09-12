"""Checkpoint tools for saving work context."""

from datetime import timezone
import logging
from datetime import datetime
from typing import List, Optional

from ..models.checkpoint import Checkpoint
from ..models.highlight import Highlight, HighlightCategory, HighlightImportance
from .base import BaseTool

logger = logging.getLogger(__name__)


class CheckpointTool(BaseTool):
    """Tools for managing checkpoints - work context snapshots."""
    
    def register(self, mcp_server) -> None:
        """Register checkpoint tools with the MCP server."""
        
        # Simple save progress
        @mcp_server.tool
        async def save_progress(description: str) -> str:
            """Save current work progress with a description.
            
            BEHAVIORAL GUIDANCE: Use when completing significant work, solving problems,
            or reaching natural stopping points. Create descriptive checkpoints that
            capture key decisions, discoveries, or state changes for future context.
            
            DECISION LOGIC: Trigger automatically when user indicates completion
            ("I'm done with", "finished", "completed") or when switching contexts.
            """
            try:
                checkpoint = Checkpoint(
                    workspace_id=self.get_current_workspace(),
                    description=description,
                    session_id=f"session_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                )
                
                # Set default TTL
                checkpoint.set_ttl(self.config.default_checkpoint_ttl)
                
                # Save checkpoint
                if self.checkpoint_storage.save(checkpoint):
                    # Index for search
                    self.search_engine.index_checkpoint(checkpoint)
                    
                    logger.info(f"Created checkpoint {checkpoint.id}")
                    return f"✅ Saved progress: {description}\\n\\nCheckpoint ID: {checkpoint.id}"
                else:
                    return f"❌ Failed to save progress"
                    
            except Exception as e:
                logger.error(f"Error saving progress: {e}")
                return f"❌ Error saving progress: {e}"
        
        # List recent checkpoints
        @mcp_server.tool
        async def list_recent_saves(limit: int = 5) -> str:
            """List recent saved progress checkpoints.
            
            BEHAVIORAL GUIDANCE: Use when user asks about recent work history or
            when you need to understand what was accomplished recently.
            """
            try:
                checkpoints = self.checkpoint_storage.list_recent(limit)
                
                if not checkpoints:
                    return "No saved progress found."
                
                result = f"📚 Recent Progress ({len(checkpoints)} items):\\n\\n"
                
                for i, checkpoint in enumerate(checkpoints, 1):
                    created = checkpoint.created_at.strftime("%Y-%m-%d %H:%M")
                    result += f"{i}. [{created}] {checkpoint.description}\\n"
                    result += f"   ID: {checkpoint.id}\\n\\n"
                
                return result
                
            except Exception as e:
                logger.error(f"Error listing checkpoints: {e}")
                return f"❌ Error listing progress: {e}"
        
        # Search checkpoints
        @mcp_server.tool
        async def search_checkpoints(query: str, limit: int = 10) -> str:
            """Search checkpoints by content using full-text search.
            
            BEHAVIORAL GUIDANCE: Use when user asks about specific topics, problems,
            or decisions from past work. More precise than browsing recent lists.
            """
            try:
                results = self.search_engine.search(
                    query=query,
                    limit=limit,
                    doc_types=["checkpoint"]
                )
                
                if not results:
                    return f"No checkpoints found for query: '{query}'"
                
                result = f"🔍 Search Results for '{query}' ({len(results)} found):\\n\\n"
                
                for i, search_result in enumerate(results, 1):
                    checkpoint = self.checkpoint_storage.load(search_result.doc_id)
                    if checkpoint:
                        created = checkpoint.created_at.strftime("%Y-%m-%d %H:%M")
                        result += f"**{i}. {checkpoint.description}** (score: {search_result.score:.2f})\\n"
                        result += f"   ID: `{checkpoint.id}`\\n"
                        result += f"   Created: {created}\\n\\n"
                
                return result
                
            except Exception as e:
                logger.error(f"Error searching checkpoints: {e}")
                return f"❌ Error searching checkpoints: {e}"