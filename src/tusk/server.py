"""Tusk FastMCP server with adaptive memory tools."""

import logging
import sys
from typing import Any

from fastmcp import FastMCP
from fastmcp.utilities.logging import get_logger

from .config import TuskConfig
from .storage import CheckpointStorage, PlanStorage, SearchEngine, TaskStorage

# Configure logging
logger = get_logger(__name__)


class TuskServer:
    """Tusk memory server using FastMCP 2.0."""

    def __init__(self, config: TuskConfig | None = None):
        self.config = config or TuskConfig.from_env()
        self.config.ensure_directories()

        # Initialize storage
        self.checkpoint_storage = CheckpointStorage(self.config)
        self.task_storage = TaskStorage(self.config)
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
                if stats.get("total_docs", 0) == 0 and self.search_engine.cleanup_locks(force=True):
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
# Tusk Memory System - Behavioral Instructions

Follow these steps for EVERY interaction:

1. **Session Start**: ALWAYS begin by using `recall(context="recent")` first
2. **Multiple Tasks**: Convert any list/numbered items to individual `task(action="add")` entries immediately  
3. **Complex Work**: Create a `plan` before starting any multi-step task (3+ steps)
4. **After Success**: Save `checkpoint` after completing significant work or solving problems
5. **Before Risk**: Save `checkpoint` before major changes, refactoring, or risky operations

## Trigger-Based Actions:
- User mentions "yesterday/last time/before" → Search with `recall` or `checkpoint(action="search")`
- User asks "what was I doing?" → Use `standup(timeframe="daily")`  
- User provides task list → Convert each item to `task(action="add")`
- Complex feature request → Create detailed `plan` with steps
- Work session ends → Save `checkpoint` with progress summary

## Critical Rules:
- NEVER start work without checking recent context first
- ALWAYS search before creating (avoid duplicates)  
- CAPTURE insights and breakthroughs immediately as checkpoints
- MAINTAIN task persistence across conversations

Your memory = their productivity. Use it religiously.
        """.strip()

    def _register_tools(self) -> None:
        """Register enhanced unified MCP tools with rich parameter descriptions."""
        # Import all enhanced tools
        from .tools.enhanced_all import (
            EnhancedUnifiedCheckpointTool,
            EnhancedUnifiedPlanTool,
            EnhancedUnifiedRecallTool,
            EnhancedUnifiedStandupTool,
        )
        from .tools.enhanced_unified import EnhancedUnifiedTaskTool
        from .tools.unified import UnifiedCleanupTool  # Keep original cleanup for now

        # Create enhanced tool instances with rich parameter descriptions
        plan_tool = EnhancedUnifiedPlanTool(self)
        task_tool = EnhancedUnifiedTaskTool(self)
        checkpoint_tool = EnhancedUnifiedCheckpointTool(self)
        recall_tool = EnhancedUnifiedRecallTool(self)
        standup_tool = EnhancedUnifiedStandupTool(self)
        # Keep cleanup tool available but don't register (testing period)
        cleanup_tool = UnifiedCleanupTool(self)
        self._cleanup_tool = cleanup_tool  # Store reference for potential manual use

        # Register enhanced tools in workflow order
        plan_tool.register(self.mcp)
        task_tool.register(self.mcp)
        checkpoint_tool.register(self.mcp)
        recall_tool.register(self.mcp)
        standup_tool.register(self.mcp)
        # cleanup_tool.register(self.mcp)  # Hidden during testing period

        logger.info("Registered 5 enhanced unified tools with rich parameter descriptions: plan, task, checkpoint, recall, standup")

    def run_stdio(self) -> None:
        """Run the server with stdio transport."""
        logger.info("Starting Tusk server with stdio transport")
        self.mcp.run(transport="stdio")

    async def run_sse(self, host: str = "localhost", port: int = 3001) -> None:
        """Run the server with SSE transport."""
        logger.info(f"Starting Tusk server with SSE transport on {host}:{port}")
        # MyPy thinks run() doesn't return a value, but it's actually an async method
        await self.mcp.run(transport="sse", host=host, port=port)  # type: ignore[func-returns-value]

    def get_workspace_stats(self) -> dict[str, Any]:
        """Get statistics about the current data."""
        return {
            "checkpoints": self.checkpoint_storage.count(),
            "tasks": self.task_storage.count(),
            "plans": self.plan_storage.count(),
            "search_stats": self.search_engine.get_index_stats(),
        }

    def cleanup_expired_data(self) -> dict[str, int]:
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
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stderr),
            logging.FileHandler(log_dir / "tusk.log", encoding="utf-8"),
        ],
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
