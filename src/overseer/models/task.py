"""Task model for Overseer."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TaskStatus(Enum):
    """Task status values."""

    ACTIVE = "active"
    BACKLOG = "backlog"
    DONE = "done"
    BLOCKED = "blocked"


class TaskType(Enum):
    """Task type values."""

    FEATURE = "feature"
    BUG = "bug"
    DEBT = "debt"
    CHORE = "chore"


class Origin(Enum):
    """Task origin - who created the task."""

    HUMAN = "human"
    AGENT = "agent"


@dataclass
class Task:
    """A work item tracked by Overseer."""

    id: str
    title: str
    status: TaskStatus
    type: TaskType
    created_by: Origin
    created_at: datetime
    updated_at: datetime
    context: str | None = None
    linked_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert task to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status.value,
            "type": self.type.value,
            "created_by": self.created_by.value,
            "context": self.context,
            "linked_files": self.linked_files,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        """Create a Task from a dictionary."""
        return cls(
            id=data["id"],
            title=data["title"],
            status=TaskStatus(data["status"]),
            type=TaskType(data["type"]),
            created_by=Origin(data["created_by"]),
            context=data.get("context"),
            linked_files=data.get("linked_files", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )

    def format_display(self, include_context: bool = True) -> str:
        """Format task for display."""
        status_icons = {
            TaskStatus.ACTIVE: "[>]",
            TaskStatus.BACKLOG: "[ ]",
            TaskStatus.DONE: "[x]",
            TaskStatus.BLOCKED: "[!]",
        }
        icon = status_icons.get(self.status, "[ ]")
        result = f"{icon} {self.id}: {self.title} ({self.type.value})"
        if include_context and self.context:
            result += f"\n    Context: {self.context}"
        if self.linked_files:
            result += f"\n    Files: {', '.join(self.linked_files)}"
        return result
