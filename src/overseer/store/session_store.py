"""Session store for work session logging."""

import json
import os
import tempfile
from datetime import datetime, date
from pathlib import Path
from typing import Any

from ..models import WorkSession


class SessionStore:
    """Store for work sessions, organized by day."""

    def __init__(self, root_path: str | Path | None = None):
        """Initialize the session store.

        Args:
            root_path: Root directory containing .overseer/. Defaults to current directory.
        """
        self.root = Path(root_path) if root_path else Path.cwd()
        self.sessions_dir = self.root / ".overseer" / "sessions"

    def ensure_initialized(self) -> None:
        """Ensure the sessions directory exists."""
        if not self.sessions_dir.exists():
            raise FileNotFoundError(
                f"Overseer not initialized. Run 'overseer init' in {self.root}"
            )

    def _session_file(self, day: date) -> Path:
        """Get the session file path for a given day."""
        return self.sessions_dir / f"{day.isoformat()}.json"

    def _read_json(self, path: Path) -> dict[str, Any]:
        """Read and parse a JSON file."""
        if not path.exists():
            return {"sessions": []}
        with open(path) as f:
            return json.load(f)

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        """Write data to JSON file atomically."""
        fd, temp_path = tempfile.mkstemp(
            dir=path.parent, prefix=".tmp_", suffix=".json"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2, sort_keys=True)
                f.write("\n")
            os.rename(temp_path, path)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def log_session(
        self,
        summary: str,
        files_touched: list[str] | None = None,
        task_id: str | None = None,
    ) -> WorkSession:
        """Log a new work session."""
        self.ensure_initialized()

        session = WorkSession.create(
            summary=summary,
            files_touched=files_touched,
            task_id=task_id,
        )

        today = date.today()
        file_path = self._session_file(today)
        data = self._read_json(file_path)
        data["sessions"].append(session.to_dict())
        self._write_json(file_path, data)

        return session

    def get_sessions_for_day(self, day: date | None = None) -> list[WorkSession]:
        """Get all sessions for a given day (defaults to today)."""
        self.ensure_initialized()

        if day is None:
            day = date.today()

        file_path = self._session_file(day)
        data = self._read_json(file_path)

        return [WorkSession.from_dict(s) for s in data.get("sessions", [])]

    def get_sessions_for_range(
        self, start: date, end: date | None = None
    ) -> list[WorkSession]:
        """Get all sessions in a date range (inclusive)."""
        self.ensure_initialized()

        if end is None:
            end = date.today()

        sessions: list[WorkSession] = []
        current = start

        while current <= end:
            sessions.extend(self.get_sessions_for_day(current))
            current = date(
                current.year,
                current.month,
                current.day + 1 if current.day < 28 else 1,
            )
            # Simple date increment (handles month boundaries approximately)
            from datetime import timedelta

            current = start + timedelta(days=(current - start).days + 1)
            if current > end:
                break

        return sessions

    def format_daily_report(self, day: date | None = None) -> str:
        """Generate a markdown report for a day's sessions."""
        if day is None:
            day = date.today()

        sessions = self.get_sessions_for_day(day)

        if not sessions:
            return f"**{day.isoformat()}**: No sessions logged."

        lines = [f"**{day.isoformat()}**", ""]
        for session in sessions:
            lines.append(f"- {session.format_display()}")

        return "\n".join(lines)
