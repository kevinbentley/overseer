"""Drift detection logic for comparing prompts to active tasks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from ..models import Task

if TYPE_CHECKING:
    from ..jira import JiraClient, JiraIssue


class MatchStrength(Enum):
    """Confidence level of a task match."""

    STRONG = "strong"  # > 0.8: Proceed without asking
    WEAK = "weak"  # 0.4-0.8: Proceed but mention the assumed task
    NONE = "none"  # < 0.4: Ask user to confirm/create task


@dataclass
class DriftResult:
    """Result of drift detection analysis."""

    matched_task: Task | None = None
    confidence: float = 0.0
    match_strength: MatchStrength = MatchStrength.NONE
    suggested_title: str | None = None
    match_reasons: list[str] = field(default_factory=list)
    jira_issue: JiraIssue | None = None

    @property
    def is_drift(self) -> bool:
        """Returns True if this appears to be scope drift (no strong match)."""
        return self.match_strength == MatchStrength.NONE

    def format_result(self) -> str:
        """Format the result for display."""
        if self.jira_issue and not self.matched_task:
            # Jira-only match
            reasons = ", ".join(self.match_reasons) if self.match_reasons else "Jira search"
            return (
                f"Found Jira issue: {self.jira_issue.key}\n"
                f"Summary: {self.jira_issue.summary}\n"
                f"Status: {self.jira_issue.status} | Type: {self.jira_issue.issue_type}\n"
                f"Reason: {reasons}"
            )
        elif self.matched_task:
            reasons = ", ".join(self.match_reasons) if self.match_reasons else "keyword match"
            result = (
                f"Matched {self.matched_task.id}: {self.matched_task.title}\n"
                f"Confidence: {self.confidence:.0%} ({self.match_strength.value})\n"
                f"Reason: {reasons}"
            )
            if self.matched_task.jira_key:
                result += f"\nJira: {self.matched_task.jira_key}"
            return result
        else:
            return (
                f"No matching task found.\n"
                f"Suggested title: {self.suggested_title or 'Unknown task'}"
            )


# Common stop words to filter out
STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
    "from", "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "under", "again", "further", "then", "once", "here",
    "there", "when", "where", "why", "how", "all", "each", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "just", "also", "now", "and",
    "but", "or", "if", "because", "until", "while", "although", "though",
    "i", "me", "my", "we", "our", "you", "your", "it", "its", "this",
    "that", "these", "those", "what", "which", "who", "whom", "please",
    "help", "want", "like", "get", "make", "let", "try", "use",
}

# Keywords that indicate specific task types
BUG_INDICATORS = {"bug", "fix", "broken", "error", "crash", "issue", "problem", "fail", "wrong"}
FEATURE_INDICATORS = {"add", "create", "implement", "build", "new", "feature"}
REFACTOR_INDICATORS = {"refactor", "clean", "improve", "optimize", "update", "change"}


class DriftDetector:
    """Detects scope drift by comparing prompts to active tasks."""

    def __init__(
        self,
        tasks: list[Task],
        jira_client: JiraClient | None = None,
        jira_project_key: str | None = None,
    ):
        """Initialize with a list of active tasks.

        Args:
            tasks: List of active tasks to match against.
            jira_client: Optional Jira client for fallback search.
            jira_project_key: Optional Jira project key to filter searches.
        """
        self.tasks = tasks
        self.jira_client = jira_client
        self.jira_project_key = jira_project_key

    def check_drift(self, prompt: str) -> DriftResult:
        """
        Check if a prompt matches any active task.

        Returns a DriftResult with match information.
        """
        # Handle empty prompt
        if not prompt.strip():
            return DriftResult(suggested_title="Empty request")

        # Check for explicit task reference first
        explicit_match = self._check_explicit_reference(prompt)
        if explicit_match:
            return explicit_match

        # Check for informational queries (not drift)
        if self._is_informational_query(prompt):
            return DriftResult(
                confidence=1.0,
                match_strength=MatchStrength.STRONG,
                match_reasons=["Informational query - not a task"],
            )

        # Extract keywords from prompt
        prompt_keywords = self._extract_keywords(prompt)
        prompt_files = self._extract_file_references(prompt)

        # Score each task
        best_match: DriftResult | None = None
        best_score = 0.0

        for task in self.tasks:
            score, reasons = self._score_task_match(
                task, prompt_keywords, prompt_files, prompt
            )
            if score > best_score:
                best_score = score
                best_match = DriftResult(
                    matched_task=task,
                    confidence=score,
                    match_strength=self._score_to_strength(score),
                    match_reasons=reasons,
                )

        # If no good match, suggest a new task title
        if best_match is None or best_score < 0.4:
            suggested = self._suggest_title(prompt)
            return DriftResult(
                matched_task=best_match.matched_task if best_match else None,
                confidence=best_score,
                match_strength=MatchStrength.NONE,
                suggested_title=suggested,
                match_reasons=best_match.match_reasons if best_match else [],
            )

        return best_match

    async def check_drift_async(self, prompt: str) -> DriftResult:
        """
        Check if a prompt matches any active task, falling back to Jira search.

        This async version first runs the local task check, then if no strong
        match is found and a Jira client is configured, searches Jira for
        potentially related issues.

        Returns a DriftResult with match information.
        """
        # First, check local tasks
        result = self.check_drift(prompt)

        # If we found a strong match or Jira isn't configured, return early
        if result.match_strength == MatchStrength.STRONG or not self.jira_client:
            return result

        # For weak or no match, try Jira fallback
        if result.match_strength == MatchStrength.NONE:
            jira_result = await self._check_jira_fallback(prompt)
            if jira_result:
                return jira_result

        return result

    async def _check_jira_fallback(self, prompt: str) -> DriftResult | None:
        """Search Jira for matching issues when no local match found."""
        if not self.jira_client:
            return None

        # Extract meaningful search terms
        keywords = self._extract_keywords(prompt)
        if len(keywords) < 2:
            return None

        # Build search query from top keywords
        search_query = " ".join(list(keywords)[:5])

        try:
            issues = await self.jira_client.search_issues(
                search_query, self.jira_project_key
            )
        except Exception:
            # Silently fail on Jira errors - local check already returned
            return None

        if not issues:
            return None

        # Return the best Jira match
        best_issue = issues[0]
        return DriftResult(
            matched_task=None,
            confidence=0.6,  # Moderate confidence for Jira matches
            match_strength=MatchStrength.WEAK,
            suggested_title=None,
            match_reasons=[f"Jira search match: {best_issue.key}"],
            jira_issue=best_issue,
        )

    def _check_explicit_reference(self, prompt: str) -> DriftResult | None:
        """Check for explicit task ID references like 'TASK-42'."""
        match = re.search(r"\bTASK-(\d+)\b", prompt, re.IGNORECASE)
        if match:
            task_id = f"TASK-{match.group(1)}"
            for task in self.tasks:
                if task.id.upper() == task_id.upper():
                    return DriftResult(
                        matched_task=task,
                        confidence=1.0,
                        match_strength=MatchStrength.STRONG,
                        match_reasons=["Explicit task reference"],
                    )
            # Task ID mentioned but not found in active tasks
            return DriftResult(
                confidence=0.0,
                match_strength=MatchStrength.NONE,
                suggested_title=f"Work on {task_id}",
                match_reasons=[f"Referenced {task_id} but not in active tasks"],
            )
        return None

    def _is_informational_query(self, prompt: str) -> bool:
        """Check if this is an informational query, not a task request."""
        prompt_lower = prompt.lower().strip()

        # Questions about status/progress
        info_patterns = [
            r"^what('s| is) the status",
            r"^how('s| is) .* going",
            r"^show me",
            r"^list( all)?",
            r"^tell me about",
            r"^explain",
            r"^what does .* do",
            r"^how does .* work",
            r"^where is",
            r"^can you (show|explain|tell)",
        ]

        for pattern in info_patterns:
            if re.match(pattern, prompt_lower):
                return True

        return False

    def _extract_keywords(self, text: str) -> set[str]:
        """Extract meaningful keywords from text."""
        # Lowercase and split into words
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9_]*", text.lower())

        # Filter out stop words and short words
        keywords = {w for w in words if w not in STOP_WORDS and len(w) > 2}

        return keywords

    def _extract_file_references(self, text: str) -> set[str]:
        """Extract file path references from text."""
        # Match common file patterns
        patterns = [
            r"[\w\-/]+\.[a-zA-Z]{1,4}",  # file.ext
            r"[\w\-]+(?:\.[\w\-]+)+",  # path.to.module
        ]

        files = set()
        for pattern in patterns:
            matches = re.findall(pattern, text)
            files.update(m.lower() for m in matches)

        return files

    def _score_task_match(
        self,
        task: Task,
        prompt_keywords: set[str],
        prompt_files: set[str],
        prompt: str,
    ) -> tuple[float, list[str]]:
        """Score how well a task matches the prompt."""
        scores: list[float] = []
        reasons: list[str] = []

        # 1. Keyword overlap with title and context
        task_text = task.title
        if task.context:
            task_text += " " + task.context
        task_keywords = self._extract_keywords(task_text)

        if prompt_keywords and task_keywords:
            overlap = prompt_keywords & task_keywords
            keyword_score = len(overlap) / max(len(prompt_keywords), 1)
            if overlap:
                scores.append(keyword_score * 0.6)  # Weight: 60%
                reasons.append(f"Keywords: {', '.join(sorted(overlap)[:3])}")

        # 2. File context matching
        if task.linked_files and prompt_files:
            task_files = {f.lower() for f in task.linked_files}
            file_overlap = prompt_files & task_files
            if file_overlap:
                scores.append(0.8)  # Strong signal
                reasons.append(f"Files: {', '.join(sorted(file_overlap)[:2])}")

        # Check if prompt mentions files similar to linked files
        for task_file in task.linked_files:
            file_base = re.sub(r"\.[^.]+$", "", task_file.split("/")[-1]).lower()
            if file_base in prompt.lower():
                scores.append(0.5)
                reasons.append(f"File reference: {task_file}")
                break

        # 3. Task type inference
        prompt_lower = prompt.lower()
        if task.type.value == "bug" and any(w in prompt_lower for w in BUG_INDICATORS):
            scores.append(0.3)
            reasons.append("Bug-related request")
        elif task.type.value == "feature" and any(w in prompt_lower for w in FEATURE_INDICATORS):
            scores.append(0.2)
            reasons.append("Feature-related request")

        # Calculate weighted average
        if not scores:
            return 0.0, []

        final_score = min(sum(scores), 1.0)  # Cap at 1.0
        return final_score, reasons

    def _score_to_strength(self, score: float) -> MatchStrength:
        """Convert a numeric score to match strength."""
        if score > 0.8:
            return MatchStrength.STRONG
        elif score >= 0.4:
            return MatchStrength.WEAK
        else:
            return MatchStrength.NONE

    def _suggest_title(self, prompt: str) -> str:
        """Suggest a task title based on the prompt."""
        # Clean up the prompt for use as a title
        title = prompt.strip()

        # Remove common prefixes
        prefixes = [
            r"^(please\s+)?",
            r"^(can you\s+)?",
            r"^(could you\s+)?",
            r"^(i want to\s+)?",
            r"^(i need to\s+)?",
            r"^(help me\s+)?",
            r"^(let's\s+)?",
        ]
        for prefix in prefixes:
            title = re.sub(prefix, "", title, flags=re.IGNORECASE)

        # Capitalize and truncate
        title = title.strip().capitalize()
        if len(title) > 60:
            title = title[:57] + "..."

        # Infer task type for better title
        title_lower = title.lower()
        if any(w in title_lower for w in BUG_INDICATORS):
            if not title_lower.startswith("fix"):
                title = "Fix: " + title
        elif any(w in title_lower for w in FEATURE_INDICATORS):
            pass  # Already descriptive
        elif any(w in title_lower for w in REFACTOR_INDICATORS):
            pass  # Already descriptive

        return title or "New task"
