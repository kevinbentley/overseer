"""Tests for drift detection."""

from datetime import datetime

import pytest

from overseer.drift import DriftDetector, DriftResult, MatchStrength
from overseer.models import Task, TaskStatus, TaskType, Origin


def make_task(
    id: str,
    title: str,
    task_type: TaskType = TaskType.FEATURE,
    context: str | None = None,
    linked_files: list[str] | None = None,
) -> Task:
    """Helper to create a task for testing."""
    now = datetime.now()
    return Task(
        id=id,
        title=title,
        status=TaskStatus.ACTIVE,
        type=task_type,
        created_by=Origin.HUMAN,
        context=context,
        linked_files=linked_files or [],
        created_at=now,
        updated_at=now,
    )


class TestDriftDetector:
    """Tests for DriftDetector."""

    def test_explicit_task_reference(self):
        """Test matching explicit TASK-N references."""
        tasks = [make_task("TASK-1", "Fix login bug")]
        detector = DriftDetector(tasks)

        result = detector.check_drift("Work on TASK-1")

        assert result.matched_task is not None
        assert result.matched_task.id == "TASK-1"
        assert result.match_strength == MatchStrength.STRONG
        assert result.confidence == 1.0

    def test_explicit_reference_not_found(self):
        """Test explicit reference to non-existent task."""
        tasks = [make_task("TASK-1", "Fix login bug")]
        detector = DriftDetector(tasks)

        result = detector.check_drift("Work on TASK-99")

        assert result.matched_task is None
        assert result.match_strength == MatchStrength.NONE
        assert "TASK-99" in (result.suggested_title or "")

    def test_keyword_match(self):
        """Test matching via keyword overlap."""
        tasks = [
            make_task("TASK-1", "Implement user authentication"),
            make_task("TASK-2", "Fix navbar styling"),
        ]
        detector = DriftDetector(tasks)

        result = detector.check_drift("Add authentication to the API")

        assert result.matched_task is not None
        assert result.matched_task.id == "TASK-1"
        assert "authentication" in str(result.match_reasons).lower()

    def test_file_context_match(self):
        """Test matching via linked files."""
        tasks = [
            make_task(
                "TASK-1",
                "Fix navbar styling",
                linked_files=["src/components/nav.tsx", "styles/global.css"],
            ),
        ]
        detector = DriftDetector(tasks)

        result = detector.check_drift("Update the nav component colors")

        assert result.matched_task is not None
        assert result.matched_task.id == "TASK-1"

    def test_bug_type_matching(self):
        """Test matching bug-related prompts to bug tasks."""
        tasks = [
            make_task("TASK-1", "Fix login timeout issue", task_type=TaskType.BUG),
            make_task("TASK-2", "Add new dashboard", task_type=TaskType.FEATURE),
        ]
        detector = DriftDetector(tasks)

        result = detector.check_drift("There's a bug with the login")

        assert result.matched_task is not None
        assert result.matched_task.id == "TASK-1"

    def test_no_match_suggests_title(self):
        """Test that no match suggests a new task title."""
        tasks = [make_task("TASK-1", "Fix navbar styling")]
        detector = DriftDetector(tasks)

        result = detector.check_drift("Implement user profile page")

        assert result.match_strength == MatchStrength.NONE
        assert result.suggested_title is not None
        assert "profile" in result.suggested_title.lower()

    def test_informational_query_not_drift(self):
        """Test that informational queries are not flagged as drift."""
        tasks = [make_task("TASK-1", "Fix navbar styling")]
        detector = DriftDetector(tasks)

        queries = [
            "What's the status of the project?",
            "Show me the current tasks",
            "Explain how the auth system works",
            "Where is the config file?",
        ]

        for query in queries:
            result = detector.check_drift(query)
            assert result.match_strength == MatchStrength.STRONG, f"Failed for: {query}"

    def test_context_matching(self):
        """Test matching via task context."""
        tasks = [
            make_task(
                "TASK-1",
                "Implement auth",
                context="Use NextAuth.js for authentication. See auth.ts for setup.",
            ),
        ]
        detector = DriftDetector(tasks)

        result = detector.check_drift("Configure NextAuth providers")

        assert result.matched_task is not None
        assert result.matched_task.id == "TASK-1"

    def test_empty_prompt(self):
        """Test handling of empty prompt."""
        tasks = [make_task("TASK-1", "Fix bug")]
        detector = DriftDetector(tasks)

        result = detector.check_drift("")

        assert result.suggested_title == "Empty request"

    def test_empty_task_list(self):
        """Test with no active tasks."""
        detector = DriftDetector([])

        result = detector.check_drift("Add login feature")

        assert result.matched_task is None
        assert result.match_strength == MatchStrength.NONE

    def test_suggested_title_cleanup(self):
        """Test that suggested titles are cleaned up."""
        tasks = [make_task("TASK-1", "Unrelated task")]
        detector = DriftDetector(tasks)

        result = detector.check_drift("Please help me add a logout button")

        assert result.suggested_title is not None
        # Should remove "please help me"
        assert not result.suggested_title.lower().startswith("please")
        assert "logout" in result.suggested_title.lower()

    def test_bug_prefix_added(self):
        """Test that bug-related suggestions get Fix prefix."""
        tasks = [make_task("TASK-1", "Unrelated task")]
        detector = DriftDetector(tasks)

        result = detector.check_drift("The button is broken and crashes the app")

        assert result.suggested_title is not None
        assert result.suggested_title.startswith("Fix:")


class TestDriftResult:
    """Tests for DriftResult."""

    def test_is_drift_property(self):
        """Test the is_drift property."""
        result_drift = DriftResult(match_strength=MatchStrength.NONE)
        result_match = DriftResult(match_strength=MatchStrength.STRONG)

        assert result_drift.is_drift is True
        assert result_match.is_drift is False

    def test_format_result_with_match(self):
        """Test formatting result with a match."""
        task = make_task("TASK-1", "Fix bug")
        result = DriftResult(
            matched_task=task,
            confidence=0.85,
            match_strength=MatchStrength.STRONG,
            match_reasons=["keyword match"],
        )

        formatted = result.format_result()

        assert "TASK-1" in formatted
        assert "Fix bug" in formatted
        assert "85%" in formatted
        assert "strong" in formatted

    def test_format_result_no_match(self):
        """Test formatting result with no match."""
        result = DriftResult(
            suggested_title="New feature request",
        )

        formatted = result.format_result()

        assert "No matching task" in formatted
        assert "New feature request" in formatted
