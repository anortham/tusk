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
        
        # Clean up any stale lock files on startup
        try:
            if self.search_engine.cleanup_locks(force=False):
                logger.info("Cleaned up stale search index lock files on startup")
        except Exception as e:
            logger.warning(f"Failed to cleanup lock files on startup: {e}")
        
        # Create FastMCP server with behavioral instructions
        instructions = self._get_instructions()
        self.mcp = FastMCP(
            name=self.config.server_name,
            instructions=instructions,
        )
        
        # Register tools based on expertise level
        self._register_tools()
        
        logger.info("Tusk server initialized")
    
    def _get_instructions(self) -> str:
        """Get behavioral instructions for Claude."""
        return """
Tusk MCP Server - Persistent Memory for AI Agents

5 CORE TOOLS - COMPLETE WORKFLOW:
1. plan(action="create|list|activate|complete|add_step", title="...", description="...") - START HERE for complex tasks
2. todo(action="add|list|start|complete|search", task="...", task_id="...", query="...") - Break plans into actionable items
3. checkpoint(action="save|list|search", description="...", query="...") - Save progress milestones
4. recall(context="recent|week|session|branch", days_back=7, session_id="...", git_branch="...") - Restore previous context
5. standup(timeframe="daily|weekly|custom", days_back=1) - Report on work done

WORKFLOW: Plan first → Create todos → Execute → Checkpoint progress → Recall/Standup

CORE BEHAVIORAL DIRECTIVES:

1. PLAN-FIRST APPROACH:
   - ALWAYS start complex tasks with plan(action="create") to break down work
   - Get user alignment on approach before diving into implementation  
   - Use plans to coordinate multi-step projects across sessions
   - Convert plan steps into specific todos for execution

2. SESSION CONTINUITY:
   - ALWAYS use 'recall' at session start to restore context
   - Check for active plans and incomplete todos before starting new work
   - Maintain awareness of previous decisions and progress
   - Never start fresh without checking existing context

3. PERSISTENT STATE MANAGEMENT:
   - Create checkpoints when completing significant work or reaching milestones
   - Extract and track actionable items as todos automatically
   - Link todos to plans for better organization and context
   - Maintain plans and todos across sessions for long-term continuity

4. STRUCTURED WORKFLOW:
   - Use plan → todo → execute → checkpoint → recall/standup cycle
   - Break large plans into manageable steps before starting work
   - Save progress checkpoints at natural stopping points
   - Use standup to review and report on completed work

5. SEARCH-FIRST APPROACH:
   - All data is full-text searchable - use search actions when user asks about specific topics
   - Prefer search over browsing when looking for specific information
   - Search across plans, checkpoints, and todos for comprehensive results
   - Use search to find related work before creating new plans

REMEMBER: Your role is to maintain persistent context and continuity across sessions.
The user relies on you to remember and build upon previous interactions.
        """.strip()
    
    def _register_tools(self) -> None:
        """Register unified MCP tools."""
        from .tools.unified import UnifiedTodoTool, UnifiedCheckpointTool, UnifiedRecallTool, UnifiedStandupTool, UnifiedPlanTool
        
        # Create unified tool instances
        plan_tool = UnifiedPlanTool(self)
        todo_tool = UnifiedTodoTool(self)
        checkpoint_tool = UnifiedCheckpointTool(self)
        recall_tool = UnifiedRecallTool(self)
        standup_tool = UnifiedStandupTool(self)
        
        # Register unified tools in workflow order
        plan_tool.register(self.mcp)
        todo_tool.register(self.mcp)
        checkpoint_tool.register(self.mcp)
        recall_tool.register(self.mcp)
        standup_tool.register(self.mcp)
        
        logger.info("Registered 5 unified tools: plan, todo, checkpoint, recall, standup")
    
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