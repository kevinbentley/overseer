# CLAUDE.md

This file provides guidance to Claude Code when working with the Overseer project.

## Required: Use Overseer MCP for Task Management

**You MUST use the Overseer MCP tools instead of the built-in TodoWrite tool for all task tracking in this project.**

### Before Starting Any Work

1. **Check active tasks first**: Call `mcp__overseer__read_active_tasks` to see what's currently being worked on
2. **Check for scope drift**: Call `mcp__overseer__check_drift` with the user's request to verify the work aligns with tracked tasks
   - If no match is found, ask the user if they want to create a new task before proceeding
   - If a weak match (40-80%), confirm which task this relates to

### During Work

3. **Create tasks for new work**: Use `mcp__overseer__create_task` to track new features, bugs, or chores
   - Always specify `type`: `feature`, `bug`, `debt`, or `chore`
   - Include `context` with implementation notes
   - Add `linked_files` for relevant source files

4. **Update task status**: Use `mcp__overseer__update_task_status` to mark tasks as:
   - `active` - currently being worked on
   - `blocked` - waiting on something
   - `done` - completed

### After Completing Work

5. **Log work sessions**: Call `mcp__overseer__log_work_session` with:
   - A brief `summary` of what was accomplished
   - The `task_id` if work was for a specific task
   - List of `files_touched` that were modified

### Jira Integration (if configured)

- Use `mcp__overseer__pull_jira_issues` to see assigned Jira issues
- Use `mcp__overseer__link_jira_issue` to connect local tasks to Jira
- Use `mcp__overseer__sync_jira_status` to push status updates to Jira

---

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
│   ├── models/                 # Data models (Task, WorkSession, Config, JiraConfig)
│   ├── store/                  # JSON store implementation
│   ├── drift/                  # Drift detection logic
│   └── jira/                   # Jira API client
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
overseer standup                     # Daily standup report
overseer serve                       # Start MCP server

# Jira integration
overseer jira setup                  # Configure Jira credentials
overseer jira pull                   # List assigned Jira issues
overseer jira pull --import          # Import issues as local tasks
overseer jira sync TASK-1            # Push task status to Jira
```

## MCP Tools

When the MCP server is connected, these tools are available:

- **read_active_tasks** - Query tasks with optional status filter
- **create_task** - Create new tasks with type, context, linked files
- **update_task_status** - Change task status (done, blocked, etc.)
- **log_work_session** - Record work summaries with file tracking
- **check_drift** - Check if a prompt matches active tasks (drift detection)
- **pull_jira_issues** - Fetch assigned Jira issues, optionally import as tasks
- **link_jira_issue** - Link a local task to a Jira issue
- **sync_jira_status** - Push local task status to linked Jira issue

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
1. AI calls `check_drift` with the user's prompt
2. If strong match (>80%): proceed with the work
3. If weak match (40-80%): proceed but confirm the task
4. If no match (<40%): ask user to create a task first

**Matching strategies:**
- Explicit task references (TASK-1)
- Keyword overlap with title/context
- File context matching (linked_files)
- Task type inference (bug, feature, etc.)
- Jira fallback search (when no local match and Jira is configured)

### Jira Integration

When Jira is configured (`overseer jira setup`), drift detection automatically searches Jira when no local task matches. This helps catch work that exists in Jira but hasn't been imported locally.

**Workflow:**
1. User asks to work on something
2. `check_drift` finds no local match
3. Jira is searched for related issues
4. If found, suggest importing or linking the Jira issue
5. User can then proceed with the tracked work

**Status sync:** When marking tasks done, use `sync_jira_status` to push the status to Jira.

## Specialized Agents

- **mcp-server-architect** - MCP server implementation guidance
- **task-schema-designer** - Data model and schema design
- **drift-detector** - Scope drift detection logic

## Development Notes

- All data is git-trackable JSON files with sorted keys
- Atomic file writes prevent corruption
- The `.overseer/` directory should be committed to git
- Set `OVERSEER_ROOT` environment variable to specify project root
- Jira credentials are stored in `.overseer/config.json` - consider adding to `.gitignore` if sensitive
