# CLAUDE.md

This file provides guidance to Claude Code when working with the Overseer project.

## Project Overview

**Overseer** is "The Invisible Project Manager" - a local-first project management tool designed for AI-assisted development workflows. It stays out of the way until needed, capturing data automatically via MCP and serving it back via a lightweight dashboard.

**Current Status**: Design/specification phase. No implementation code exists yet.

## Repository Structure

```
/
├── README.md                    # MVP roadmap, phase definitions, feature specs
└── .claude/
    └── agents/
        ├── mcp-server-architect.md   # MCP server implementation guidance
        ├── task-schema-designer.md   # Data model and schema design
        └── drift-detector.md         # Scope drift detection logic
```

## Core Concepts

### Tasks
Work items with structured metadata:
- **Status**: `active`, `backlog`, `done`, `blocked`
- **Type**: `feature`, `bug`, `debt`, `chore`
- **Origin**: `human` or `agent`
- **Linked files**: Associated source files

### Work Sessions
Logged interactions capturing:
- Summary of completed work
- Files touched during session
- Timestamps for timeline reconstruction

### Drift Check
The signature workflow that prevents scope creep:
1. AI calls `read_active_tasks` before generating code
2. If prompt matches active task, proceed
3. If prompt is new, ask user to create a task first

### MCP Tools (Planned)
- `read_active_tasks` - Retrieve current task list
- `create_task` - Log bugs and feature requests
- `update_task_status` - Mark tasks as done
- `log_work_session` - Record work summaries

## Specialized Agents

Use these agents for domain-specific guidance:

- **mcp-server-architect** - For implementing the MCP server, defining tools, configuring Claude Code integration
- **task-schema-designer** - For designing the `.overseer/` data store schemas (JSON or SQLite)
- **drift-detector** - For implementing and tuning the drift check workflow

## Planned Technology

- **MCP Server**: Python (`mcp` SDK)
- **Data Store**: `.overseer/` directory with JSON files or SQLite database
- **Dashboard**: Localhost web UI or VS Code Webview
- **Transport**: Stdio for local, SSE for remote

## Development Notes

When implementation begins:
- Start with the MCP server - it's the most critical MVP component
- Use the agent specs in `.claude/agents/` for detailed implementation patterns
- The data store should be git-trackable and work offline
- Prioritize the "Drift Check" workflow as the key differentiating feature
