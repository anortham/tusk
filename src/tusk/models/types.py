"""Custom Pydantic types for Tusk models."""

from datetime import datetime, timezone
from typing import Any

from pydantic import Field, field_validator
from pydantic_core import core_schema


class TZAwareDatetime(datetime):
    """A datetime that is always timezone-aware.
    
    This class ensures that:
    1. All datetimes are stored with timezone information
    2. When deserializing from JSON, naive datetimes are assumed to be UTC
    3. All datetime operations preserve timezone awareness
    """
    
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        """Pydantic v2 core schema for custom datetime validation."""
        
        def validate_datetime(value: Any) -> datetime:
            """Validate and ensure datetime is timezone-aware."""
            if isinstance(value, datetime):
                # If already timezone-aware, return as-is
                if value.tzinfo is not None:
                    return value
                # If naive, assume it's UTC and add timezone info
                return value.replace(tzinfo=timezone.utc)
            
            elif isinstance(value, str):
                # Parse ISO format strings
                if value.endswith('Z'):
                    # Handle 'Z' suffix as UTC
                    dt = datetime.fromisoformat(value[:-1])
                    return dt.replace(tzinfo=timezone.utc)
                elif '+' in value or value.endswith('+00:00'):
                    # Already has timezone info
                    return datetime.fromisoformat(value)
                else:
                    # Assume UTC if no timezone info
                    dt = datetime.fromisoformat(value)
                    return dt.replace(tzinfo=timezone.utc)
            
            elif isinstance(value, (int, float)):
                # Unix timestamp
                return datetime.fromtimestamp(value, tz=timezone.utc)
            
            else:
                raise ValueError(f"Cannot convert {type(value)} to timezone-aware datetime")
        
        # Create core schema for validation
        return core_schema.no_info_plain_validator_function(validate_datetime)
    
    @classmethod
    def now_utc(cls) -> 'TZAwareDatetime':
        """Get current time in UTC as a TZAwareDatetime."""
        return cls.now(timezone.utc)
    
    def __str__(self) -> str:
        """String representation that shows timezone info."""
        return self.strftime("%Y-%m-%d %H:%M:%S %Z")
    
    def __repr__(self) -> str:
        """Representation that shows timezone info."""
        return f"TZAwareDatetime({super().__repr__()})"


def utc_now() -> TZAwareDatetime:
    """Factory function to create current UTC datetime."""
    return TZAwareDatetime.now(timezone.utc)


# For backwards compatibility and cleaner imports
UTCDateTime = TZAwareDatetime