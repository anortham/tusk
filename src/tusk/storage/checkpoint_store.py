"""Storage for checkpoint data with date-based organization."""

import logging
from datetime import UTC, datetime
from pathlib import Path

from ..models.checkpoint import Checkpoint
from .base import BaseStorage

logger = logging.getLogger(__name__)


class CheckpointStorage(BaseStorage[Checkpoint]):
    """Storage for checkpoints with date-based directory organization."""

    def __init__(self, config):
        super().__init__(config, Checkpoint)

    def get_storage_subdir(self) -> str:
        return "checkpoints"

    def _get_date_dir(self, date: datetime) -> Path:
        """Get the date-based directory for a checkpoint."""
        date_str = date.strftime("%Y-%m-%d")
        return self.data_dir / self.get_storage_subdir() / date_str

    def _get_file_path(self, item_id: str) -> Path:
        """Get file path for checkpoint - requires loading to get date."""
        # First try to find the file in any date directory
        storage_dir = self.data_dir / self.get_storage_subdir()

        for date_dir in storage_dir.iterdir():
            if date_dir.is_dir():
                file_path = date_dir / f"{item_id}.json"
                if file_path.exists():
                    return file_path

        # If not found, use today's date
        today = datetime.now(UTC)
        return self._get_date_dir(today) / f"{item_id}.json"

    def save(self, checkpoint: Checkpoint) -> bool:
        """Save checkpoint in date-based directory."""
        try:
            # Use created_at date for directory organization
            date_dir = self._get_date_dir(checkpoint.created_at)
            date_dir.mkdir(parents=True, exist_ok=True)

            file_path = date_dir / f"{checkpoint.id}.json"

            # Convert to dict and save
            data = checkpoint.model_dump(mode="json")
            success = self._write_json_file(file_path, data)

            if success:
                logger.debug(f"Saved checkpoint {checkpoint.id} to {file_path}")
            else:
                logger.error(f"Failed to save checkpoint {checkpoint.id}")

            return success
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}")
            return False

    def list_by_date_range(
        self, start_date: datetime | None = None, end_date: datetime | None = None
    ) -> list[Checkpoint]:
        """List checkpoints within a date range."""
        checkpoints = []
        storage_dir = self.data_dir / self.get_storage_subdir()

        if not storage_dir.exists():
            return checkpoints

        # Get all date directories
        date_dirs = [d for d in storage_dir.iterdir() if d.is_dir()]

        for date_dir in date_dirs:
            # Parse date from directory name
            try:
                dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
            except ValueError:
                continue

            # Filter by date range (compare just the date parts to avoid timezone issues)
            if start_date and dir_date.date() < start_date.date():
                continue
            if end_date and dir_date.date() > end_date.date():
                continue

            # Load checkpoints from this date
            for file_path in date_dir.glob("*.json"):
                checkpoint_id = file_path.stem
                checkpoint = self.load(checkpoint_id)
                if checkpoint:
                    checkpoints.append(checkpoint)

        # Sort by created_at - now all datetimes are timezone-aware
        checkpoints.sort(key=lambda c: c.created_at, reverse=True)
        return checkpoints

    def list_recent(self, limit: int = 10) -> list[Checkpoint]:
        """List most recent checkpoints."""
        all_checkpoints = self.load_all()

        # Sort by created_at - now all datetimes are timezone-aware
        all_checkpoints.sort(key=lambda c: c.created_at, reverse=True)
        return all_checkpoints[:limit]

    def find_by_session(self, session_id: str) -> list[Checkpoint]:
        """Find checkpoints by session ID."""
        all_checkpoints = self.load_all()
        session_checkpoints = [c for c in all_checkpoints if c.session_id == session_id]
        session_checkpoints.sort(key=lambda c: c.created_at, reverse=True)
        return session_checkpoints

    def find_by_git_branch(self, branch: str) -> list[Checkpoint]:
        """Find checkpoints by git branch."""
        all_checkpoints = self.load_all()
        branch_checkpoints = [c for c in all_checkpoints if c.git_branch == branch]
        branch_checkpoints.sort(key=lambda c: c.created_at, reverse=True)
        return branch_checkpoints

    def find_by_tags(self, tags: list[str]) -> list[Checkpoint]:
        """Find checkpoints that have any of the specified tags."""
        all_checkpoints = self.load_all()
        matching_checkpoints = []

        for checkpoint in all_checkpoints:
            if any(tag in checkpoint.tags for tag in tags):
                matching_checkpoints.append(checkpoint)

        matching_checkpoints.sort(key=lambda c: c.created_at, reverse=True)
        return matching_checkpoints

    def cleanup_expired(self) -> int:
        """Remove expired checkpoints."""
        removed_count = 0
        storage_dir = self.data_dir / self.get_storage_subdir()

        if not storage_dir.exists():
            return 0

        # Check all date directories
        for date_dir in storage_dir.iterdir():
            if not date_dir.is_dir():
                continue

            for file_path in date_dir.glob("*.json"):
                checkpoint_id = file_path.stem
                checkpoint = self.load(checkpoint_id)

                if checkpoint and checkpoint.is_expired():
                    try:
                        file_path.unlink()
                        removed_count += 1
                        logger.info(f"Removed expired checkpoint {checkpoint_id}")
                    except OSError as e:
                        logger.error(f"Error removing expired checkpoint {checkpoint_id}: {e}")

            # Remove empty date directories
            if not any(date_dir.iterdir()):
                try:
                    date_dir.rmdir()
                    logger.debug(f"Removed empty date directory {date_dir}")
                except OSError:
                    pass  # Directory not empty or other issue

        return removed_count

    def list_ids(self) -> list[str]:
        """List all checkpoint IDs across all date directories."""
        ids = []
        storage_dir = self.data_dir / self.get_storage_subdir()

        if not storage_dir.exists():
            return ids

        for date_dir in storage_dir.iterdir():
            if date_dir.is_dir():
                for file_path in date_dir.glob("*.json"):
                    ids.append(file_path.stem)

        return sorted(ids)
