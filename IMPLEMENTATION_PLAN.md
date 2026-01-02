# Overseer Implementation Plan

A detailed, step-by-step implementation guide for building Overseer MVP.

---

## Phase 1: Project Setup

### 1.1 Initialize Python Project

```bash
mkdir -p src/overseer
cd src/overseer
```

**Files to create:**
- `pyproject.toml` - Project metadata and dependencies
- `src/overseer/__init__.py` - Package init
- `src/overseer/server.py` - MCP server entry point

**Dependencies:**
```toml
[project]
name = "overseer"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.0.0",
]

[project.scripts]
overseer = "overseer.server:main"
```

### 1.2 Create Data Store Directory Structure

```
.overseer/
├── config.json          # Project settings
├── tasks.json           # Task list
└── sessions/            # Work session logs (one file per day)
    └── 2024-01-15.json
```

---

## Phase 2: Data Models

### 2.1 Task Schema

**File:** `src/overseer/models/task.py`

```python
@dataclass
class Task:
    id: str                    # "TASK-1", "TASK-2", etc.
    title: str                 # Brief description
    status: TaskStatus         # active, backlog, done, blocked
    type: TaskType             # feature, bug, debt, chore
    created_by: Origin         # human, agent
    context: str | None        # Additional notes
    linked_files: list[str]    # Associated file paths
    created_at: datetime
    updated_at: datetime
```

**Enums:**
```python
class TaskStatus(Enum):
    ACTIVE = "active"
    BACKLOG = "backlog"
    DONE = "done"
    BLOCKED = "blocked"

class TaskType(Enum):
    FEATURE = "feature"
    BUG = "bug"
    DEBT = "debt"
    CHORE = "chore"

class Origin(Enum):
    HUMAN = "human"
    AGENT = "agent"
```

### 2.2 Work Session Schema

**File:** `src/overseer/models/session.py`

```python
@dataclass
class WorkSession:
    id: str                    # UUID
    summary: str               # What was done
    files_touched: list[str]   # Files modified
    task_id: str | None        # Associated task
    logged_at: datetime
```

### 2.3 Config Schema

**File:** `src/overseer/models/config.py`

```python
@dataclass
class OverseerConfig:
    version: str = "0.1"
    active_task_id: str | None = None  # Current focus
    auto_log_sessions: bool = True
```

---

## Phase 3: Data Store Layer

### 3.1 Store Interface

**File:** `src/overseer/store/base.py`

```python
class TaskStore(Protocol):
    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]: ...
    def get_task(self, task_id: str) -> Task | None: ...
    def create_task(self, task: Task) -> Task: ...
    def update_task(self, task_id: str, updates: dict) -> Task: ...
    def delete_task(self, task_id: str) -> bool: ...
    def next_task_id(self) -> str: ...
```

### 3.2 JSON Store Implementation

**File:** `src/overseer/store/json_store.py`

Implements `TaskStore` using `.overseer/tasks.json`:
- Atomic writes (write to temp, then rename)
- Auto-create `.overseer/` if missing
- Pretty-print JSON for git diffs
- Sort keys for consistent ordering

### 3.3 Session Store

**File:** `src/overseer/store/session_store.py`

- One file per day: `.overseer/sessions/YYYY-MM-DD.json`
- Append-only within the day
- `get_today()` and `get_range(start, end)` methods

---

## Phase 4: MCP Server

### 4.1 Server Setup

**File:** `src/overseer/server.py`

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server

server = Server("overseer")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        read_active_tasks_tool,
        create_task_tool,
        update_task_status_tool,
        log_work_session_tool,
    ]
```

### 4.2 Tool: read_active_tasks

**Purpose:** Retrieve current task list for drift checking.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string",
      "enum": ["active", "backlog", "done", "blocked"],
      "description": "Filter by status (optional, defaults to 'active')"
    },
    "include_context": {
      "type": "boolean",
      "description": "Include full task context (default: true)"
    }
  }
}
```

**Output:** List of tasks as formatted text.

### 4.3 Tool: create_task

**Purpose:** Log a new task (bug, feature, etc.).

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "title": { "type": "string", "description": "Task title" },
    "type": { "type": "string", "enum": ["feature", "bug", "debt", "chore"] },
    "status": { "type": "string", "enum": ["active", "backlog"], "default": "backlog" },
    "context": { "type": "string", "description": "Additional notes" },
    "linked_files": { "type": "array", "items": { "type": "string" } }
  },
  "required": ["title", "type"]
}
```

**Output:** Created task with assigned ID.

### 4.4 Tool: update_task_status

**Purpose:** Change task status (e.g., mark as done).

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "task_id": { "type": "string", "description": "Task ID (e.g., TASK-1)" },
    "status": { "type": "string", "enum": ["active", "backlog", "done", "blocked"] }
  },
  "required": ["task_id", "status"]
}
```

### 4.5 Tool: log_work_session

**Purpose:** Record a work session for standup reports.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "summary": { "type": "string", "description": "What was accomplished" },
    "files_touched": { "type": "array", "items": { "type": "string" } },
    "task_id": { "type": "string", "description": "Associated task ID (optional)" }
  },
  "required": ["summary"]
}
```

---

## Phase 5: CLI Interface

### 5.1 CLI Commands

**File:** `src/overseer/cli.py`

```bash
# Initialize .overseer/ in current directory
overseer init

# List tasks
overseer tasks                    # List active tasks
overseer tasks --all              # List all tasks
overseer tasks --status backlog   # Filter by status

# Manage tasks
overseer add "Fix login bug" --type bug
overseer done TASK-1
overseer block TASK-2 --reason "Waiting on API"

# Reports
overseer report --today           # Today's work sessions
overseer report --week            # This week's summary

# Start MCP server (for Claude Code integration)
overseer serve
```

### 5.2 CLI Implementation

Use `argparse` or `click` for argument parsing:
- `init` - Create `.overseer/` directory with default config
- `tasks` - Query and display tasks
- `add` - Create task interactively
- `done`/`block` - Quick status updates
- `report` - Generate markdown reports
- `serve` - Start MCP server (stdio transport)

---

## Phase 6: Claude Code Integration

### 6.1 MCP Configuration

**File:** `~/.claude/claude_desktop_config.json` or project `.mcp.json`

```json
{
  "mcpServers": {
    "overseer": {
      "command": "overseer",
      "args": ["serve"],
      "env": {
        "OVERSEER_ROOT": "/path/to/project"
      }
    }
  }
}
```

### 6.2 System Prompt Snippet

Add to Claude Code's custom instructions:

```
You have access to Overseer project management tools.

**Before generating code:**
1. Call `read_active_tasks` to see current work items
2. If your task matches an active task, proceed and reference it
3. If it's new work, ask: "Should I add '[title]' to the backlog first?"

**When you encounter a bug:** Use `create_task` with type="bug"
**When you complete work:** Use `update_task_status` to mark done
**After significant work:** Use `log_work_session` to record progress
```

---

## Phase 7: Testing

### 7.1 Unit Tests

**Directory:** `tests/`

- `test_models.py` - Task/Session serialization
- `test_json_store.py` - CRUD operations, file handling
- `test_tools.py` - MCP tool input validation

### 7.2 Integration Tests

- `test_server.py` - Full MCP request/response cycle
- `test_cli.py` - CLI command execution

### 7.3 Manual Testing

1. Initialize overseer in a test project
2. Create tasks via CLI
3. Connect Claude Code via MCP
4. Verify `read_active_tasks` returns correct data
5. Test drift check workflow with various prompts

---

## Implementation Order

### Milestone 1: Core Data Layer ✅
1. [x] Project setup (`pyproject.toml`, package structure)
2. [x] Data models (Task, WorkSession, Config)
3. [x] JSON store implementation
4. [x] Unit tests for store

### Milestone 2: MCP Server ✅
5. [x] Basic MCP server setup
6. [x] `read_active_tasks` tool
7. [x] `create_task` tool
8. [x] `update_task_status` tool
9. [x] `log_work_session` tool
10. [x] Unit tests (15 passing)

### Milestone 3: CLI ✅
11. [x] `overseer init` command
12. [x] `overseer tasks` command
13. [x] `overseer add`/`done`/`block`/`activate` commands
14. [x] `overseer report` command
15. [x] `overseer serve` command

### Milestone 4: Integration ✅
16. [x] Claude Code MCP configuration (`mcp.json`)
17. [x] System prompt snippet (in CLAUDE.md)
18. [x] End-to-end CLI testing
19. [x] Documentation updated

### Future Work
- [ ] Web dashboard
- [ ] Semantic drift detection
- [ ] Git branch integration
- [ ] VS Code extension

---

## File Structure (Final)

```
overseer/
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── IMPLEMENTATION_PLAN.md
├── src/
│   └── overseer/
│       ├── __init__.py
│       ├── server.py           # MCP server entry point
│       ├── cli.py              # CLI commands
│       ├── models/
│       │   ├── __init__.py
│       │   ├── task.py
│       │   ├── session.py
│       │   └── config.py
│       ├── store/
│       │   ├── __init__.py
│       │   ├── base.py         # Protocol definitions
│       │   ├── json_store.py   # JSON file implementation
│       │   └── session_store.py
│       └── tools/
│           ├── __init__.py
│           ├── read_tasks.py
│           ├── create_task.py
│           ├── update_status.py
│           └── log_session.py
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_json_store.py
│   ├── test_tools.py
│   └── test_cli.py
└── .claude/
    └── agents/
        ├── mcp-server-architect.md
        ├── task-schema-designer.md
        └── drift-detector.md
```

---

## Success Criteria

The MVP is complete when:

1. **MCP Server works** - Claude Code can connect and call all 4 tools
2. **Tasks persist** - Created tasks survive server restarts
3. **Drift check functions** - `read_active_tasks` returns useful context
4. **CLI is usable** - Can manage tasks without MCP
5. **Git-friendly** - `.overseer/` files diff cleanly

---

## Future Enhancements (Post-MVP)

- SQLite backend for larger projects
- Web dashboard (FastAPI + HTMX or similar)
- Semantic drift detection with embeddings
- Git branch integration
- VS Code extension
