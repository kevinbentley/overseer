# CLAUDE.md

This file provides guidance to Claude Code when working with the Overseer project.

## Project Overview

**Overseer** is "The Invisible Project Manager" - a local-first project management tool designed for AI-assisted development workflows. It stays out of the way until needed, capturing data automatically via MCP and serving it back via a lightweight dashboard.

## Repository Structure

```
/
├── pyproject.toml              # Python package configuration
├── mcp.json                    # MCP server configuration for Claude Code
├── src/overseer/
│   ├── server.py               # MCP server implementation
│   ├── cli.py                  # CLI interface
│   ├── models/                 # Data models (Task, WorkSession, Config)
│   └── store/                  # JSON store implementation
├── tests/                      # pytest test suite
└── .claude/agents/             # Specialized agent definitions
```

## Build Commands

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Initialize Overseer in a project
overseer init

# Start MCP server
overseer serve
```

## CLI Commands

```bash
overseer init                        # Initialize .overseer/ directory
overseer tasks                       # List active tasks
overseer tasks --all                 # List all tasks
overseer add "Title" --type feature  # Add a new task
overseer done TASK-1                 # Mark task as done
overseer block TASK-2 --reason "..."  # Mark task as blocked
overseer activate TASK-3             # Move to active
overseer log "Summary" --task TASK-1  # Log work session
overseer report --today              # Daily report
overseer serve                       # Start MCP server
```

## MCP Tools

When the MCP server is connected, these tools are available:

- **read_active_tasks** - Query tasks with optional status filter
- **create_task** - Create new tasks with type, context, linked files
- **update_task_status** - Change task status (done, blocked, etc.)
- **log_work_session** - Record work summaries with file tracking

## Data Store

Data is stored in `.overseer/` directory:
- `tasks.json` - Task list with status, type, context, linked files
- `config.json` - Project configuration
- `sessions/YYYY-MM-DD.json` - Daily work session logs

## Core Concepts

### Tasks
- **Status**: `active`, `backlog`, `done`, `blocked`
- **Type**: `feature`, `bug`, `debt`, `chore`
- **Origin**: `human` or `agent`

### Drift Check Workflow
1. AI calls `read_active_tasks` before generating code
2. If prompt matches active task, proceed
3. If prompt is new, ask user to create a task first

## Specialized Agents

- **mcp-server-architect** - MCP server implementation guidance
- **task-schema-designer** - Data model and schema design
- **drift-detector** - Scope drift detection logic

## Development Notes

- All data is git-trackable JSON files with sorted keys
- Atomic file writes prevent corruption
- The `.overseer/` directory should be committed to git
- Set `OVERSEER_ROOT` environment variable to specify project root
