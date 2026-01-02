"""Configuration model for Overseer."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OverseerConfig:
    """Overseer project configuration."""

    version: str = "0.1"
    active_task_id: str | None = None
    auto_log_sessions: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "active_task_id": self.active_task_id,
            "auto_log_sessions": self.auto_log_sessions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OverseerConfig":
        """Create an OverseerConfig from a dictionary."""
        return cls(
            version=data.get("version", "0.1"),
            active_task_id=data.get("active_task_id"),
            auto_log_sessions=data.get("auto_log_sessions", True),
        )
