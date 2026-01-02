"""FastAPI application for Overseer web frontend."""

import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..models import TaskStatus, TaskType, Origin
from ..store import JsonTaskStore

# Path setup
WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

# FastAPI app
app = FastAPI(title="Overseer", description="The Invisible Project Manager")

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)


def get_store() -> JsonTaskStore:
    """Dependency to get the task store."""
    root = os.environ.get("OVERSEER_ROOT", os.getcwd())
    store = JsonTaskStore(root)
    store.ensure_initialized()
    return store


StoreDep = Annotated[JsonTaskStore, Depends(get_store)]


# --- Main Routes ---


@app.get("/", response_class=RedirectResponse)
async def root():
    """Redirect to tasks view."""
    return RedirectResponse(url="/tasks", status_code=302)


@app.get("/tasks", response_class=HTMLResponse)
async def tasks_page(
    request: Request,
    store: StoreDep,
    view: str = Query(default="kanban", pattern="^(kanban|list)$"),
):
    """Main tasks page with view toggle."""
    all_tasks = store.list_tasks()
    tasks_by_status = {
        "active": [t for t in all_tasks if t.status == TaskStatus.ACTIVE],
        "backlog": [t for t in all_tasks if t.status == TaskStatus.BACKLOG],
        "blocked": [t for t in all_tasks if t.status == TaskStatus.BLOCKED],
        "done": [t for t in all_tasks if t.status == TaskStatus.DONE],
    }
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "view": view,
            "tasks_by_status": tasks_by_status,
            "task_types": [t.value for t in TaskType],
            "statuses": [s.value for s in TaskStatus],
        },
    )


# --- Partial Routes (HTMX) ---


@app.get("/partials/kanban", response_class=HTMLResponse)
async def kanban_partial(request: Request, store: StoreDep):
    """HTMX partial: Kanban board."""
    all_tasks = store.list_tasks()
    tasks_by_status = {
        "active": [t for t in all_tasks if t.status == TaskStatus.ACTIVE],
        "backlog": [t for t in all_tasks if t.status == TaskStatus.BACKLOG],
        "blocked": [t for t in all_tasks if t.status == TaskStatus.BLOCKED],
        "done": [t for t in all_tasks if t.status == TaskStatus.DONE],
    }
    return templates.TemplateResponse(
        request,
        "components/kanban.html",
        {"tasks_by_status": tasks_by_status},
    )


@app.get("/partials/list", response_class=HTMLResponse)
async def list_partial(request: Request, store: StoreDep):
    """HTMX partial: List view."""
    all_tasks = store.list_tasks()
    return templates.TemplateResponse(
        request,
        "components/list.html",
        {"tasks": all_tasks},
    )


@app.get("/tasks/new", response_class=HTMLResponse)
async def new_task_form(request: Request):
    """HTMX partial: New task form modal."""
    return templates.TemplateResponse(
        request,
        "components/task_form.html",
        {
            "task": None,
            "task_types": [t.value for t in TaskType],
            "statuses": [s.value for s in TaskStatus],
        },
    )


# --- Task CRUD Routes ---


@app.post("/tasks", response_class=HTMLResponse)
async def create_task(
    request: Request,
    store: StoreDep,
    title: str = Form(...),
    task_type: str = Form(...),
    status: str = Form(default="backlog"),
    context: str = Form(default=""),
):
    """Create a new task."""
    task = store.create_task(
        title=title,
        task_type=TaskType(task_type),
        status=TaskStatus(status),
        created_by=Origin.HUMAN,
        context=context if context else None,
    )
    # Return the new task card for HTMX to insert
    return templates.TemplateResponse(
        request,
        "components/task_card.html",
        {"task": task},
    )


@app.get("/tasks/{task_id}", response_class=HTMLResponse)
async def get_task(request: Request, task_id: str, store: StoreDep):
    """Get task detail."""
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return templates.TemplateResponse(
        request,
        "components/task_card.html",
        {"task": task, "expanded": True},
    )


@app.patch("/tasks/{task_id}/status", response_class=HTMLResponse)
async def update_task_status(
    request: Request,
    task_id: str,
    store: StoreDep,
    status: str = Form(...),
):
    """Update task status (for drag-and-drop)."""
    task = store.update_task(task_id, status=TaskStatus(status))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return templates.TemplateResponse(
        request,
        "components/task_card.html",
        {"task": task},
    )


@app.delete("/tasks/{task_id}", response_class=HTMLResponse)
async def delete_task(task_id: str, store: StoreDep):
    """Delete a task."""
    deleted = store.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    # Return empty response - HTMX will remove the element
    return HTMLResponse(content="", status_code=200)
