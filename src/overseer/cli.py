"""Overseer CLI interface."""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

from .store import JsonTaskStore, SessionStore
from .models import TaskStatus, TaskType, Origin


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
    }

    handler = handlers.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
