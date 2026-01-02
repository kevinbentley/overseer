"""Overseer CLI interface."""

import argparse
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

from .store import JsonTaskStore, SessionStore
from .models import TaskStatus, TaskType, Origin, JiraConfig


def get_stores(root: Path | None = None) -> tuple[JsonTaskStore, SessionStore]:
    """Get initialized stores."""
    if root is None:
        root = Path.cwd()
    return JsonTaskStore(root), SessionStore(root)


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize .overseer/ in current directory."""
    root = Path.cwd()
    task_store = JsonTaskStore(root)

    if (root / ".overseer").exists():
        print("Overseer already initialized in this directory.")
        return 0

    task_store.initialize()
    print(f"Initialized Overseer in {root / '.overseer'}")
    return 0


def cmd_tasks(args: argparse.Namespace) -> int:
    """List tasks."""
    task_store, _ = get_stores()

    try:
        if args.all:
            tasks = task_store.list_tasks()
        else:
            status = TaskStatus(args.status) if args.status else TaskStatus.ACTIVE
            tasks = task_store.list_tasks(status=status)

        if not tasks:
            status_msg = "any" if args.all else args.status or "active"
            print(f"No {status_msg} tasks found.")
            return 0

        for task in tasks:
            print(task.format_display(include_context=args.verbose))
            print()

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_add(args: argparse.Namespace) -> int:
    """Add a new task."""
    task_store, _ = get_stores()

    try:
        task_type = TaskType(args.type)
        status = TaskStatus(args.status) if args.status else TaskStatus.BACKLOG
        created_by = Origin.HUMAN

        task = task_store.create_task(
            title=args.title,
            task_type=task_type,
            status=status,
            created_by=created_by,
            context=args.context,
            linked_files=args.files or [],
        )

        print(f"Created {task.id}: {task.title}")
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_done(args: argparse.Namespace) -> int:
    """Mark a task as done."""
    task_store, _ = get_stores()

    try:
        task = task_store.update_task(args.task_id, status=TaskStatus.DONE)
        if task is None:
            print(f"Task {args.task_id} not found.", file=sys.stderr)
            return 1

        print(f"Marked {task.id} as done: {task.title}")
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_block(args: argparse.Namespace) -> int:
    """Mark a task as blocked."""
    task_store, _ = get_stores()

    try:
        updates = {"status": TaskStatus.BLOCKED}
        if args.reason:
            # Append blocking reason to context
            task = task_store.get_task(args.task_id)
            if task:
                existing_context = task.context or ""
                new_context = (
                    f"{existing_context}\n\nBlocked: {args.reason}"
                    if existing_context
                    else f"Blocked: {args.reason}"
                )
                updates["context"] = new_context

        task = task_store.update_task(args.task_id, **updates)
        if task is None:
            print(f"Task {args.task_id} not found.", file=sys.stderr)
            return 1

        print(f"Marked {task.id} as blocked: {task.title}")
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_activate(args: argparse.Namespace) -> int:
    """Move a task to active status."""
    task_store, _ = get_stores()

    try:
        task = task_store.update_task(args.task_id, status=TaskStatus.ACTIVE)
        if task is None:
            print(f"Task {args.task_id} not found.", file=sys.stderr)
            return 1

        print(f"Activated {task.id}: {task.title}")
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_report(args: argparse.Namespace) -> int:
    """Generate a work session report."""
    _, session_store = get_stores()

    try:
        if args.today:
            report = session_store.format_daily_report(date.today())
        elif args.yesterday:
            report = session_store.format_daily_report(date.today() - timedelta(days=1))
        elif args.week:
            # Last 7 days
            sessions = []
            for i in range(7):
                day = date.today() - timedelta(days=i)
                day_sessions = session_store.get_sessions_for_day(day)
                if day_sessions:
                    sessions.append((day, day_sessions))

            if not sessions:
                print("No sessions logged this week.")
                return 0

            lines = ["## Week Summary", ""]
            for day, day_sessions in reversed(sessions):
                lines.append(f"### {day.isoformat()}")
                for session in day_sessions:
                    lines.append(f"- {session.format_display()}")
                lines.append("")

            report = "\n".join(lines)
        else:
            report = session_store.format_daily_report(date.today())

        print(report)
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_serve(args: argparse.Namespace) -> int:
    """Start the MCP server."""
    from .server import main as server_main

    server_main()
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    """Log a work session."""
    _, session_store = get_stores()

    try:
        session = session_store.log_session(
            summary=args.summary,
            files_touched=args.files or [],
            task_id=args.task,
        )

        print(f"Logged session {session.id}: {session.summary}")
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_standup(args: argparse.Namespace) -> int:
    """Generate a daily standup report."""
    task_store, session_store = get_stores()

    try:
        today = date.today()
        yesterday = today - timedelta(days=1)

        lines = [f"## Daily Standup - {today.isoformat()}", ""]

        # Completed yesterday (tasks marked done yesterday or sessions from yesterday)
        yesterday_sessions = session_store.get_sessions_for_day(yesterday)
        done_tasks = task_store.list_tasks(status=TaskStatus.DONE)

        # Filter done tasks that were updated yesterday
        recently_done = [
            t for t in done_tasks
            if t.updated_at.date() == yesterday
        ]

        if recently_done or yesterday_sessions:
            lines.append("### Completed Yesterday")
            for task in recently_done:
                lines.append(f"- [x] {task.id}: {task.title}")
            for session in yesterday_sessions:
                if not any(session.task_id == t.id for t in recently_done):
                    lines.append(f"- {session.summary}")
            lines.append("")

        # In Progress (active tasks)
        active_tasks = task_store.list_tasks(status=TaskStatus.ACTIVE)
        if active_tasks:
            lines.append("### In Progress")
            for task in active_tasks:
                lines.append(f"- [>] {task.id}: {task.title} ({task.type.value})")
                if task.context:
                    # Show first line of context
                    first_line = task.context.split("\n")[0]
                    if len(first_line) > 60:
                        first_line = first_line[:57] + "..."
                    lines.append(f"    {first_line}")
            lines.append("")

        # Blocked
        blocked_tasks = task_store.list_tasks(status=TaskStatus.BLOCKED)
        if blocked_tasks:
            lines.append("### Blocked")
            for task in blocked_tasks:
                lines.append(f"- [!] {task.id}: {task.title}")
                if task.context and "Blocked:" in task.context:
                    # Extract blocking reason
                    for line in task.context.split("\n"):
                        if line.startswith("Blocked:"):
                            lines.append(f"    {line}")
                            break
            lines.append("")

        # Today's sessions so far
        today_sessions = session_store.get_sessions_for_day(today)
        if today_sessions:
            lines.append("### Today's Progress")
            for session in today_sessions:
                task_ref = f" ({session.task_id})" if session.task_id else ""
                lines.append(f"- {session.summary}{task_ref}")
            lines.append("")

        # Backlog preview
        backlog_tasks = task_store.list_tasks(status=TaskStatus.BACKLOG)
        if backlog_tasks and args.include_backlog:
            lines.append("### Backlog")
            for task in backlog_tasks[:5]:  # Show top 5
                lines.append(f"- [ ] {task.id}: {task.title} ({task.type.value})")
            if len(backlog_tasks) > 5:
                lines.append(f"    ... and {len(backlog_tasks) - 5} more")
            lines.append("")

        # Summary
        if not any([recently_done, yesterday_sessions, active_tasks, blocked_tasks, today_sessions]):
            lines.append("No activity to report. Use `overseer add` to create tasks.")

        print("\n".join(lines))
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_jira_setup(args: argparse.Namespace) -> int:
    """Configure Jira integration."""
    task_store, _ = get_stores()

    try:
        task_store.ensure_initialized()
        config = task_store.get_config()

        # Get credentials from args or prompt
        url = args.url
        email = args.email
        token = args.token
        project = args.project

        if not url:
            url = input("Jira URL (e.g., https://company.atlassian.net): ").strip()
        if not email:
            email = input("Your Jira email: ").strip()
        if not token:
            token = input("API token: ").strip()
        if not project:
            project = input("Default project key (optional, press Enter to skip): ").strip() or None

        if not all([url, email, token]):
            print("Error: URL, email, and token are required.", file=sys.stderr)
            return 1

        # Test connection
        print("Testing connection...")
        debug = getattr(args, 'debug', False)
        if debug:
            print(f"  URL: {url}")
            print(f"  Email: {email}")
            print(f"  Token: {'*' * 8}...{token[-4:] if len(token) > 4 else '****'}")

        from .jira import JiraClient

        async def test_connection():
            async with JiraClient(url, email, token) as client:
                return await client.test_connection(debug=debug)

        try:
            success, message = asyncio.run(test_connection())
            if success:
                print(f"Connection successful! {message}")
            else:
                print(f"Connection failed: {message}", file=sys.stderr)
                return 1
        except Exception as e:
            print(f"Connection error: {type(e).__name__}: {e}", file=sys.stderr)
            if debug:
                import traceback
                traceback.print_exc()
            return 1

        # Save configuration
        config.jira = JiraConfig(
            url=url,
            email=email,
            api_token=token,
            project_key=project,
        )
        task_store.save_config(config)
        print("Jira configuration saved.")
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_jira_pull(args: argparse.Namespace) -> int:
    """Fetch assigned Jira issues."""
    task_store, _ = get_stores()

    try:
        config = task_store.get_config()
        if not config.jira.is_configured():
            print("Jira not configured. Run 'overseer jira setup' first.", file=sys.stderr)
            return 1

        from .jira import JiraClient

        project_key = args.project or config.jira.project_key

        async def fetch_issues():
            async with JiraClient(
                config.jira.url, config.jira.email, config.jira.api_token
            ) as client:
                return await client.get_assigned_issues(project_key)

        issues = asyncio.run(fetch_issues())

        if not issues:
            print("No assigned issues found.")
            return 0

        print(f"## Assigned Issues ({len(issues)})\n")
        for issue in issues:
            status_display = f"[{issue.status:12}]"
            print(f"{status_display} {issue.key}: {issue.summary}")

            if args.import_tasks:
                existing = [t for t in task_store.list_tasks() if t.jira_key == issue.key]
                if not existing:
                    task = task_store.create_task(
                        title=f"[{issue.key}] {issue.summary}",
                        task_type=issue.to_local_task_type(),
                        status=issue.to_local_status(),
                        created_by=Origin.AGENT,
                        context=f"Imported from Jira",
                        jira_key=issue.key,
                    )
                    print(f"             -> Imported as {task.id}")
                else:
                    print(f"             -> Already linked to {existing[0].id}")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_jira_sync(args: argparse.Namespace) -> int:
    """Sync task status to Jira."""
    task_store, _ = get_stores()

    try:
        config = task_store.get_config()
        if not config.jira.is_configured():
            print("Jira not configured. Run 'overseer jira setup' first.", file=sys.stderr)
            return 1

        task = task_store.get_task(args.task_id)
        if not task:
            print(f"Task {args.task_id} not found.", file=sys.stderr)
            return 1

        if not task.jira_key:
            print(f"Task {args.task_id} has no linked Jira issue.", file=sys.stderr)
            return 1

        from .jira import JiraClient, JiraClientError

        # Map Overseer status to Jira transition
        status_mapping = {
            TaskStatus.ACTIVE: "In Progress",
            TaskStatus.DONE: "Done",
            TaskStatus.BLOCKED: "Blocked",
            TaskStatus.BACKLOG: "To Do",
        }
        target_status = status_mapping.get(task.status, "To Do")

        async def sync_status():
            async with JiraClient(
                config.jira.url, config.jira.email, config.jira.api_token
            ) as client:
                await client.transition_issue(task.jira_key, target_status)

        try:
            asyncio.run(sync_status())
            print(f"Synced {args.task_id} -> {task.jira_key}: status now '{target_status}'")
            return 0
        except JiraClientError as e:
            print(f"Sync failed: {e}", file=sys.stderr)
            return 1

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_jira(args: argparse.Namespace) -> int:
    """Handle jira subcommand dispatch."""
    if args.jira_command == "setup":
        return cmd_jira_setup(args)
    elif args.jira_command == "pull":
        return cmd_jira_pull(args)
    elif args.jira_command == "sync":
        return cmd_jira_sync(args)
    else:
        print("Usage: overseer jira {setup|pull|sync}", file=sys.stderr)
        return 1


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="overseer",
        description="The Invisible Project Manager - local-first task management for AI-assisted development",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init
    subparsers.add_parser("init", help="Initialize .overseer/ in current directory")

    # tasks
    tasks_parser = subparsers.add_parser("tasks", help="List tasks")
    tasks_parser.add_argument(
        "--status",
        "-s",
        choices=["active", "backlog", "done", "blocked"],
        help="Filter by status (default: active)",
    )
    tasks_parser.add_argument(
        "--all", "-a", action="store_true", help="Show all tasks"
    )
    tasks_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show full context"
    )

    # add
    add_parser = subparsers.add_parser("add", help="Add a new task")
    add_parser.add_argument("title", help="Task title")
    add_parser.add_argument(
        "--type",
        "-t",
        choices=["feature", "bug", "debt", "chore"],
        default="feature",
        help="Task type (default: feature)",
    )
    add_parser.add_argument(
        "--status",
        "-s",
        choices=["active", "backlog"],
        help="Initial status (default: backlog)",
    )
    add_parser.add_argument("--context", "-c", help="Additional context or notes")
    add_parser.add_argument(
        "--files", "-f", nargs="+", help="Linked file paths"
    )

    # done
    done_parser = subparsers.add_parser("done", help="Mark a task as done")
    done_parser.add_argument("task_id", help="Task ID (e.g., TASK-1)")

    # block
    block_parser = subparsers.add_parser("block", help="Mark a task as blocked")
    block_parser.add_argument("task_id", help="Task ID (e.g., TASK-1)")
    block_parser.add_argument("--reason", "-r", help="Reason for blocking")

    # activate
    activate_parser = subparsers.add_parser("activate", help="Move a task to active")
    activate_parser.add_argument("task_id", help="Task ID (e.g., TASK-1)")

    # log
    log_parser = subparsers.add_parser("log", help="Log a work session")
    log_parser.add_argument("summary", help="Session summary")
    log_parser.add_argument("--files", "-f", nargs="+", help="Files touched")
    log_parser.add_argument("--task", "-t", help="Associated task ID")

    # report
    report_parser = subparsers.add_parser("report", help="Generate work session report")
    report_group = report_parser.add_mutually_exclusive_group()
    report_group.add_argument(
        "--today", action="store_true", help="Today's sessions (default)"
    )
    report_group.add_argument(
        "--yesterday", action="store_true", help="Yesterday's sessions"
    )
    report_group.add_argument(
        "--week", action="store_true", help="This week's sessions"
    )

    # serve
    subparsers.add_parser("serve", help="Start the MCP server")

    # standup
    standup_parser = subparsers.add_parser("standup", help="Generate daily standup report")
    standup_parser.add_argument(
        "--include-backlog", "-b", action="store_true", help="Include backlog preview"
    )

    # jira
    jira_parser = subparsers.add_parser("jira", help="Jira integration commands")
    jira_subparsers = jira_parser.add_subparsers(dest="jira_command")

    # jira setup
    jira_setup_parser = jira_subparsers.add_parser("setup", help="Configure Jira integration")
    jira_setup_parser.add_argument("--url", help="Jira instance URL")
    jira_setup_parser.add_argument("--email", help="Your Jira email")
    jira_setup_parser.add_argument("--token", help="API token")
    jira_setup_parser.add_argument("--project", help="Default project key")
    jira_setup_parser.add_argument(
        "--debug", "-d", action="store_true",
        help="Show detailed connection debug info"
    )

    # jira pull
    jira_pull_parser = jira_subparsers.add_parser("pull", help="Fetch assigned Jira issues")
    jira_pull_parser.add_argument("--project", "-p", help="Project key filter")
    jira_pull_parser.add_argument(
        "--import", "-i", dest="import_tasks", action="store_true",
        help="Import as local tasks"
    )

    # jira sync
    jira_sync_parser = jira_subparsers.add_parser("sync", help="Sync task status to Jira")
    jira_sync_parser.add_argument("task_id", help="Task ID to sync")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    # Dispatch to command handlers
    handlers = {
        "init": cmd_init,
        "tasks": cmd_tasks,
        "add": cmd_add,
        "done": cmd_done,
        "block": cmd_block,
        "activate": cmd_activate,
        "log": cmd_log,
        "report": cmd_report,
        "serve": cmd_serve,
        "standup": cmd_standup,
        "jira": cmd_jira,
    }

    handler = handlers.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
