"""Checkpoint model for work context snapshots."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from .highlight import Highlight
from .types import TZAwareDatetime, utc_now


def generate_id() -> str:
    """Generate a unique ID for checkpoints."""
    return str(uuid4())


def parse_ttl(ttl_str: str) -> timedelta:
    """Parse TTL string like '7d', '1h', '30m' into timedelta."""
    if not ttl_str:
        return timedelta(days=7)  # Default 7 days
    
    unit = ttl_str[-1].lower()
    try:
        value = int(ttl_str[:-1])
    except ValueError:
        return timedelta(days=7)  # Default on parse error
    
    unit_map = {
        'm': timedelta(minutes=value),
        'h': timedelta(hours=value),
        'd': timedelta(days=value),
        'w': timedelta(weeks=value),
    }
    
    return unit_map.get(unit, timedelta(days=7))


class Checkpoint(BaseModel):
    """A checkpoint represents a snapshot of work context at a point in time."""
    
    # Identity
    id: str = Field(default_factory=generate_id, description="Unique checkpoint ID")
    
    workspace_id: str = Field(description="ID of the workspace this checkpoint belongs to")
    
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID when this checkpoint was created"
    )
    
    # Core content
    description: str = Field(
        description="Human-readable description of what's happening in this checkpoint"
    )
    
    work_context: Optional[str] = Field(
        default=None,
        description="Detailed context about the current work - goals, status, next steps"
    )
    
    # File tracking
    active_files: list[str] = Field(
        default_factory=list,
        description="List of files that were actively being worked on"
    )
    
    # Highlights and key moments
    highlights: list[Highlight] = Field(
        default_factory=list,
        description="Important moments, decisions, or discoveries"
    )
    
    # Version control context
    git_branch: Optional[str] = Field(
        default=None,
        description="Git branch when checkpoint was created"
    )
    
    git_commit: Optional[str] = Field(
        default=None,
        description="Git commit hash when checkpoint was created"
    )
    
    # Metadata
    is_global: bool = Field(
        default=False,
        description="Whether this checkpoint applies globally or just to current workspace"
    )
    
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for organization and filtering"
    )
    
    # Timestamps
    created_at: TZAwareDatetime = Field(
        default_factory=utc_now,
        description="When this checkpoint was created"
    )
    
    updated_at: Optional[TZAwareDatetime] = Field(
        default=None,
        description="When this checkpoint was last updated"
    )
    
    ttl_expiry: Optional[TZAwareDatetime] = Field(
        default=None,
        description="When this checkpoint should expire and be cleaned up"
    )
    
    def set_ttl(self, ttl_str: str) -> None:
        """Set TTL expiry based on string like '7d', '1h', etc."""
        ttl_delta = parse_ttl(ttl_str)
        self.ttl_expiry = utc_now() + ttl_delta
    
    def is_expired(self) -> bool:
        """Check if this checkpoint has expired."""
        if not self.ttl_expiry:
            return False
        return utc_now() > self.ttl_expiry
    
    def add_highlight(self, highlight: Highlight) -> None:
        """Add a highlight to this checkpoint."""
        self.highlights.append(highlight)
        self.updated_at = utc_now()
    
    def get_summary(self, max_length: int = 200) -> str:
        """Get a brief summary of this checkpoint."""
        summary = self.description
        if len(summary) > max_length:
            summary = summary[:max_length-3] + "..."
        
        if self.highlights:
            highlight_count = len(self.highlights)
            summary += f" ({highlight_count} highlights)"
        
        return summary
    
    def to_search_text(self) -> str:
        """Convert checkpoint to searchable text."""
        parts = [
            self.description,
            self.work_context or "",
        ]
        
        parts.extend(self.active_files)
        parts.extend(self.tags)
        
        if self.git_branch:
            parts.append(self.git_branch)
        
        # Add highlight content for search
        for highlight in self.highlights:
            parts.append(highlight.to_search_text())
        
        return " ".join(filter(None, parts))
    
    def __str__(self) -> str:
        created = self.created_at.strftime("%Y-%m-%d %H:%M")
        return f"[{created}] {self.description}"