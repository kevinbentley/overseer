"""Work session model for Overseer."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import uuid


@dataclass
class WorkSession:
    """A logged work session."""

    id: str
    summary: str
    logged_at: datetime
    files_touched: list[str] = field(default_factory=list)
    task_id: str | None = None

    @classmethod
    def create(
        cls,
        summary: str,
        files_touched: list[str] | None = None,
        task_id: str | None = None,
    ) -> "WorkSession":
        """Create a new work session with generated ID and timestamp."""
        return cls(
            id=str(uuid.uuid4())[:8],
            summary=summary,
            files_touched=files_touched or [],
            task_id=task_id,
            logged_at=datetime.now(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert session to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "summary": self.summary,
            "files_touched": self.files_touched,
            "task_id": self.task_id,
            "logged_at": self.logged_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkSession":
        """Create a WorkSession from a dictionary."""
        return cls(
            id=data["id"],
            summary=data["summary"],
            files_touched=data.get("files_touched", []),
            task_id=data.get("task_id"),
            logged_at=datetime.fromisoformat(data["logged_at"]),
        )

    def format_display(self) -> str:
        """Format session for display."""
        time_str = self.logged_at.strftime("%H:%M")
        result = f"[{time_str}] {self.summary}"
        if self.task_id:
            result += f" ({self.task_id})"
        if self.files_touched:
            result += f"\n         Files: {', '.join(self.files_touched)}"
        return result
