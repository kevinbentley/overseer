"""Overseer MCP Server."""

import os
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .store import JsonTaskStore, SessionStore
from .models import TaskStatus, TaskType, Origin
from .drift import DriftDetector
from .jira import JiraClient, JiraClientError, JiraNotFoundError


def get_root_path() -> Path:
    """Get the root path from environment or current directory."""
    root = os.environ.get("OVERSEER_ROOT")
    if root:
        return Path(root)
    return Path.cwd()


# Initialize stores
def get_stores() -> tuple[JsonTaskStore, SessionStore]:
    """Get initialized stores."""
    root = get_root_path()
    return JsonTaskStore(root), SessionStore(root)


# Create the MCP server
server = Server("overseer")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="read_active_tasks",
            description="Read the current task list. Use this before starting work to check what tasks are active and avoid scope drift.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["active", "backlog", "done", "blocked"],
                        "description": "Filter by status. Defaults to 'active' if not specified.",
                    },
                    "include_context": {
                        "type": "boolean",
                        "description": "Include full task context and linked files. Defaults to true.",
                        "default": True,
                    },
                },
            },
        ),
        Tool(
            name="create_task",
            description="Create a new task. Use this to log bugs, feature requests, or technical debt discovered during work.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Brief description of the task.",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["feature", "bug", "debt", "chore"],
                        "description": "Type of task.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "backlog"],
                        "description": "Initial status. Defaults to 'backlog'.",
                        "default": "backlog",
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional notes or implementation hints.",
                    },
                    "linked_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "File paths associated with this task.",
                    },
                },
                "required": ["title", "type"],
            },
        ),
        Tool(
            name="update_task_status",
            description="Update a task's status. Use this to mark tasks as done, blocked, or move them between active and backlog.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task ID (e.g., TASK-1).",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "backlog", "done", "blocked"],
                        "description": "New status for the task.",
                    },
                },
                "required": ["task_id", "status"],
            },
        ),
        Tool(
            name="log_work_session",
            description="Log a work session summary. Use this after completing significant work to maintain a development journal.",
            inputSchema={
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Brief summary of what was accomplished.",
                    },
                    "files_touched": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of files modified during this session.",
                    },
                    "task_id": {
                        "type": "string",
                        "description": "Associated task ID if this work was for a specific task.",
                    },
                },
                "required": ["summary"],
            },
        ),
        Tool(
            name="check_drift",
            description="Check if a user request matches any active task. Use this to detect scope drift before starting work. Returns match information or suggests creating a new task.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The user's request or prompt to check against active tasks.",
                    },
                },
                "required": ["prompt"],
            },
        ),
        Tool(
            name="pull_jira_issues",
            description="Fetch your assigned Jira issues. Optionally import them as local tasks. Requires Jira to be configured.",
            inputSchema={
                "type": "object",
                "properties": {
                    "import_as_tasks": {
                        "type": "boolean",
                        "description": "If true, create local tasks for each Jira issue. Default: false (list only).",
                        "default": False,
                    },
                    "project_key": {
                        "type": "string",
                        "description": "Filter by Jira project key (uses default from config if not specified).",
                    },
                },
            },
        ),
        Tool(
            name="link_jira_issue",
            description="Link a local task to a Jira issue by key. This allows syncing status between Overseer and Jira.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Local task ID (e.g., TASK-1).",
                    },
                    "jira_key": {
                        "type": "string",
                        "description": "Jira issue key (e.g., PROJ-123).",
                    },
                },
                "required": ["task_id", "jira_key"],
            },
        ),
        Tool(
            name="sync_jira_status",
            description="Sync a local task's status to its linked Jira issue. Only works for tasks with a jira_key.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Local task ID (e.g., TASK-1).",
                    },
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="push_task_to_jira",
            description="Create a new Jira issue from a local task. The task will be linked to the new Jira issue.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Local task ID (e.g., TASK-1).",
                    },
                    "project_key": {
                        "type": "string",
                        "description": "Jira project key (uses default from config if not specified).",
                    },
                },
                "required": ["task_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    task_store, session_store = get_stores()

    if name == "read_active_tasks":
        return await handle_read_active_tasks(task_store, arguments)
    elif name == "create_task":
        return await handle_create_task(task_store, arguments)
    elif name == "update_task_status":
        return await handle_update_task_status(task_store, arguments)
    elif name == "log_work_session":
        return await handle_log_work_session(session_store, arguments)
    elif name == "check_drift":
        return await handle_check_drift(task_store, arguments)
    elif name == "pull_jira_issues":
        return await handle_pull_jira_issues(task_store, arguments)
    elif name == "link_jira_issue":
        return await handle_link_jira_issue(task_store, arguments)
    elif name == "sync_jira_status":
        return await handle_sync_jira_status(task_store, arguments)
    elif name == "push_task_to_jira":
        return await handle_push_task_to_jira(task_store, arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def handle_read_active_tasks(
    store: JsonTaskStore, arguments: dict
) -> list[TextContent]:
    """Handle read_active_tasks tool call."""
    try:
        status_str = arguments.get("status", "active")
        status = TaskStatus(status_str)
        include_context = arguments.get("include_context", True)

        tasks = store.list_tasks(status=status)

        if not tasks:
            return [
                TextContent(
                    type="text",
                    text=f"No tasks with status '{status_str}'.",
                )
            ]

        lines = [f"## Tasks ({status_str})", ""]
        for task in tasks:
            lines.append(task.format_display(include_context=include_context))
            lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    except FileNotFoundError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error reading tasks: {e}")]


async def handle_create_task(
    store: JsonTaskStore, arguments: dict
) -> list[TextContent]:
    """Handle create_task tool call."""
    try:
        title = arguments["title"]
        task_type = TaskType(arguments["type"])
        status = TaskStatus(arguments.get("status", "backlog"))
        context = arguments.get("context")
        linked_files = arguments.get("linked_files", [])

        task = store.create_task(
            title=title,
            task_type=task_type,
            status=status,
            created_by=Origin.AGENT,
            context=context,
            linked_files=linked_files,
        )

        return [
            TextContent(
                type="text",
                text=f"Created task {task.id}: {task.title}\nStatus: {task.status.value}\nType: {task.type.value}",
            )
        ]

    except FileNotFoundError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error creating task: {e}")]


async def handle_update_task_status(
    store: JsonTaskStore, arguments: dict
) -> list[TextContent]:
    """Handle update_task_status tool call."""
    try:
        task_id = arguments["task_id"]
        new_status = TaskStatus(arguments["status"])

        task = store.update_task(task_id, status=new_status)

        if task is None:
            return [TextContent(type="text", text=f"Task {task_id} not found.")]

        return [
            TextContent(
                type="text",
                text=f"Updated {task.id}: status changed to '{task.status.value}'",
            )
        ]

    except FileNotFoundError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error updating task: {e}")]


async def handle_log_work_session(
    store: SessionStore, arguments: dict
) -> list[TextContent]:
    """Handle log_work_session tool call."""
    try:
        summary = arguments["summary"]
        files_touched = arguments.get("files_touched", [])
        task_id = arguments.get("task_id")

        session = store.log_session(
            summary=summary,
            files_touched=files_touched,
            task_id=task_id,
        )

        result = f"Logged session {session.id}: {session.summary}"
        if task_id:
            result += f" (linked to {task_id})"

        return [TextContent(type="text", text=result)]

    except FileNotFoundError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error logging session: {e}")]


async def handle_check_drift(
    store: JsonTaskStore, arguments: dict
) -> list[TextContent]:
    """Handle check_drift tool call."""
    try:
        prompt = arguments["prompt"]

        # Get active tasks for comparison
        active_tasks = store.list_tasks(status=TaskStatus.ACTIVE)

        if not active_tasks:
            # Even with no local tasks, try Jira if configured
            config = store.get_config()
            if config.jira.is_configured():
                # Create detector with Jira fallback only
                async with JiraClient(
                    config.jira.url, config.jira.email, config.jira.api_token
                ) as jira_client:
                    detector = DriftDetector(
                        [], jira_client=jira_client, jira_project_key=config.jira.project_key
                    )
                    result = await detector.check_drift_async(prompt)

                    if result.jira_issue:
                        return [
                            TextContent(
                                type="text",
                                text=(
                                    f"No local tasks, but found related Jira issue!\n"
                                    f"{result.format_result()}\n\n"
                                    f"Use pull_jira_issues to import it, or link_jira_issue to link it."
                                ),
                            )
                        ]

            return [
                TextContent(
                    type="text",
                    text=(
                        "No active tasks found.\n"
                        "This appears to be new work. Consider creating a task first with create_task."
                    ),
                )
            ]

        # Load Jira config for fallback
        config = store.get_config()
        jira_client = None

        if config.jira.is_configured():
            # Run with Jira fallback
            async with JiraClient(
                config.jira.url, config.jira.email, config.jira.api_token
            ) as jira_client:
                detector = DriftDetector(
                    active_tasks,
                    jira_client=jira_client,
                    jira_project_key=config.jira.project_key,
                )
                result = await detector.check_drift_async(prompt)
        else:
            # Run without Jira
            detector = DriftDetector(active_tasks)
            result = detector.check_drift(prompt)

        # Format response based on match strength
        if result.match_strength.value == "strong":
            return [
                TextContent(
                    type="text",
                    text=(
                        f"✓ Strong match found!\n"
                        f"{result.format_result()}\n\n"
                        f"Proceed with the work."
                    ),
                )
            ]
        elif result.match_strength.value == "weak":
            # Check if this is a Jira-only match
            if result.jira_issue and not result.matched_task:
                return [
                    TextContent(
                        type="text",
                        text=(
                            f"~ Found related Jira issue!\n"
                            f"{result.format_result()}\n\n"
                            f"Use pull_jira_issues to import it, or link_jira_issue to link it to a local task."
                        ),
                    )
                ]
            return [
                TextContent(
                    type="text",
                    text=(
                        f"~ Possible match found.\n"
                        f"{result.format_result()}\n\n"
                        f"This might be related to the matched task. "
                        f"Proceed, but confirm if this is the intended work."
                    ),
                )
            ]
        else:
            return [
                TextContent(
                    type="text",
                    text=(
                        f"⚠ No matching task found - possible scope drift!\n\n"
                        f"Suggested title: {result.suggested_title}\n\n"
                        f"Before proceeding, ask the user:\n"
                        f'"This looks like new work. Should I add \'{result.suggested_title}\' to the backlog first?"'
                    ),
                )
            ]

    except FileNotFoundError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error checking drift: {e}")]


async def handle_pull_jira_issues(
    store: JsonTaskStore, arguments: dict
) -> list[TextContent]:
    """Handle pull_jira_issues tool call."""
    try:
        config = store.get_config()

        if not config.jira.is_configured():
            return [
                TextContent(
                    type="text",
                    text="Jira is not configured. Run 'overseer jira setup' first.",
                )
            ]

        import_tasks = arguments.get("import_as_tasks", False)
        project_key = arguments.get("project_key") or config.jira.project_key

        async with JiraClient(
            config.jira.url, config.jira.email, config.jira.api_token
        ) as client:
            issues = await client.get_assigned_issues(project_key)

        if not issues:
            return [TextContent(type="text", text="No assigned issues found.")]

        lines = [f"## Assigned Jira Issues ({len(issues)})", ""]
        imported_count = 0

        for issue in issues:
            lines.append(f"**{issue.key}**: {issue.summary}")
            lines.append(f"  Status: {issue.status} | Type: {issue.issue_type}")

            if import_tasks:
                # Check if already linked
                existing = [t for t in store.list_tasks() if t.jira_key == issue.key]
                if not existing:
                    task = store.create_task(
                        title=f"[{issue.key}] {issue.summary}",
                        task_type=issue.to_local_task_type(),
                        status=issue.to_local_status(),
                        created_by=Origin.AGENT,
                        context=f"Imported from Jira: {issue.key}",
                        jira_key=issue.key,
                    )
                    imported_count += 1
                    lines.append(f"  -> Imported as {task.id}")
                else:
                    lines.append(f"  -> Already linked to {existing[0].id}")

            lines.append("")

        if import_tasks:
            lines.append(f"Imported {imported_count} new task(s).")

        return [TextContent(type="text", text="\n".join(lines))]

    except JiraClientError as e:
        return [TextContent(type="text", text=f"Jira error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def handle_link_jira_issue(
    store: JsonTaskStore, arguments: dict
) -> list[TextContent]:
    """Handle link_jira_issue tool call."""
    try:
        config = store.get_config()

        if not config.jira.is_configured():
            return [
                TextContent(
                    type="text",
                    text="Jira is not configured. Run 'overseer jira setup' first.",
                )
            ]

        task_id = arguments["task_id"]
        jira_key = arguments["jira_key"].upper()

        task = store.get_task(task_id)
        if not task:
            return [TextContent(type="text", text=f"Task {task_id} not found.")]

        # Verify Jira issue exists
        async with JiraClient(
            config.jira.url, config.jira.email, config.jira.api_token
        ) as client:
            try:
                issue = await client.get_issue(jira_key)
            except JiraNotFoundError:
                return [
                    TextContent(type="text", text=f"Jira issue {jira_key} not found.")
                ]

        # Update task with jira_key
        store.update_task(task_id, jira_key=jira_key)

        return [
            TextContent(
                type="text",
                text=f"Linked {task_id} to {jira_key}: {issue.summary}",
            )
        ]

    except JiraClientError as e:
        return [TextContent(type="text", text=f"Jira error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def handle_sync_jira_status(
    store: JsonTaskStore, arguments: dict
) -> list[TextContent]:
    """Handle sync_jira_status tool call."""
    try:
        config = store.get_config()

        if not config.jira.is_configured():
            return [
                TextContent(
                    type="text",
                    text="Jira is not configured. Run 'overseer jira setup' first.",
                )
            ]

        task_id = arguments["task_id"]
        task = store.get_task(task_id)

        if not task:
            return [TextContent(type="text", text=f"Task {task_id} not found.")]

        if not task.jira_key:
            return [
                TextContent(
                    type="text",
                    text=f"Task {task_id} has no linked Jira issue. Use link_jira_issue first.",
                )
            ]

        # Map Overseer status to Jira transition name
        status_mapping = {
            TaskStatus.ACTIVE: "In Progress",
            TaskStatus.DONE: "Done",
            TaskStatus.BLOCKED: "Blocked",
            TaskStatus.BACKLOG: "To Do",
        }
        target_status = status_mapping.get(task.status, "To Do")

        async with JiraClient(
            config.jira.url, config.jira.email, config.jira.api_token
        ) as client:
            await client.transition_issue(task.jira_key, target_status)

        return [
            TextContent(
                type="text",
                text=f"Synced {task_id} -> {task.jira_key}: status now '{target_status}'",
            )
        ]

    except JiraClientError as e:
        return [TextContent(type="text", text=f"Jira error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def handle_push_task_to_jira(
    store: JsonTaskStore, arguments: dict
) -> list[TextContent]:
    """Handle push_task_to_jira tool call."""
    try:
        config = store.get_config()

        if not config.jira.is_configured():
            return [
                TextContent(
                    type="text",
                    text="Jira is not configured. Run 'overseer jira setup' first.",
                )
            ]

        task_id = arguments["task_id"]
        task = store.get_task(task_id)

        if not task:
            return [TextContent(type="text", text=f"Task {task_id} not found.")]

        if task.jira_key:
            return [
                TextContent(
                    type="text",
                    text=f"Task {task_id} is already linked to {task.jira_key}.",
                )
            ]

        project_key = arguments.get("project_key") or config.jira.project_key
        if not project_key:
            return [
                TextContent(
                    type="text",
                    text="No project key specified and no default configured. "
                    "Provide project_key or run 'overseer jira setup' with a default project.",
                )
            ]

        # Map TaskType to preferred Jira issue types (in order of preference)
        type_preferences = {
            TaskType.BUG: ["Bug", "Defect", "Task"],
            TaskType.FEATURE: ["Story", "New Feature", "Feature", "Task"],
            TaskType.DEBT: ["Task", "Improvement", "Story"],
            TaskType.CHORE: ["Task", "Chore", "Story"],
        }
        preferred_types = type_preferences.get(task.type, ["Task"])

        async with JiraClient(
            config.jira.url, config.jira.email, config.jira.api_token
        ) as client:
            # Get available issue types for the project
            available_types = await client.get_project_issue_types(project_key)

            # Find the first preferred type that's available
            issue_type = None
            for pref in preferred_types:
                if pref in available_types:
                    issue_type = pref
                    break

            if not issue_type:
                # Fall back to first available non-subtask type
                if available_types:
                    issue_type = available_types[0]
                else:
                    return [
                        TextContent(
                            type="text",
                            text=f"No issue types available in project {project_key}. "
                            f"Check project permissions.",
                        )
                    ]

            issue = await client.create_issue(
                project_key=project_key,
                summary=task.title,
                issue_type=issue_type,
                description=task.context,
            )

        # Link the task to the new Jira issue
        store.update_task(task_id, jira_key=issue.key)

        return [
            TextContent(
                type="text",
                text=f"Created {issue.key}: {issue.summary}\nLinked to {task_id}",
            )
        ]

    except JiraClientError as e:
        return [TextContent(type="text", text=f"Jira error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def run_server():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    """Entry point for the MCP server."""
    import asyncio

    asyncio.run(run_server())


if __name__ == "__main__":
    main()
