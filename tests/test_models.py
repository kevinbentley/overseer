"""Tests for data models."""

from datetime import datetime

from overseer.models import Task, TaskStatus, TaskType, Origin, WorkSession, OverseerConfig


class TestTask:
    """Tests for the Task model."""

    def test_to_dict_and_back(self):
        """Test serialization round-trip."""
        now = datetime.now()
        task = Task(
            id="TASK-1",
            title="Test task",
            status=TaskStatus.ACTIVE,
            type=TaskType.FEATURE,
            created_by=Origin.HUMAN,
            context="Some context",
            linked_files=["src/main.py"],
            created_at=now,
            updated_at=now,
        )

        data = task.to_dict()
        restored = Task.from_dict(data)

        assert restored.id == task.id
        assert restored.title == task.title
        assert restored.status == task.status
        assert restored.type == task.type
        assert restored.created_by == task.created_by
        assert restored.context == task.context
        assert restored.linked_files == task.linked_files

    def test_format_display(self):
        """Test task display formatting."""
        task = Task(
            id="TASK-1",
            title="Fix bug",
            status=TaskStatus.ACTIVE,
            type=TaskType.BUG,
            created_by=Origin.AGENT,
            context=None,
            linked_files=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        display = task.format_display()
        assert "TASK-1" in display
        assert "Fix bug" in display
        assert "[>]" in display  # Active icon


class TestWorkSession:
    """Tests for the WorkSession model."""

    def test_create(self):
        """Test session creation."""
        session = WorkSession.create(
            summary="Did some work",
            files_touched=["file.py"],
            task_id="TASK-1",
        )

        assert session.summary == "Did some work"
        assert session.files_touched == ["file.py"]
        assert session.task_id == "TASK-1"
        assert session.id is not None
        assert session.logged_at is not None

    def test_to_dict_and_back(self):
        """Test serialization round-trip."""
        session = WorkSession.create(summary="Test session")
        data = session.to_dict()
        restored = WorkSession.from_dict(data)

        assert restored.id == session.id
        assert restored.summary == session.summary


class TestOverseerConfig:
    """Tests for the OverseerConfig model."""

    def test_defaults(self):
        """Test default config values."""
        config = OverseerConfig()
        assert config.version == "0.1"
        assert config.active_task_id is None
        assert config.auto_log_sessions is True

    def test_to_dict_and_back(self):
        """Test serialization round-trip."""
        config = OverseerConfig(active_task_id="TASK-1")
        data = config.to_dict()
        restored = OverseerConfig.from_dict(data)

        assert restored.active_task_id == config.active_task_id
