"""Overseer MCP Server."""

import os
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .store import JsonTaskStore, SessionStore
from .models import TaskStatus, TaskType, Origin
from .drift import DriftDetector


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
            return [
                TextContent(
                    type="text",
                    text=(
                        "No active tasks found.\n"
                        "This appears to be new work. Consider creating a task first with create_task."
                    ),
                )
            ]

        # Run drift detection
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
