"""Tests for Jira API client."""

import pytest
import httpx
import respx

from overseer.jira import (
    JiraClient,
    JiraClientError,
    JiraAuthenticationError,
    JiraNotFoundError,
)


class TestJiraClient:
    """Tests for the JiraClient class."""

    @pytest.fixture
    def client(self):
        """Create a JiraClient instance for testing."""
        return JiraClient(
            url="https://test.atlassian.net",
            email="user@test.com",
            api_token="test-token",
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_assigned_issues(self, client):
        """Test fetching assigned issues."""
        respx.get("https://test.atlassian.net/rest/api/3/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "issues": [
                        {
                            "key": "PROJ-123",
                            "fields": {
                                "summary": "Test issue",
                                "status": {"name": "In Progress"},
                                "issuetype": {"name": "Bug"},
                                "assignee": {"emailAddress": "user@test.com"},
                            },
                        }
                    ]
                },
            )
        )

        async with client:
            issues = await client.get_assigned_issues()

        assert len(issues) == 1
        assert issues[0].key == "PROJ-123"
        assert issues[0].summary == "Test issue"
        assert issues[0].status == "In Progress"
        assert issues[0].issue_type == "Bug"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_assigned_issues_with_project_filter(self, client):
        """Test fetching issues filtered by project."""
        route = respx.get("https://test.atlassian.net/rest/api/3/search").mock(
            return_value=httpx.Response(200, json={"issues": []})
        )

        async with client:
            await client.get_assigned_issues(project_key="PROJ")

        # Verify the JQL includes project filter
        assert "PROJ" in route.calls[0].request.url.params.get("jql", "")

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_issue(self, client):
        """Test fetching a single issue."""
        respx.get("https://test.atlassian.net/rest/api/3/issue/PROJ-123").mock(
            return_value=httpx.Response(
                200,
                json={
                    "key": "PROJ-123",
                    "fields": {
                        "summary": "Single issue",
                        "status": {"name": "Open"},
                        "issuetype": {"name": "Task"},
                        "assignee": None,
                    },
                },
            )
        )

        async with client:
            issue = await client.get_issue("PROJ-123")

        assert issue.key == "PROJ-123"
        assert issue.summary == "Single issue"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_issue_not_found(self, client):
        """Test getting a non-existent issue."""
        respx.get("https://test.atlassian.net/rest/api/3/issue/PROJ-999").mock(
            return_value=httpx.Response(404)
        )

        async with client:
            with pytest.raises(JiraNotFoundError):
                await client.get_issue("PROJ-999")

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_issues(self, client):
        """Test searching issues by text."""
        respx.get("https://test.atlassian.net/rest/api/3/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "issues": [
                        {
                            "key": "PROJ-456",
                            "fields": {
                                "summary": "Related work",
                                "status": {"name": "Open"},
                                "issuetype": {"name": "Story"},
                                "assignee": None,
                            },
                        }
                    ]
                },
            )
        )

        async with client:
            issues = await client.search_issues("related work")

        assert len(issues) == 1
        assert issues[0].key == "PROJ-456"

    @respx.mock
    @pytest.mark.asyncio
    async def test_transition_issue(self, client):
        """Test transitioning an issue status."""
        # Mock get transitions
        respx.get(
            "https://test.atlassian.net/rest/api/3/issue/PROJ-123/transitions"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "transitions": [
                        {"id": "1", "name": "To Do"},
                        {"id": "2", "name": "In Progress"},
                        {"id": "3", "name": "Done"},
                    ]
                },
            )
        )

        # Mock perform transition
        respx.post(
            "https://test.atlassian.net/rest/api/3/issue/PROJ-123/transitions"
        ).mock(return_value=httpx.Response(204))

        async with client:
            result = await client.transition_issue("PROJ-123", "Done")

        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_transition_issue_invalid_transition(self, client):
        """Test transitioning to an unavailable status."""
        respx.get(
            "https://test.atlassian.net/rest/api/3/issue/PROJ-123/transitions"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "transitions": [
                        {"id": "1", "name": "To Do"},
                        {"id": "2", "name": "In Progress"},
                    ]
                },
            )
        )

        async with client:
            with pytest.raises(JiraClientError) as exc_info:
                await client.transition_issue("PROJ-123", "Invalid Status")

        assert "not available" in str(exc_info.value)
        assert "To Do" in str(exc_info.value)
        assert "In Progress" in str(exc_info.value)

    @respx.mock
    @pytest.mark.asyncio
    async def test_test_connection_success(self, client):
        """Test successful connection test."""
        respx.get("https://test.atlassian.net/rest/api/3/myself").mock(
            return_value=httpx.Response(
                200, json={"accountId": "123", "emailAddress": "user@test.com"}
            )
        )

        async with client:
            success, message = await client.test_connection()

        assert success is True
        assert "user@test.com" in message

    @respx.mock
    @pytest.mark.asyncio
    async def test_test_connection_failure(self, client):
        """Test failed connection test."""
        respx.get("https://test.atlassian.net/rest/api/3/myself").mock(
            return_value=httpx.Response(401)
        )

        async with client:
            success, message = await client.test_connection()

        assert success is False
        assert "401" in message

    @respx.mock
    @pytest.mark.asyncio
    async def test_authentication_error(self, client):
        """Test authentication error handling."""
        respx.get("https://test.atlassian.net/rest/api/3/search").mock(
            return_value=httpx.Response(401)
        )

        async with client:
            with pytest.raises(JiraAuthenticationError):
                await client.get_assigned_issues()

    @respx.mock
    @pytest.mark.asyncio
    async def test_api_error(self, client):
        """Test generic API error handling."""
        respx.get("https://test.atlassian.net/rest/api/3/search").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        async with client:
            with pytest.raises(JiraClientError) as exc_info:
                await client.get_assigned_issues()

        assert "500" in str(exc_info.value)
