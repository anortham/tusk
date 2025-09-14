"""Configuration management for Tusk memory server."""

import json
import os
from pathlib import Path
from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field


class TuskConfig(BaseModel):
    """Configuration for Tusk memory server."""

    # Server settings
    server_name: str = Field(default="Tusk", description="Name of the MCP server")

    # Storage settings
    storage_mode: Literal["global", "local"] = Field(
        default="global",
        description="Storage mode: 'global' for cross-project at ~/.coa/tusk, 'local' for project-specific",
    )

    data_dir: Optional[Path] = Field(
        default=None, description="Custom data directory (overrides storage_mode if set)"
    )

    # Search settings
    search_enabled: bool = Field(default=True, description="Enable full-text search")
    max_search_results: int = Field(default=50, description="Maximum search results")

    # Memory settings
    default_checkpoint_ttl: str = Field(
        default="7d", description="Default TTL for checkpoints (e.g., '7d', '30d', '1h')"
    )
    max_highlights_per_checkpoint: int = Field(
        default=10, description="Maximum highlights to store per checkpoint"
    )

    # Removed expertise_level - we now use unified tools for everyone
    enable_transformations: bool = Field(
        default=True, description="Enable adaptive tool transformations"
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )
    log_dir: Optional[Path] = Field(
        default=None, description="Directory for log files (auto-determined if not set)"
    )

    # Project settings
    auto_detect_project: bool = Field(
        default=True, description="Automatically detect current project from working directory"
    )

    @classmethod
    def from_env(cls) -> "TuskConfig":
        """Create config from environment variables."""
        data_dir = os.getenv("TUSK_DATA_DIR")
        log_dir = os.getenv("TUSK_LOG_DIR")

        return cls(
            server_name=os.getenv("TUSK_SERVER_NAME", "Tusk"),
            storage_mode=os.getenv("TUSK_STORAGE_MODE", "global"),
            data_dir=Path(data_dir).expanduser() if data_dir else None,
            search_enabled=os.getenv("TUSK_SEARCH_ENABLED", "true").lower() == "true",
            max_search_results=int(os.getenv("TUSK_MAX_SEARCH_RESULTS", "50")),
            default_checkpoint_ttl=os.getenv("TUSK_DEFAULT_TTL", "7d"),
            max_highlights_per_checkpoint=int(os.getenv("TUSK_MAX_HIGHLIGHTS", "10")),
            enable_transformations=os.getenv("TUSK_TRANSFORMATIONS", "true").lower() == "true",
            log_level=os.getenv("TUSK_LOG_LEVEL", "INFO"),
            log_dir=Path(log_dir).expanduser() if log_dir else None,
            auto_detect_project=os.getenv("TUSK_AUTO_DETECT_PROJECT", "true").lower() == "true",
        )

    def get_data_dir(self) -> Path:
        """Get the data directory based on storage mode."""
        if self.data_dir:
            # Custom data directory specified
            return self.data_dir

        if self.storage_mode == "global":
            return Path.home() / ".coa" / "tusk" / "data"
        else:  # local mode
            return Path.cwd() / ".coa" / "tusk" / "data"

    def get_log_dir(self) -> Path:
        """Get the log directory based on storage mode."""
        if self.log_dir:
            # Custom log directory specified
            return self.log_dir

        if self.storage_mode == "global":
            return Path.home() / ".coa" / "tusk" / "logs"
        else:  # local mode
            return Path.cwd() / ".coa" / "tusk" / "logs"

    def get_projects_registry_path(self) -> Path:
        """Get the path to the projects registry file."""
        if self.storage_mode == "global":
            return Path.home() / ".coa" / "tusk" / "projects.json"
        else:  # local mode - no registry needed
            return Path.cwd() / ".coa" / "tusk" / "projects.json"

    def get_current_project_id(self) -> str:
        """Get the current project ID based on working directory."""
        if not self.auto_detect_project:
            return "default"

        cwd = Path.cwd()

        # Try to find git repo root first
        git_root = self._find_git_root(cwd)
        if git_root:
            return git_root.name

        # Try to find meaningful parent (not just random folder)
        meaningful_dirs = {"src", "lib", "app", "backend", "frontend", "api", "web"}
        current = cwd
        while current != current.parent:
            if any((current / d).exists() for d in meaningful_dirs):
                return current.name
            current = current.parent

        # Fallback to current directory name
        return cwd.name

    def _find_git_root(self, path: Path) -> Optional[Path]:
        """Find the git repository root starting from the given path."""
        current = path.resolve()
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        return None

    def get_current_project_path(self) -> str:
        """Get the current project path as a string."""
        return str(Path.cwd().resolve())

    def load_projects_registry(self) -> Dict[str, str]:
        """Load the projects registry (path -> project_id mapping)."""
        registry_path = self.get_projects_registry_path()
        if not registry_path.exists():
            return {}

        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def save_projects_registry(self, registry: Dict[str, str]) -> None:
        """Save the projects registry (path -> project_id mapping)."""
        registry_path = self.get_projects_registry_path()
        registry_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(registry_path, "w", encoding="utf-8") as f:
                json.dump(registry, f, indent=2, ensure_ascii=False)
        except IOError as e:
            # Log error but don't fail - registry is not critical
            import logging

            logging.getLogger(__name__).warning(f"Failed to save projects registry: {e}")

    def register_current_project(self) -> str:
        """Register the current project in the registry and return its ID."""
        if self.storage_mode == "local":
            # No registry needed for local mode
            return self.get_current_project_id()

        project_path = self.get_current_project_path()
        project_id = self.get_current_project_id()

        # Load existing registry
        registry = self.load_projects_registry()

        # Add current project if not already registered
        if project_path not in registry:
            registry[project_path] = project_id
            self.save_projects_registry(registry)

        return registry[project_path]

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        data_dir = self.get_data_dir()
        log_dir = self.get_log_dir()

        data_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create data subdirectories
        (data_dir / "checkpoints").mkdir(exist_ok=True)
        (data_dir / "todos").mkdir(exist_ok=True)
        (data_dir / "plans").mkdir(exist_ok=True)
        (data_dir / "index").mkdir(exist_ok=True)

        # Register current project if using global storage
        if self.storage_mode == "global":
            self.register_current_project()
