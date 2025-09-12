"""Configuration management for Tusk memory server."""

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class TuskConfig(BaseModel):
    """Configuration for Tusk memory server."""
    
    # Server settings
    server_name: str = Field(default="Tusk", description="Name of the MCP server")
    
    # Storage settings
    data_dir: Path = Field(
        default_factory=lambda: Path.cwd() / "data",
        description="Directory for storing memory data"
    )
    
    # Search settings
    search_enabled: bool = Field(default=True, description="Enable full-text search")
    max_search_results: int = Field(default=50, description="Maximum search results")
    
    # Memory settings  
    default_checkpoint_ttl: str = Field(
        default="7d", 
        description="Default TTL for checkpoints (e.g., '7d', '30d', '1h')"
    )
    max_highlights_per_checkpoint: int = Field(
        default=10, 
        description="Maximum highlights to store per checkpoint"
    )
    
    # Tool behavior
    expertise_level: Literal["beginner", "expert"] = Field(
        default="beginner",
        description="User expertise level for tool adaptation"
    )
    enable_transformations: bool = Field(
        default=True,
        description="Enable adaptive tool transformations"
    )
    
    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level"
    )
    log_dir: Path = Field(
        default_factory=lambda: Path.cwd() / "logs",
        description="Directory for log files"
    )
    
    # Workspace
    current_workspace: str = Field(
        default="default",
        description="Current workspace name"
    )
    auto_detect_workspace: bool = Field(
        default=True,
        description="Try to auto-detect workspace from git/directory"
    )
    
    @classmethod
    def from_env(cls) -> "TuskConfig":
        """Create config from environment variables."""
        return cls(
            server_name=os.getenv("TUSK_SERVER_NAME", "Tusk"),
            data_dir=Path(os.getenv("TUSK_DATA_DIR", "data")),
            search_enabled=os.getenv("TUSK_SEARCH_ENABLED", "true").lower() == "true",
            max_search_results=int(os.getenv("TUSK_MAX_SEARCH_RESULTS", "50")),
            default_checkpoint_ttl=os.getenv("TUSK_DEFAULT_TTL", "7d"),
            max_highlights_per_checkpoint=int(os.getenv("TUSK_MAX_HIGHLIGHTS", "10")),
            expertise_level=os.getenv("TUSK_EXPERTISE_LEVEL", "beginner"),
            enable_transformations=os.getenv("TUSK_TRANSFORMATIONS", "true").lower() == "true",
            log_level=os.getenv("TUSK_LOG_LEVEL", "INFO"),
            log_dir=Path(os.getenv("TUSK_LOG_DIR", "logs")),
            current_workspace=os.getenv("TUSK_WORKSPACE", "default"),
            auto_detect_workspace=os.getenv("TUSK_AUTO_WORKSPACE", "true").lower() == "true",
        )
    
    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create workspace directory
        workspace_dir = self.data_dir / self.current_workspace
        workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (workspace_dir / "checkpoints").mkdir(exist_ok=True)
        (workspace_dir / "todos").mkdir(exist_ok=True)
        (workspace_dir / "plans").mkdir(exist_ok=True)
        (workspace_dir / "index").mkdir(exist_ok=True)
    
    def get_workspace_dir(self, workspace: str | None = None) -> Path:
        """Get the directory for a specific workspace."""
        workspace = workspace or self.current_workspace
        return self.data_dir / workspace