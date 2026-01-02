"""Tests for drift detection with Jira fallback."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from overseer.drift import DriftDetector, DriftResult, MatchStrength
from overseer.jira.models import JiraIssue


class TestDriftDetectorJiraFallback:
    """Tests for drift detection Jira fallback functionality."""

    @pytest.fixture
    def mock_jira_client(self):
        """Create a mock Jira client."""
        client = MagicMock()
        client.search_issues = AsyncMock()
        return client

    @pytest.fixture
    def jira_issue(self):
        """Create a sample Jira issue."""
        return JiraIssue(
            key="PROJ-99",
            summary="Related work from Jira",
            status="Open",
            issue_type="Task",
            assignee="user@example.com",
        )

    @pytest.mark.asyncio
    async def test_jira_fallback_when_no_local_match(
        self, mock_jira_client, jira_issue
    ):
        """Test Jira fallback when no local tasks match."""
        mock_jira_client.search_issues.return_value = [jira_issue]

        detector = DriftDetector(
            tasks=[],  # No local tasks
            jira_client=mock_jira_client,
            jira_project_key="PROJ",
        )

        result = await detector.check_drift_async("do some related work")

        assert result.jira_issue is not None
        assert result.jira_issue.key == "PROJ-99"
        assert result.match_strength == MatchStrength.WEAK
        assert "Jira search match" in result.match_reasons[0]

    @pytest.mark.asyncio
    async def test_no_jira_fallback_on_strong_local_match(self, mock_jira_client):
        """Test that Jira is not searched when local match is strong."""
        from datetime import datetime
        from overseer.models import Task, TaskStatus, TaskType, Origin

        local_task = Task(
            id="TASK-1",
            title="Fix the authentication bug",
            status=TaskStatus.ACTIVE,
            type=TaskType.BUG,
            created_by=Origin.HUMAN,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        detector = DriftDetector(
            tasks=[local_task],
            jira_client=mock_jira_client,
        )

        # Explicit task reference - should be strong match
        result = await detector.check_drift_async("Work on TASK-1")

        assert result.matched_task is not None
        assert result.matched_task.id == "TASK-1"
        assert result.match_strength == MatchStrength.STRONG
        # Jira should not be called for strong local matches
        mock_jira_client.search_issues.assert_not_called()

    @pytest.mark.asyncio
    async def test_jira_fallback_only_on_no_match(
        self, mock_jira_client, jira_issue
    ):
        """Test Jira fallback only triggers on NONE match strength."""
        from datetime import datetime
        from overseer.models import Task, TaskStatus, TaskType, Origin

        local_task = Task(
            id="TASK-1",
            title="Implement feature X",
            status=TaskStatus.ACTIVE,
            type=TaskType.FEATURE,
            created_by=Origin.HUMAN,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        mock_jira_client.search_issues.return_value = [jira_issue]

        detector = DriftDetector(
            tasks=[local_task],
            jira_client=mock_jira_client,
        )

        # This prompt has some overlap with the local task
        result = await detector.check_drift_async("add feature X implementation")

        # Should find local match (weak or strong)
        assert result.matched_task is not None
        # Jira should not override local matches
        assert result.jira_issue is None

    @pytest.mark.asyncio
    async def test_jira_client_error_handled_gracefully(self, mock_jira_client):
        """Test that Jira errors don't break drift detection."""
        mock_jira_client.search_issues.side_effect = Exception("Network error")

        detector = DriftDetector(
            tasks=[],
            jira_client=mock_jira_client,
        )

        # Should not raise, should return normal result
        result = await detector.check_drift_async("do some work")

        assert result.match_strength == MatchStrength.NONE
        assert result.jira_issue is None

    @pytest.mark.asyncio
    async def test_no_jira_fallback_without_client(self):
        """Test drift detection works without Jira client."""
        detector = DriftDetector(
            tasks=[],
            jira_client=None,  # No Jira configured
        )

        result = await detector.check_drift_async("do some work")

        assert result.match_strength == MatchStrength.NONE
        assert result.jira_issue is None
        assert result.suggested_title is not None

    @pytest.mark.asyncio
    async def test_jira_fallback_no_results(self, mock_jira_client):
        """Test Jira fallback when search returns no results."""
        mock_jira_client.search_issues.return_value = []

        detector = DriftDetector(
            tasks=[],
            jira_client=mock_jira_client,
        )

        result = await detector.check_drift_async("do some completely unrelated work")

        assert result.jira_issue is None
        assert result.match_strength == MatchStrength.NONE


class TestDriftResultJiraFormatting:
    """Tests for DriftResult formatting with Jira issues."""

    def test_format_result_jira_only_match(self):
        """Test formatting result when only Jira match exists."""
        jira_issue = JiraIssue(
            key="PROJ-42",
            summary="Jira matched issue",
            status="In Progress",
            issue_type="Bug",
            assignee=None,
        )

        result = DriftResult(
            matched_task=None,
            confidence=0.6,
            match_strength=MatchStrength.WEAK,
            match_reasons=["Jira search match: PROJ-42"],
            jira_issue=jira_issue,
        )

        formatted = result.format_result()

        assert "PROJ-42" in formatted
        assert "Jira matched issue" in formatted
        assert "In Progress" in formatted
        assert "Bug" in formatted

    def test_format_result_local_task_with_jira_key(self):
        """Test formatting result for local task linked to Jira."""
        from datetime import datetime
        from overseer.models import Task, TaskStatus, TaskType, Origin

        task = Task(
            id="TASK-5",
            title="Local task",
            status=TaskStatus.ACTIVE,
            type=TaskType.FEATURE,
            created_by=Origin.HUMAN,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            jira_key="PROJ-100",
        )

        result = DriftResult(
            matched_task=task,
            confidence=0.85,
            match_strength=MatchStrength.STRONG,
            match_reasons=["keyword match"],
        )

        formatted = result.format_result()

        assert "TASK-5" in formatted
        assert "PROJ-100" in formatted
