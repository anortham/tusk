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
        
        # Create FastMCP server with behavioral instructions
        instructions = self._get_instructions()
        self.mcp = FastMCP(
            name=self.config.server_name,
            instructions=instructions,
        )
        
        # Register tools based on expertise level
        self._register_tools()
        
        logger.info(f"Tusk server initialized for workspace: {self.config.current_workspace}")
    
    def _get_instructions(self) -> str:
        """Get behavioral instructions for Claude."""
        return f"""
Tusk MCP Server - Persistent Memory for AI Agents

Workspace: {self.config.current_workspace}
Expertise Level: {self.config.expertise_level}

CORE BEHAVIORAL DIRECTIVES:

1. SESSION CONTINUITY:
   - ALWAYS use 'recall' at session start to restore context
   - Maintain awareness of previous work, decisions, and progress
   - Never start fresh without checking existing context

2. PERSISTENT STATE MANAGEMENT:
   - Create checkpoints when completing significant work or making key decisions
   - Extract and track actionable items as todos automatically
   - Maintain todos across sessions for continuity

3. DECISION LOGIC:
   - Use recall_quick for recent context (default)
   - Use full recall when user indicates broader investigation needed
   - Use specific filters (session_id, git_branch) when context suggests focused work
   - Automatically save progress when transitioning between major tasks

4. SEARCH-FIRST APPROACH:
   - All data is full-text searchable - use search tools when user asks about specific topics
   - Prefer search over browsing when looking for specific information
   - Search across checkpoints, todos, and plans for comprehensive results

5. PROACTIVE CONTEXT PRESERVATION:
   - Save checkpoints before major context switches
   - Create todos for incomplete items mentioned in conversation
   - Update task status (start/complete) as work progresses

REMEMBER: Your role is to maintain persistent context and continuity across sessions.
The user relies on you to remember and build upon previous interactions.
        """.strip()
    
    def _register_tools(self) -> None:
        """Register MCP tools based on configuration."""
        if self.config.expertise_level == "beginner":
            # Register simplified tools for beginners (7 core tools)
            from .tools.simplified import SimplifiedTools
            simplified_tools = SimplifiedTools(self)
            simplified_tools.register_simplified_tools(self.mcp)
            logger.info("Registered 7 simplified tools for beginner mode")
            
        else:
            # Register expert tools for advanced users
            from .tools import (
                CheckpointTool,
                PlanTool, 
                RecallTool,
                StandupTool,
                TodoTool,
            )
            
            # Create tool instances
            checkpoint_tool = CheckpointTool(self)
            todo_tool = TodoTool(self)
            plan_tool = PlanTool(self)
            recall_tool = RecallTool(self)
            standup_tool = StandupTool(self)
            
            # Register expert tools
            checkpoint_tool.register(self.mcp)
            todo_tool.register(self.mcp)
            plan_tool.register(self.mcp)
            recall_tool.register(self.mcp)
            standup_tool.register(self.mcp)
            logger.info("Registered expert tools with full functionality")
    
    def run_stdio(self) -> None:
        """Run the server with stdio transport."""
        logger.info("Starting Tusk server with stdio transport")
        self.mcp.run(transport="stdio")
    
    async def run_sse(self, host: str = "localhost", port: int = 3001) -> None:
        """Run the server with SSE transport."""
        logger.info(f"Starting Tusk server with SSE transport on {host}:{port}")
        await self.mcp.run(transport="sse", host=host, port=port)
    
    def get_workspace_stats(self) -> Dict[str, Any]:
        """Get statistics about the current workspace."""
        return {
            "workspace": self.config.current_workspace,
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
    config.log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stderr),
            logging.FileHandler(
                config.log_dir / f"tusk_{config.current_workspace}.log",
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