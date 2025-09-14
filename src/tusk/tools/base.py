"""Base tool class for Tusk memory tools."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..server import TuskServer


class BaseTool(ABC):
    """Base class for Tusk memory tools."""
    
    def __init__(self, server: "TuskServer"):
        self.server = server
        self.config = server.config
        self.checkpoint_storage = server.checkpoint_storage
        self.task_storage = server.task_storage
        self.plan_storage = server.plan_storage
        self.search_engine = server.search_engine
    
    @abstractmethod
    def register(self, mcp_server) -> None:
        """Register this tool's functions with the MCP server."""
        pass
    
    def get_current_workspace(self) -> str:
        """Get the current workspace ID (deprecated - returns empty string)."""
        return ""