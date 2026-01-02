"""Jira REST API client wrapper."""

from typing import Any

import httpx

from .models import JiraIssue


class JiraClientError(Exception):
    """Base exception for Jira client errors."""

    pass


class JiraAuthenticationError(JiraClientError):
    """Authentication failed."""

    pass


class JiraNotFoundError(JiraClientError):
    """Resource not found."""

    pass


class JiraClient:
    """Async Jira REST API client using httpx."""

    def __init__(self, url: str, email: str, api_token: str):
        """Initialize the client.

        Args:
            url: Jira instance URL (e.g., https://company.atlassian.net)
            email: User email for authentication
            api_token: Jira API token
        """
        self.base_url = url.rstrip("/")
        self.auth = (email, api_token)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "JiraClient":
        self._client = httpx.AsyncClient(
            base_url=f"{self.base_url}/rest/api/3",
            auth=self.auth,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=30.0,
        )
        return self

    async def __aexit__(self, *args) -> None:
        if self._client:
            await self._client.aclose()

    async def _request(
        self, method: str, endpoint: str, **kwargs
    ) -> dict[str, Any]:
        """Make an API request with error handling."""
        if not self._client:
            raise JiraClientError("Client not initialized. Use async with context.")

        response = await self._client.request(method, endpoint, **kwargs)

        if response.status_code == 401:
            raise JiraAuthenticationError("Invalid credentials")
        elif response.status_code == 404:
            raise JiraNotFoundError(f"Not found: {endpoint}")
        elif response.status_code >= 400:
            raise JiraClientError(
                f"API error {response.status_code}: {response.text}"
            )

        return response.json() if response.content else {}

    async def get_assigned_issues(
        self, project_key: str | None = None, max_results: int = 50
    ) -> list[JiraIssue]:
        """Fetch issues assigned to the authenticated user.

        Args:
            project_key: Optional project filter
            max_results: Maximum issues to return

        Returns:
            List of JiraIssue objects
        """
        jql = "assignee = currentUser() AND resolution = Unresolved"
        if project_key:
            jql += f" AND project = {project_key}"
        jql += " ORDER BY updated DESC"

        data = await self._request(
            "GET",
            "/search",
            params={
                "jql": jql,
                "maxResults": max_results,
                "fields": "summary,status,issuetype,assignee,description",
            },
        )

        return [
            JiraIssue.from_api_response(issue) for issue in data.get("issues", [])
        ]

    async def get_issue(self, key: str) -> JiraIssue:
        """Fetch a specific issue by key.

        Args:
            key: Issue key (e.g., PROJ-123)

        Returns:
            JiraIssue object
        """
        data = await self._request(
            "GET",
            f"/issue/{key}",
            params={"fields": "summary,status,issuetype,assignee,description"},
        )
        return JiraIssue.from_api_response(data)

    async def search_issues(
        self, query: str, project_key: str | None = None, max_results: int = 10
    ) -> list[JiraIssue]:
        """Search issues by text query.

        Args:
            query: Search text
            project_key: Optional project filter
            max_results: Maximum issues to return

        Returns:
            List of matching JiraIssue objects
        """
        # Escape special JQL characters in query
        escaped_query = query.replace('"', '\\"')
        jql = f'text ~ "{escaped_query}" AND resolution = Unresolved'
        if project_key:
            jql += f" AND project = {project_key}"
        jql += " ORDER BY updated DESC"

        data = await self._request(
            "GET",
            "/search",
            params={
                "jql": jql,
                "maxResults": max_results,
                "fields": "summary,status,issuetype,assignee,description",
            },
        )

        return [
            JiraIssue.from_api_response(issue) for issue in data.get("issues", [])
        ]

    async def transition_issue(self, key: str, transition_name: str) -> bool:
        """Transition an issue to a new status.

        Args:
            key: Issue key (e.g., PROJ-123)
            transition_name: Target status name (e.g., "Done", "In Progress")

        Returns:
            True if transition succeeded
        """
        # First, get available transitions
        transitions_data = await self._request("GET", f"/issue/{key}/transitions")
        transitions = transitions_data.get("transitions", [])

        # Find matching transition (case-insensitive)
        target_transition = None
        for t in transitions:
            if t["name"].lower() == transition_name.lower():
                target_transition = t
                break

        if not target_transition:
            available = [t["name"] for t in transitions]
            raise JiraClientError(
                f"Transition '{transition_name}' not available for {key}. "
                f"Available transitions: {', '.join(available)}"
            )

        # Execute transition
        await self._request(
            "POST",
            f"/issue/{key}/transitions",
            json={"transition": {"id": target_transition["id"]}},
        )
        return True

    async def get_project_issue_types(self, project_key: str) -> list[str]:
        """Get available issue types for a project.

        Args:
            project_key: Project key (e.g., PROJ)

        Returns:
            List of issue type names available in the project
        """
        data = await self._request(
            "GET",
            f"/project/{project_key}",
        )
        issue_types = data.get("issueTypes", [])
        return [it["name"] for it in issue_types if not it.get("subtask", False)]

    async def create_issue(
        self,
        project_key: str,
        summary: str,
        issue_type: str = "Task",
        description: str | None = None,
    ) -> JiraIssue:
        """Create a new Jira issue.

        Args:
            project_key: Project key (e.g., PROJ)
            summary: Issue title/summary
            issue_type: Issue type name (e.g., Task, Bug, Story)
            description: Optional description text

        Returns:
            Created JiraIssue object
        """
        # Build the issue payload
        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }

        # Add description in Atlassian Document Format (ADF)
        if description:
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            }

        data = await self._request("POST", "/issue", json={"fields": fields})

        # Fetch the created issue to get full details
        return await self.get_issue(data["key"])

    async def test_connection(self, debug: bool = False) -> tuple[bool, str]:
        """Test if the credentials are valid.

        Args:
            debug: If True, return detailed debug info

        Returns:
            Tuple of (success, message)
        """
        if not self._client:
            return False, "Client not initialized"

        full_url = f"{self.base_url}/rest/api/3/myself"

        try:
            response = await self._client.get("/myself")

            if debug:
                debug_info = (
                    f"URL: {full_url}\n"
                    f"Status: {response.status_code}\n"
                    f"Response: {response.text[:500] if response.text else '(empty)'}"
                )
            else:
                debug_info = ""

            if response.status_code == 200:
                data = response.json()
                user_email = data.get("emailAddress", data.get("accountId", "unknown"))
                return True, f"Connected as: {user_email}" + (f"\n{debug_info}" if debug else "")
            elif response.status_code == 401:
                return False, f"Authentication failed (401){': ' + debug_info if debug else ''}"
            elif response.status_code == 403:
                return False, f"Access forbidden (403) - check API token permissions{': ' + debug_info if debug else ''}"
            else:
                return False, f"Unexpected status {response.status_code}{': ' + debug_info if debug else ''}"

        except httpx.ConnectError as e:
            return False, f"Connection error: Could not reach {self.base_url} - {e}"
        except httpx.TimeoutException:
            return False, f"Timeout: Server at {self.base_url} did not respond"
        except Exception as e:
            return False, f"Error: {type(e).__name__}: {e}"
