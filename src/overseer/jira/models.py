"""Jira-specific data models."""

from dataclasses import dataclass
from typing import Any

from ..models import TaskStatus, TaskType


@dataclass
class JiraIssue:
    """Representation of a Jira issue."""

    key: str  # e.g., "PROJ-123"
    summary: str  # Issue title
    status: str  # e.g., "In Progress", "Done"
    issue_type: str  # e.g., "Bug", "Story", "Task"
    assignee: str | None  # Email of assignee
    description: str | None = None

    def to_local_task_type(self) -> TaskType:
        """Map Jira issue type to Overseer TaskType."""
        mapping = {
            "bug": TaskType.BUG,
            "story": TaskType.FEATURE,
            "task": TaskType.CHORE,
            "epic": TaskType.FEATURE,
            "sub-task": TaskType.CHORE,
            "technical debt": TaskType.DEBT,
            "improvement": TaskType.FEATURE,
            "new feature": TaskType.FEATURE,
        }
        return mapping.get(self.issue_type.lower(), TaskType.FEATURE)

    def to_local_status(self) -> TaskStatus:
        """Map Jira status to Overseer TaskStatus."""
        status_lower = self.status.lower()
        if status_lower in ("done", "resolved", "closed", "complete"):
            return TaskStatus.DONE
        elif status_lower in ("blocked", "on hold", "impediment"):
            return TaskStatus.BLOCKED
        elif status_lower in ("in progress", "in review", "in development"):
            return TaskStatus.ACTIVE
        else:
            return TaskStatus.BACKLOG

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "JiraIssue":
        """Create a JiraIssue from Jira API response."""
        fields = data.get("fields", {})
        assignee = fields.get("assignee")

        # Handle description - can be string or ADF document
        description = fields.get("description")
        if isinstance(description, dict):
            # ADF format - extract text content
            description = cls._extract_adf_text(description)

        return cls(
            key=data["key"],
            summary=fields.get("summary", ""),
            status=fields.get("status", {}).get("name", "Unknown"),
            issue_type=fields.get("issuetype", {}).get("name", "Task"),
            assignee=assignee.get("emailAddress") if assignee else None,
            description=description,
        )

    @staticmethod
    def _extract_adf_text(adf: dict[str, Any]) -> str | None:
        """Extract plain text from Atlassian Document Format."""
        if not adf or adf.get("type") != "doc":
            return None

        texts = []
        for content in adf.get("content", []):
            if content.get("type") == "paragraph":
                for item in content.get("content", []):
                    if item.get("type") == "text":
                        texts.append(item.get("text", ""))
        return " ".join(texts) if texts else None
