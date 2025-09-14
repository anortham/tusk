"""Base storage class with common JSON file operations."""

import json
import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Generic, TypeVar

import portalocker
from pydantic import BaseModel

from ..config import TuskConfig

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class BaseStorage(Generic[T], ABC):
    """Base class for JSON file storage with file locking."""

    def __init__(self, config: TuskConfig, model_class: type[T]):
        self.config = config
        self.model_class = model_class
        self.data_dir = config.get_data_dir()
        self._ensure_directories()

    @abstractmethod
    def get_storage_subdir(self) -> str:
        """Get the subdirectory name for this storage type."""
        pass

    def _ensure_directories(self) -> None:
        """Ensure storage directories exist."""
        storage_dir = self.data_dir / self.get_storage_subdir()
        storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, item_id: str) -> Path:
        """Get the file path for an item."""
        storage_dir = self.data_dir / self.get_storage_subdir()
        return storage_dir / f"{item_id}.json"

    def _read_json_file(self, file_path: Path) -> dict[str, Any] | None:
        """Read JSON data from file with locking."""
        if not file_path.exists():
            return None

        try:
            with open(file_path, encoding="utf-8") as f:
                # Use shared lock for reading
                portalocker.lock(f, portalocker.LOCK_SH)
                try:
                    return json.load(f)
                finally:
                    portalocker.unlock(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Error reading {file_path}: {e}")
            return None

    def _write_json_file(self, file_path: Path, data: dict[str, Any]) -> bool:
        """Write JSON data to file with locking."""
        try:
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                # Use exclusive lock for writing
                portalocker.lock(f, portalocker.LOCK_EX)
                try:
                    json.dump(data, f, indent=2, ensure_ascii=False, default=self._json_serializer)
                finally:
                    portalocker.unlock(f)
            return True
        except OSError as e:
            logger.error(f"Error writing {file_path}: {e}")
            return False

    def _json_serializer(self, obj: Any) -> Any:
        """Custom JSON serializer for datetime and other objects."""
        if isinstance(obj, datetime):
            # Ensure timezone-aware datetimes are properly serialized
            if obj.tzinfo is not None:
                # Use isoformat() which preserves timezone info
                return obj.isoformat()
            else:
                # For naive datetimes, assume UTC and add explicit timezone

                obj_utc = obj.replace(tzinfo=UTC)
                return obj_utc.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    def load(self, item_id: str) -> T | None:
        """Load an item by ID."""
        file_path = self._get_file_path(item_id)
        data = self._read_json_file(file_path)

        if data is None:
            return None

        try:
            return self.model_class.model_validate(data)
        except Exception as e:
            logger.error(f"Error deserializing {item_id}: {e}")
            return None

    def save(self, item: T) -> bool:
        """Save an item."""
        try:
            # Get ID from the item
            item_id = item.id
            file_path = self._get_file_path(item_id)

            # Convert to dict and save
            data = item.model_dump(mode="json")
            success = self._write_json_file(file_path, data)

            if success:
                logger.debug(f"Saved {self.model_class.__name__} {item_id}")
            else:
                logger.error(f"Failed to save {self.model_class.__name__} {item_id}")

            return success
        except Exception as e:
            logger.error(f"Error saving item: {e}")
            return False

    def delete(self, item_id: str) -> bool:
        """Delete an item by ID."""
        file_path = self._get_file_path(item_id)

        if not file_path.exists():
            return True  # Already deleted

        try:
            file_path.unlink()
            logger.debug(f"Deleted {self.model_class.__name__} {item_id}")
            return True
        except OSError as e:
            logger.error(f"Error deleting {item_id}: {e}")
            return False

    def exists(self, item_id: str) -> bool:
        """Check if an item exists."""
        file_path = self._get_file_path(item_id)
        return file_path.exists()

    def list_ids(self) -> list[str]:
        """List all item IDs."""
        storage_dir = self.data_dir / self.get_storage_subdir()

        if not storage_dir.exists():
            return []

        ids = []
        for file_path in storage_dir.glob("*.json"):
            # Remove .json extension to get ID
            item_id = file_path.stem
            ids.append(item_id)

        return sorted(ids)

    def load_all(self) -> list[T]:
        """Load all items."""
        items = []

        for item_id in self.list_ids():
            item = self.load(item_id)
            if item is not None:
                items.append(item)

        return items

    def count(self) -> int:
        """Count the number of items."""
        return len(self.list_ids())

    def cleanup_expired(self) -> int:
        """Remove expired items (if applicable). Returns count of removed items."""
        removed_count = 0

        for item_id in self.list_ids():
            item = self.load(item_id)
            if item is None:
                continue

            # Check if item has expiration logic
            if hasattr(item, "is_expired") and item.is_expired():
                if self.delete(item_id):
                    removed_count += 1
                    logger.info(f"Removed expired {self.model_class.__name__} {item_id}")

        return removed_count
