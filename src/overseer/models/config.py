"""Configuration model for Overseer."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class JiraConfig:
    """Jira integration configuration."""

    url: str | None = None
    email: str | None = None
    api_token: str | None = None
    project_key: str | None = None

    def is_configured(self) -> bool:
        """Check if Jira is fully configured."""
        return all([self.url, self.email, self.api_token])

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary for JSON serialization."""
        return {
            "url": self.url,
            "email": self.email,
            "api_token": self.api_token,
            "project_key": self.project_key,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JiraConfig":
        """Create a JiraConfig from a dictionary."""
        return cls(
            url=data.get("url"),
            email=data.get("email"),
            api_token=data.get("api_token"),
            project_key=data.get("project_key"),
        )


@dataclass
class OverseerConfig:
    """Overseer project configuration."""

    version: str = "0.1"
    active_task_id: str | None = None
    auto_log_sessions: bool = True
    jira: JiraConfig = field(default_factory=JiraConfig)

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "active_task_id": self.active_task_id,
            "auto_log_sessions": self.auto_log_sessions,
            "jira": self.jira.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OverseerConfig":
        """Create an OverseerConfig from a dictionary."""
        jira_data = data.get("jira", {})
        return cls(
            version=data.get("version", "0.1"),
            active_task_id=data.get("active_task_id"),
            auto_log_sessions=data.get("auto_log_sessions", True),
            jira=JiraConfig.from_dict(jira_data) if jira_data else JiraConfig(),
        )
