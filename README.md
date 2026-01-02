

Here is a design roadmap and MVP definition for **Overseer**, tailored for a solo dev with high-velocity AI workflows.

---

### Core Philosophy: "The Invisible Project Manager"

The tool should feel less like *management* and more like *memory*. It stays out of the way until it is needed, capturing data automatically via MCP and serving it back via a lightweight dashboard.

### Phase 1: MVP (The "Memory" Engine)

**Goal:** Capture what is happening, organize it, and allow the AI to interact with the plan.

#### 1. The Data Store (Local-First)

We need a single source of truth that is portable and lives with the code.

* **Structure:** A `.overseer/` directory in your repo root.
* **Format:** JSON or SQLite files.
* **Why:** Git-trackable, zero-config, works offline.

#### 2. The MCP Server (The Bridge)

This is the most critical MVP component. It exposes tools to your AI agent (Claude/Cursor).

* **Tool: `read_active_tasks**`
* Allows the AI to see what is currently on the "To-Do" list before starting work.


* **Tool: `create_task**`
* Allows the AI to log a bug or future feature request: `create_task(title="Fix validation logic", type="debt", priority="medium")`.


* **Tool: `update_task_status**`
* Allows the AI to move a card to "Done" automatically when it finishes a prompt.


* **Tool: `log_work_session**`
* Logs a summary of the current chat/interaction for the "Daily Standup."



#### 3. The Dashboard (The "HUD")

A simple, locally hosted web UI (e.g., `localhost:3000` or a VS Code Webview).

* **The "Now" Focus:** A giant, bold text area showing the *current active objective*.
* **The "Inbox" Stream:** A list of items the AI (or you) have thrown into the backlog.
* **The Standup View:** A computed timeline of today's `log_work_session` entries.

#### 4. The "Drift Check" Workflow (Your requested feature)

This is a specific interaction pattern enforced via the System Prompt of your AI agent.

* **Trigger:** You give a prompt to the AI.
* **Action:** The AI calls `read_active_tasks`.
* **Logic:**
* *If prompt matches a task:* Proceed.
* *If prompt is new:* AI asks, "This looks like a new task. Should I add 'Refactor Login' to the Overseer backlog before we start?"



---

### Phase 2: Intelligence (The "Manager")

**Goal:** Active monitoring and automated organization.

* **Auto-Tagging:** An LLM runs in the background to tag tasks (e.g., #frontend, #database) based on content.
* **Stale Task Alerts:** "You haven't touched the 'Refactor Auth' ticket in 10 days, but you've edited `auth.ts` 5 times. Is this done?"
* **Dependencies:** Linking tasks together (Task B cannot start until Task A is done).

---

### Phase 3: Orchestration (The "Team Lead")

**Goal:** Managing parallel agents and complexity.

* **Branch Visualization:** Visualizing git branches associated with specific tasks.
* **Conflict Prediction:** Analyzing active tasks for potential file overlap.
* **QA Auto-Gen:** Spinning up a separate agent to write tests for "Done" tasks.

---

### Detailed MVP Feature Spec: "Overseer v0.1"

Here is exactly what we should build first to validate the concept.

#### A. The Context/Standup System

Instead of manual "updates," we treat the development process as a stream of events.

* **Input:** Every time you finish a major prompt or commit, the MCP tool `log_work_session` is called.
* *Payload:* `{ "summary": "Fixed the styling on the navbar", "files_touched": ["nav.tsx", "global.css"], "mood": "productive" }`


* **Output (Daily Standup):** A simple command `overseer report --today` generates a Markdown summary:
> **Today's Progress:**
> * ✅ Fixed Navbar styling.
> * ⚠️ **Blocking:** The API endpoint for search is returning 500s. (Logged as Ticket #42)
> * 📝 **Note:** Need to refactor the CSS variables later.
> 
> 



#### B. The "Smart" Todo List

A JSON file (`.overseer/tasks.json`) managed by the MCP server.

* **Schema:**
```json
{
  "id": "TASK-1",
  "status": "active", // active, backlog, done, blocked
  "type": "feature", // feature, bug, debt, chore
  "title": "Implement User Login",
  "context": "Use NextAuth.js, see auth.ts",
  "created_by": "human", // or "agent"
  "linked_files": ["src/auth/"]
}

```



#### C. The "Drift Check" Prompt Injection

We create a standard "System Prompt" snippet you paste into your AI configuration:

> "You have access to the 'Overseer' project management tools. Before generating code, ALWAYS check active tasks. If my request deviates from the current active task, ask if I want to log a new ticket. If I report a bug, use `create_task` to log it immediately."

---

### Next Step: Implementation Strategy

To get this running, we need to build the MCP Server first. Python is usually the easiest path for MCP servers (using the official SDK).

