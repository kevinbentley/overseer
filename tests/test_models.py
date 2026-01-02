"""Tests for data models."""

from datetime import datetime

from overseer.models import Task, TaskStatus, TaskType, Origin, WorkSession, OverseerConfig, JiraConfig


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

    def test_jira_key_serialization(self):
        """Test jira_key field serialization."""
        now = datetime.now()
        task = Task(
            id="TASK-1",
            title="Jira linked task",
            status=TaskStatus.ACTIVE,
            type=TaskType.FEATURE,
            created_by=Origin.HUMAN,
            created_at=now,
            updated_at=now,
            jira_key="PROJ-123",
        )

        data = task.to_dict()
        assert data["jira_key"] == "PROJ-123"

        restored = Task.from_dict(data)
        assert restored.jira_key == "PROJ-123"

    def test_jira_key_display(self):
        """Test jira_key appears in display."""
        task = Task(
            id="TASK-1",
            title="Jira linked task",
            status=TaskStatus.ACTIVE,
            type=TaskType.FEATURE,
            created_by=Origin.HUMAN,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            jira_key="PROJ-456",
        )

        display = task.format_display()
        assert "PROJ-456" in display
        assert "Jira:" in display


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

    def test_jira_config_defaults(self):
        """Test JiraConfig default values."""
        config = OverseerConfig()
        assert config.jira is not None
        assert config.jira.url is None
        assert config.jira.email is None
        assert config.jira.api_token is None
        assert config.jira.project_key is None
        assert config.jira.is_configured() is False

    def test_jira_config_serialization(self):
        """Test JiraConfig serialization round-trip."""
        jira_config = JiraConfig(
            url="https://test.atlassian.net",
            email="user@test.com",
            api_token="secret-token",
            project_key="PROJ",
        )
        config = OverseerConfig(jira=jira_config)

        data = config.to_dict()
        assert data["jira"]["url"] == "https://test.atlassian.net"
        assert data["jira"]["api_token"] == "secret-token"

        restored = OverseerConfig.from_dict(data)
        assert restored.jira.url == "https://test.atlassian.net"
        assert restored.jira.email == "user@test.com"
        assert restored.jira.api_token == "secret-token"
        assert restored.jira.project_key == "PROJ"
        assert restored.jira.is_configured() is True

    def test_jira_config_is_configured(self):
        """Test JiraConfig.is_configured() method."""
        # Not configured - missing url
        assert JiraConfig(email="x", api_token="y").is_configured() is False
        # Not configured - missing email
        assert JiraConfig(url="x", api_token="y").is_configured() is False
        # Not configured - missing token
        assert JiraConfig(url="x", email="y").is_configured() is False
        # Configured - project_key is optional
        assert JiraConfig(url="x", email="y", api_token="z").is_configured() is True
