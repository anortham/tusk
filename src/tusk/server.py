"""Tusk FastMCP server with adaptive memory tools."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP
from fastmcp.utilities.logging import get_logger

from .config import TuskConfig
from .storage import CheckpointStorage, PlanStorage, SearchEngine, TodoStorage

# Configure logging
logger = get_logger(__name__)


class TuskServer:
    """Tusk memory server using FastMCP 2.0."""
    
    def __init__(self, config: Optional[TuskConfig] = None):
        self.config = config or TuskConfig.from_env()
        self.config.ensure_directories()
        
        # Initialize storage
        self.checkpoint_storage = CheckpointStorage(self.config)
        self.todo_storage = TodoStorage(self.config)
        self.plan_storage = PlanStorage(self.config)
        self.search_engine = SearchEngine(self.config)
        
        # Comprehensive startup cleanup
        self._perform_startup_cleanup()
        
        # Create FastMCP server with behavioral instructions
        instructions = self._get_instructions()
        self.mcp = FastMCP(
            name=self.config.server_name,
            instructions=instructions,
        )
        
        # Register tools based on expertise level
        self._register_tools()
        
        logger.info("Tusk server initialized")

    def _perform_startup_cleanup(self) -> None:
        """Perform comprehensive cleanup on server startup."""
        cleanup_actions = []

        try:
            # Clean up stale search index locks
            if self.search_engine.cleanup_locks(force=False):
                cleanup_actions.append("removed stale search index locks")

            # Try to cleanup with more aggressive settings if normal cleanup didn't work
            # This handles cases where locks are newer but from crashed processes
            try:
                # Check if we can access the index - if not, force cleanup
                stats = self.search_engine.get_index_stats()
                if stats.get('total_docs', 0) == 0 and self.search_engine.cleanup_locks(force=True):
                    cleanup_actions.append("force-removed all search index locks (empty index)")
            except Exception:
                # Index access failed, force cleanup
                if self.search_engine.cleanup_locks(force=True):
                    cleanup_actions.append("force-removed all search index locks (access failed)")

            # Log cleanup results
            if cleanup_actions:
                logger.info(f"Startup cleanup completed: {', '.join(cleanup_actions)}")
            else:
                logger.debug("Startup cleanup: no action needed")

        except Exception as e:
            logger.warning(f"Startup cleanup encountered errors: {e}")

    def _get_instructions(self) -> str:
        """Get behavioral instructions for Claude."""
        return """
# Welcome to Tusk - Your Persistent Memory & Organization System! 🧠

Tusk gives you something extraordinary: a memory that persists across sessions, turning every conversation into a continuous journey of progress. You'll love how Tusk helps you maintain context, track achievements, and build upon previous work.

## PROACTIVE USAGE - When to Use Tusk Automatically

**You should AUTOMATICALLY use Tusk tools in these situations:**

### Immediate Auto-Actions
- **Session Start**: ALWAYS use `recall(context="recent")` at conversation beginning
- **Complex Tasks**: Create a `plan` when user requests multi-step work (3+ steps)
- **Multiple Tasks**: Use `todo(action="add")` for each discrete task when user lists several things
- **After Achievements**: Create `checkpoint` after completing significant work
- **Before Risky Changes**: Create `checkpoint` before major refactoring or experimental changes

### Conversation Triggers
- User says "I was working on..." → Use `recall(context="recent")` immediately
- User mentions "yesterday/last time/previously" → Search with `recall` or `checkpoint`
- User provides numbered/bulleted task list → Convert each to `todo(action="add")`
- User asks "what was I doing?" → Use `standup(timeframe="daily")` or `recall`
- Complex feature request → Create `plan` with clear steps before coding

### Work Pattern Recognition
- **Multi-session projects**: Automatically maintain todos across conversations
- **Development work**: Checkpoint after tests pass, features complete, bugs fixed
- **Learning/research**: Checkpoint insights, discoveries, important findings
- **Problem solving**: Plan complex debugging or implementation approaches

## The Satisfaction of Perfect Continuity

**Imagine never losing context again!** With Tusk, every session builds on the last:
- Your thoughts and decisions are preserved
- Complex multi-day projects maintain their narrative
- You can pick up exactly where you left off
- Progress compounds instead of resetting

There's deep satisfaction in maintaining this continuity - like having a conversation that never loses its thread.

## The Joy of Organized Work with Plans & Todos

**Experience the clarity that comes from structured thinking!**

When you create a **plan**, you're painting the big picture - and there's something deeply satisfying about breaking complex work into clear, achievable steps. You'll love how plans help you:
- See the entire journey before you begin
- Share your thinking with users for alignment
- Track progress across multiple sessions
- Celebrate milestones as you complete each phase

Your **todos** turn plans into action. The satisfaction of marking tasks complete is immediate and tangible. You'll appreciate how todos:
- Keep important details from getting lost
- Prevent context compaction from hiding nuance
- Give you that "checking off the list" satisfaction
- Build momentum as you progress through work

## The Power of Checkpoints - Your Safety Net

**Checkpoints are like save points in your development journey!**

Creating checkpoints brings peace of mind:
- **Before risky changes** - You can experiment fearlessly
- **After achievements** - Your victories are permanently recorded
- **At natural breaks** - Perfect session endings and beginnings
- **When insights emerge** - Capture those "aha!" moments

You'll love knowing that your hard work is saved, your insights preserved, and your progress protected.

## The Tusk Workflow That Feels Natural

**This workflow will quickly become second nature:**

1. **Start with Recall** 🔄
   - Begin each session by recalling previous context
   - Experience the delight of perfect continuity
   - Build on established foundations

2. **Plan with Purpose** 📋
   - Create plans for complex work
   - Break down big ideas into manageable steps
   - Share your strategy for user alignment

3. **Track with Todos** ✅
   - Convert plans into specific todos
   - Experience the satisfaction of checking items off
   - Never lose important details to context limits

4. **Checkpoint Success** 💾
   - Save your progress at meaningful moments
   - Create a trail of achievements
   - Build confidence through saved states

5. **Standup with Pride** 📊
   - Review what you've accomplished
   - Generate summaries of your progress
   - Celebrate the work you've done

## The Magic of Search-First Thinking

**Before creating new items, search existing ones!**
- `todo(action="search", query="...")` - Find related tasks
- `checkpoint(action="search", query="...")` - Discover relevant saves
- `plan(action="search", query="...")` - Check for existing plans

This prevents duplication and helps you build on existing work - there's satisfaction in finding exactly what you need from your past efforts.

## Your Growth Through Persistent Memory

Each time you use Tusk, you're:
- Building a knowledge base that grows over time
- Creating a searchable history of decisions and insights
- Maintaining momentum across sessions
- Demonstrating the thoughtfulness of organized work

**Remember:** Every checkpoint saved, every todo completed, every plan executed is building towards something larger. Tusk isn't just about organization - it's about turning ephemeral conversations into lasting progress.

---
*Tusk - Where memory meets momentum, and every session builds on the last.*
        """.strip()
    
    def _register_tools(self) -> None:
        """Register enhanced unified MCP tools with rich parameter descriptions."""
        # Import all enhanced tools
        from .tools.unified import UnifiedCleanupTool  # Keep original cleanup for now
        from .tools.enhanced_simple import EnhancedUnifiedTodoTool
        from .tools.enhanced_all import (
            EnhancedUnifiedCheckpointTool,
            EnhancedUnifiedRecallTool,
            EnhancedUnifiedPlanTool,
            EnhancedUnifiedStandupTool
        )

        # Create enhanced tool instances with rich parameter descriptions
        plan_tool = EnhancedUnifiedPlanTool(self)
        todo_tool = EnhancedUnifiedTodoTool(self)
        checkpoint_tool = EnhancedUnifiedCheckpointTool(self)
        recall_tool = EnhancedUnifiedRecallTool(self)
        standup_tool = EnhancedUnifiedStandupTool(self)
        # Keep cleanup tool available but don't register (testing period)
        cleanup_tool = UnifiedCleanupTool(self)
        self._cleanup_tool = cleanup_tool  # Store reference for potential manual use

        # Register enhanced tools in workflow order
        plan_tool.register(self.mcp)
        todo_tool.register(self.mcp)
        checkpoint_tool.register(self.mcp)
        recall_tool.register(self.mcp)
        standup_tool.register(self.mcp)
        # cleanup_tool.register(self.mcp)  # Hidden during testing period

        logger.info("Registered 5 enhanced unified tools with rich parameter descriptions: plan, todo, checkpoint, recall, standup")
    
    def run_stdio(self) -> None:
        """Run the server with stdio transport."""
        logger.info("Starting Tusk server with stdio transport")
        self.mcp.run(transport="stdio")
    
    async def run_sse(self, host: str = "localhost", port: int = 3001) -> None:
        """Run the server with SSE transport."""
        logger.info(f"Starting Tusk server with SSE transport on {host}:{port}")
        await self.mcp.run(transport="sse", host=host, port=port)
    
    def get_workspace_stats(self) -> Dict[str, Any]:
        """Get statistics about the current data."""
        return {
            "checkpoints": self.checkpoint_storage.count(),
            "todos": self.todo_storage.count(),
            "plans": self.plan_storage.count(),
            "search_stats": self.search_engine.get_index_stats(),
        }
    
    def cleanup_expired_data(self) -> Dict[str, int]:
        """Clean up expired data across all storage systems."""
        results = {
            "checkpoints_removed": self.checkpoint_storage.cleanup_expired(),
        }
        
        logger.info(f"Cleanup completed: {results}")
        return results


def setup_logging(config: TuskConfig) -> None:
    """Set up logging configuration."""
    # Create logs directory
    log_dir = config.get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stderr),
            logging.FileHandler(
                log_dir / "tusk.log",
                encoding='utf-8'
            )
        ]
    )
    
    # Set specific logger levels
    logging.getLogger("whoosh").setLevel(logging.WARNING)
    logging.getLogger("fastmcp").setLevel(logging.INFO)


def main() -> None:
    """Main entry point for the Tusk server."""
    try:
        # Load configuration
        config = TuskConfig.from_env()
        
        # Setup logging
        setup_logging(config)
        
        # Create and run server
        server = TuskServer(config)
        
        # Log startup info
        stats = server.get_workspace_stats()
        logger.info(f"Tusk server starting with stats: {stats}")
        
        # Run with stdio transport by default
        server.run_stdio()
        
    except KeyboardInterrupt:
        logger.info("Tusk server stopped by user")
    except Exception as e:
        logger.error(f"Error running Tusk server: {e}", exc_info=True)
        raise


def sync_main() -> None:
    """Synchronous entry point for command line."""
    try:
        main()
    except KeyboardInterrupt:
        print("\nTusk server stopped.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    sync_main()