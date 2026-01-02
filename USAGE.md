# Overseer Usage Guide

A complete guide to using Overseer for AI-assisted development workflows.

---

## Quick Start

```bash
# Install Overseer
cd /path/to/overseer
pip install -e .

# Initialize in your project
cd /path/to/your-project
overseer init

# Add your first task
overseer add "Implement user authentication" --type feature --status active

# Start working with Claude Code
```

---

## Claude Code Integration

### Step 1: Add MCP Configuration

Create `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "overseer": {
      "command": "overseer",
      "args": ["serve"],
      "env": {
        "OVERSEER_ROOT": "."
      }
    }
  }
}
```

### Step 2: Add Prompt Injection to CLAUDE.md

Add this section to your project's `CLAUDE.md` file:

```markdown
## Overseer Integration

You have access to Overseer project management tools. Use them to stay focused and prevent scope drift.

### Before Starting Work

**Always call `check_drift` first** with the user's request to verify it matches an active task:

- **Strong match (>80%)**: Proceed with the work, reference the task ID
- **Weak match (40-80%)**: Proceed but confirm: "This seems related to [TASK-X]. Is that correct?"
- **No match (<40%)**: Ask the user: "This looks like new work. Should I add '[suggested title]' to the backlog first?"

### During Work

- When you discover a bug: `create_task` with type="bug"
- When you identify technical debt: `create_task` with type="debt"
- When you think of a future enhancement: `create_task` with type="feature" status="backlog"

### After Completing Work

- Mark tasks done: `update_task_status` with status="done"
- Log significant progress: `log_work_session` with summary and files touched

### Available Tools

- `check_drift` - Check if request matches active tasks
- `read_active_tasks` - View current task list
- `create_task` - Log new tasks
- `update_task_status` - Update task status
- `log_work_session` - Record work summaries
```

---

## Developer Workflow Examples

### Example 1: Starting a New Feature

```bash
# Create the task
$ overseer add "Add dark mode toggle" --type feature --status active \
    --context "Add toggle in settings, persist preference to localStorage" \
    --files src/components/Settings.tsx src/hooks/useTheme.ts

Created TASK-1: Add dark mode toggle

# Check current tasks
$ overseer tasks
[>] TASK-1: Add dark mode toggle (feature)
    Context: Add toggle in settings, persist preference to localStorage
    Files: src/components/Settings.tsx, src/hooks/useTheme.ts
```

Now when you ask Claude: *"Add the dark mode toggle to the settings page"*

Claude calls `check_drift` → Strong match on TASK-1 → Proceeds with the work.

---

### Example 2: Discovering a Bug While Working

You're working on TASK-1 (dark mode) and notice a bug:

**You:** "The settings page crashes when localStorage is disabled"

**Claude:**
1. Calls `check_drift` → No match (this is a bug, not dark mode feature)
2. Calls `create_task` with type="bug"
3. Asks: "I've logged this as TASK-2. Should I fix it now or continue with dark mode?"

```bash
$ overseer tasks --all
[>] TASK-1: Add dark mode toggle (feature)
[ ] TASK-2: Fix: Settings page crashes when localStorage is disabled (bug)
```

---

### Example 3: Completing Work

**You:** "The dark mode toggle is done, let's move on"

**Claude:**
1. Calls `update_task_status` for TASK-1 → done
2. Calls `log_work_session` with summary

```bash
$ overseer tasks
No active tasks found.

$ overseer tasks --status done
[x] TASK-1: Add dark mode toggle (feature)
```

---

### Example 4: Scope Drift Prevention

Active task: *"Refactor the API client"*

**You:** "Actually, can you add pagination to the user list?"

**Claude:**
1. Calls `check_drift` → No match (pagination ≠ refactoring)
2. Responds: "This looks like new work. Should I add 'Add pagination to the user list' to the backlog first, or would you like to switch focus?"

**You:** "Add it to backlog, let's finish the refactor first"

**Claude:** Creates TASK-3 in backlog, continues with refactor.

---

### Example 5: Daily Standup

```bash
$ overseer standup

## Daily Standup - 2026-01-02

### Completed Yesterday
- [x] TASK-1: Add dark mode toggle

### In Progress
- [>] TASK-3: Refactor API client (debt)
    Extract common request logic into base class

### Blocked
- [!] TASK-4: Integrate payment provider
    Blocked: Waiting on API credentials from finance team

### Today's Progress
- Extracted base HTTP client class (TASK-3)
- Fixed retry logic in API client (TASK-3)
```

---

### Example 6: Working with Linked Files

```bash
# Create task with file context
$ overseer add "Fix navbar responsive layout" --type bug \
    --files src/components/Navbar.tsx src/styles/navbar.css

Created TASK-5: Fix navbar responsive layout
```

Now when you ask: *"The nav component is broken on mobile"*

Claude calls `check_drift` → Matches TASK-5 via file context (`nav` → `Navbar.tsx`)

---

## CLI Reference

### Task Management

```bash
# List tasks
overseer tasks                       # Active tasks only
overseer tasks --all                 # All tasks
overseer tasks --status backlog      # Filter by status
overseer tasks -v                    # Include full context

# Create tasks
overseer add "Title" --type feature  # Types: feature, bug, debt, chore
overseer add "Title" --status active # Status: active, backlog (default)
overseer add "Title" --context "Details here"
overseer add "Title" --files file1.ts file2.ts

# Update tasks
overseer done TASK-1                 # Mark as done
overseer block TASK-1 --reason "Waiting on X"
overseer activate TASK-1             # Move to active
```

### Work Sessions

```bash
# Log a session
overseer log "Implemented feature X"
overseer log "Fixed bug" --task TASK-1
overseer log "Refactored code" --files src/api.ts src/utils.ts

# View reports
overseer report --today
overseer report --yesterday
overseer report --week
```

### Daily Standup

```bash
overseer standup                     # Basic standup
overseer standup --include-backlog   # Include backlog preview
```

---

## Task States

```
┌─────────┐     activate      ┌────────┐
│ BACKLOG │ ───────────────▶  │ ACTIVE │
└─────────┘                   └────────┘
     ▲                            │
     │                            │ done
     │         ┌───────┐          ▼
     └──────── │ BLOCKED│ ◀── ┌──────┐
      unblock  └───────┘      │ DONE │
                              └──────┘
```

---

## Best Practices

### 1. Start Each Session with Context

```bash
$ overseer standup
```

This shows what you accomplished yesterday and what's in progress.

### 2. Keep Tasks Granular

Instead of:
> "Build the entire authentication system"

Break it down:
> - "Add login form UI"
> - "Implement JWT token handling"
> - "Add password reset flow"

### 3. Link Files to Tasks

```bash
overseer add "Fix navbar" --files src/Navbar.tsx styles/nav.css
```

This improves drift detection accuracy.

### 4. Log Sessions Regularly

After completing significant work:
```bash
overseer log "Completed login form with validation" --task TASK-1 --files src/Login.tsx
```

### 5. Use the Backlog

Don't let ideas disappear:
```bash
overseer add "Add dark mode" --type feature  # Goes to backlog by default
```

Review the backlog during planning:
```bash
overseer tasks --status backlog
```

---

## Troubleshooting

### "Overseer not initialized"

Run `overseer init` in your project root.

### MCP Server Not Connecting

1. Verify `.mcp.json` exists in project root
2. Check that `overseer` is in your PATH
3. Restart Claude Code

### Drift Detection Too Sensitive

Add more context to your tasks:
```bash
overseer add "Refactor auth" --context "Focus on JWT handling in src/auth/*"
```

### Drift Detection Missing Matches

Link relevant files:
```bash
overseer add "Fix login" --files src/auth/login.ts src/components/LoginForm.tsx
```
