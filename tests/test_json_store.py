"""Tests for the JSON store."""

import tempfile
from pathlib import Path

import pytest

from overseer.store import JsonTaskStore
from overseer.models import TaskStatus, TaskType, Origin


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def store(temp_dir: Path) -> JsonTaskStore:
    """Create an initialized store for testing."""
    store = JsonTaskStore(temp_dir)
    store.initialize()
    return store


class TestJsonTaskStore:
    """Tests for JsonTaskStore."""

    def test_initialize(self, temp_dir: Path):
        """Test store initialization."""
        store = JsonTaskStore(temp_dir)
        store.initialize()

        assert (temp_dir / ".overseer").exists()
        assert (temp_dir / ".overseer" / "tasks.json").exists()
        assert (temp_dir / ".overseer" / "config.json").exists()
        assert (temp_dir / ".overseer" / "sessions").exists()

    def test_create_task(self, store: JsonTaskStore):
        """Test task creation."""
        task = store.create_task(
            title="Test task",
            task_type=TaskType.FEATURE,
            status=TaskStatus.ACTIVE,
            created_by=Origin.HUMAN,
            context="Test context",
        )

        assert task.id == "TASK-1"
        assert task.title == "Test task"
        assert task.type == TaskType.FEATURE
        assert task.status == TaskStatus.ACTIVE

    def test_list_tasks(self, store: JsonTaskStore):
        """Test listing tasks."""
        store.create_task(title="Task 1", task_type=TaskType.FEATURE)
        store.create_task(
            title="Task 2", task_type=TaskType.BUG, status=TaskStatus.ACTIVE
        )

        all_tasks = store.list_tasks()
        assert len(all_tasks) == 2

        active_tasks = store.list_tasks(status=TaskStatus.ACTIVE)
        assert len(active_tasks) == 1
        assert active_tasks[0].title == "Task 2"

    def test_get_task(self, store: JsonTaskStore):
        """Test getting a specific task."""
        created = store.create_task(title="Test", task_type=TaskType.FEATURE)

        task = store.get_task(created.id)
        assert task is not None
        assert task.id == created.id
        assert task.title == "Test"

        missing = store.get_task("TASK-999")
        assert missing is None

    def test_update_task(self, store: JsonTaskStore):
        """Test updating a task."""
        task = store.create_task(
            title="Original", task_type=TaskType.FEATURE, status=TaskStatus.BACKLOG
        )

        updated = store.update_task(task.id, status=TaskStatus.DONE)
        assert updated is not None
        assert updated.status == TaskStatus.DONE

        # Verify persistence
        reloaded = store.get_task(task.id)
        assert reloaded is not None
        assert reloaded.status == TaskStatus.DONE

    def test_delete_task(self, store: JsonTaskStore):
        """Test deleting a task."""
        task = store.create_task(title="To delete", task_type=TaskType.CHORE)

        assert store.delete_task(task.id) is True
        assert store.get_task(task.id) is None
        assert store.delete_task(task.id) is False  # Already deleted

    def test_next_task_id(self, store: JsonTaskStore):
        """Test task ID generation."""
        task1 = store.create_task(title="First", task_type=TaskType.FEATURE)
        task2 = store.create_task(title="Second", task_type=TaskType.FEATURE)

        assert task1.id == "TASK-1"
        assert task2.id == "TASK-2"

    def test_config(self, store: JsonTaskStore):
        """Test config read/write."""
        config = store.get_config()
        assert config.version == "0.1"

        config.active_task_id = "TASK-1"
        store.save_config(config)

        reloaded = store.get_config()
        assert reloaded.active_task_id == "TASK-1"

    def test_not_initialized_error(self, temp_dir: Path):
        """Test error when store is not initialized."""
        store = JsonTaskStore(temp_dir)

        with pytest.raises(FileNotFoundError):
            store.list_tasks()
