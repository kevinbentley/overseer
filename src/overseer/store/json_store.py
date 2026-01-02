"""JSON-based task store implementation."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models import Task, TaskStatus, TaskType, Origin, OverseerConfig


class JsonTaskStore:
    """Task store using JSON files in .overseer/ directory."""

    def __init__(self, root_path: str | Path | None = None):
        """Initialize the store.

        Args:
            root_path: Root directory containing .overseer/. Defaults to current directory.
        """
        self.root = Path(root_path) if root_path else Path.cwd()
        self.overseer_dir = self.root / ".overseer"
        self.tasks_file = self.overseer_dir / "tasks.json"
        self.config_file = self.overseer_dir / "config.json"

    def ensure_initialized(self) -> None:
        """Ensure the .overseer directory and files exist."""
        if not self.overseer_dir.exists():
            raise FileNotFoundError(
                f"Overseer not initialized. Run 'overseer init' in {self.root}"
            )

    def initialize(self) -> None:
        """Create the .overseer directory with default files."""
        self.overseer_dir.mkdir(parents=True, exist_ok=True)
        (self.overseer_dir / "sessions").mkdir(exist_ok=True)

        # Create default config if not exists
        if not self.config_file.exists():
            self._write_json(self.config_file, OverseerConfig().to_dict())

        # Create empty tasks file if not exists
        if not self.tasks_file.exists():
            self._write_json(self.tasks_file, {"version": "0.1", "tasks": []})

    def _read_json(self, path: Path) -> dict[str, Any]:
        """Read and parse a JSON file."""
        with open(path) as f:
            return json.load(f)

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        """Write data to JSON file atomically with sorted keys for git diffs."""
        # Write to temp file first, then rename for atomic operation
        fd, temp_path = tempfile.mkstemp(
            dir=path.parent, prefix=".tmp_", suffix=".json"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2, sort_keys=True)
                f.write("\n")  # Trailing newline for git
            os.rename(temp_path, path)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def _load_tasks_data(self) -> dict[str, Any]:
        """Load the tasks file data."""
        self.ensure_initialized()
        return self._read_json(self.tasks_file)

    def _save_tasks_data(self, data: dict[str, Any]) -> None:
        """Save the tasks file data."""
        self._write_json(self.tasks_file, data)

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """List all tasks, optionally filtered by status."""
        data = self._load_tasks_data()
        tasks = [Task.from_dict(t) for t in data.get("tasks", [])]

        if status is not None:
            tasks = [t for t in tasks if t.status == status]

        return tasks

    def get_task(self, task_id: str) -> Task | None:
        """Get a specific task by ID."""
        data = self._load_tasks_data()
        for task_data in data.get("tasks", []):
            if task_data["id"] == task_id:
                return Task.from_dict(task_data)
        return None

    def create_task(
        self,
        title: str,
        task_type: TaskType,
        status: TaskStatus = TaskStatus.BACKLOG,
        created_by: Origin = Origin.AGENT,
        context: str | None = None,
        linked_files: list[str] | None = None,
    ) -> Task:
        """Create a new task."""
        data = self._load_tasks_data()
        task_id = self._next_task_id(data)
        now = datetime.now()

        task = Task(
            id=task_id,
            title=title,
            status=status,
            type=task_type,
            created_by=created_by,
            context=context,
            linked_files=linked_files or [],
            created_at=now,
            updated_at=now,
        )

        data["tasks"].append(task.to_dict())
        self._save_tasks_data(data)

        return task

    def update_task(self, task_id: str, **updates: Any) -> Task | None:
        """Update a task by ID. Returns updated task or None if not found."""
        data = self._load_tasks_data()

        for i, task_data in enumerate(data.get("tasks", [])):
            if task_data["id"] == task_id:
                # Apply updates
                for key, value in updates.items():
                    if key == "status" and isinstance(value, TaskStatus):
                        task_data["status"] = value.value
                    elif key == "type" and isinstance(value, TaskType):
                        task_data["type"] = value.value
                    elif key == "created_by" and isinstance(value, Origin):
                        task_data["created_by"] = value.value
                    else:
                        task_data[key] = value

                task_data["updated_at"] = datetime.now().isoformat()
                data["tasks"][i] = task_data
                self._save_tasks_data(data)

                return Task.from_dict(task_data)

        return None

    def delete_task(self, task_id: str) -> bool:
        """Delete a task by ID. Returns True if deleted."""
        data = self._load_tasks_data()
        original_len = len(data.get("tasks", []))

        data["tasks"] = [t for t in data.get("tasks", []) if t["id"] != task_id]

        if len(data["tasks"]) < original_len:
            self._save_tasks_data(data)
            return True

        return False

    def _next_task_id(self, data: dict[str, Any] | None = None) -> str:
        """Generate the next task ID."""
        if data is None:
            data = self._load_tasks_data()

        tasks = data.get("tasks", [])
        if not tasks:
            return "TASK-1"

        # Find highest existing task number
        max_num = 0
        for task in tasks:
            task_id = task.get("id", "")
            if task_id.startswith("TASK-"):
                try:
                    num = int(task_id[5:])
                    max_num = max(max_num, num)
                except ValueError:
                    pass

        return f"TASK-{max_num + 1}"

    def get_config(self) -> OverseerConfig:
        """Load the project configuration."""
        self.ensure_initialized()
        data = self._read_json(self.config_file)
        return OverseerConfig.from_dict(data)

    def save_config(self, config: OverseerConfig) -> None:
        """Save the project configuration."""
        self._write_json(self.config_file, config.to_dict())
