"""Tests for Jira-specific models."""

from overseer.jira.models import JiraIssue
from overseer.models import TaskStatus, TaskType


class TestJiraIssue:
    """Tests for the JiraIssue model."""

    def test_to_local_task_type_bug(self):
        """Test mapping bug issue type."""
        issue = JiraIssue(
            key="TEST-1",
            summary="Bug issue",
            status="Open",
            issue_type="Bug",
            assignee=None,
        )
        assert issue.to_local_task_type() == TaskType.BUG

    def test_to_local_task_type_story(self):
        """Test mapping story issue type."""
        issue = JiraIssue(
            key="TEST-2",
            summary="Story issue",
            status="Open",
            issue_type="Story",
            assignee=None,
        )
        assert issue.to_local_task_type() == TaskType.FEATURE

    def test_to_local_task_type_task(self):
        """Test mapping task issue type."""
        issue = JiraIssue(
            key="TEST-3",
            summary="Task issue",
            status="Open",
            issue_type="Task",
            assignee=None,
        )
        assert issue.to_local_task_type() == TaskType.CHORE

    def test_to_local_task_type_unknown(self):
        """Test mapping unknown issue type defaults to FEATURE."""
        issue = JiraIssue(
            key="TEST-4",
            summary="Unknown issue",
            status="Open",
            issue_type="CustomType",
            assignee=None,
        )
        assert issue.to_local_task_type() == TaskType.FEATURE

    def test_to_local_status_done(self):
        """Test mapping done status."""
        for status in ["Done", "Resolved", "Closed", "Complete"]:
            issue = JiraIssue(
                key="TEST-1",
                summary="Test",
                status=status,
                issue_type="Task",
                assignee=None,
            )
            assert issue.to_local_status() == TaskStatus.DONE

    def test_to_local_status_blocked(self):
        """Test mapping blocked status."""
        for status in ["Blocked", "On Hold", "Impediment"]:
            issue = JiraIssue(
                key="TEST-1",
                summary="Test",
                status=status,
                issue_type="Task",
                assignee=None,
            )
            assert issue.to_local_status() == TaskStatus.BLOCKED

    def test_to_local_status_active(self):
        """Test mapping active status."""
        for status in ["In Progress", "In Review", "In Development"]:
            issue = JiraIssue(
                key="TEST-1",
                summary="Test",
                status=status,
                issue_type="Task",
                assignee=None,
            )
            assert issue.to_local_status() == TaskStatus.ACTIVE

    def test_to_local_status_backlog(self):
        """Test mapping backlog status (unknown statuses)."""
        for status in ["To Do", "Open", "Backlog", "New"]:
            issue = JiraIssue(
                key="TEST-1",
                summary="Test",
                status=status,
                issue_type="Task",
                assignee=None,
            )
            assert issue.to_local_status() == TaskStatus.BACKLOG

    def test_from_api_response(self):
        """Test creating JiraIssue from API response."""
        api_response = {
            "key": "PROJ-123",
            "fields": {
                "summary": "Test issue summary",
                "status": {"name": "In Progress"},
                "issuetype": {"name": "Bug"},
                "assignee": {"emailAddress": "user@example.com"},
                "description": "Issue description text",
            },
        }

        issue = JiraIssue.from_api_response(api_response)

        assert issue.key == "PROJ-123"
        assert issue.summary == "Test issue summary"
        assert issue.status == "In Progress"
        assert issue.issue_type == "Bug"
        assert issue.assignee == "user@example.com"
        assert issue.description == "Issue description text"

    def test_from_api_response_no_assignee(self):
        """Test creating JiraIssue when no assignee."""
        api_response = {
            "key": "PROJ-124",
            "fields": {
                "summary": "Unassigned issue",
                "status": {"name": "Open"},
                "issuetype": {"name": "Task"},
                "assignee": None,
            },
        }

        issue = JiraIssue.from_api_response(api_response)

        assert issue.key == "PROJ-124"
        assert issue.assignee is None

    def test_from_api_response_adf_description(self):
        """Test extracting text from ADF format description."""
        api_response = {
            "key": "PROJ-125",
            "fields": {
                "summary": "ADF test",
                "status": {"name": "Open"},
                "issuetype": {"name": "Task"},
                "assignee": None,
                "description": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": "First paragraph."},
                            ],
                        },
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": "Second paragraph."},
                            ],
                        },
                    ],
                },
            },
        }

        issue = JiraIssue.from_api_response(api_response)

        assert issue.description == "First paragraph. Second paragraph."
