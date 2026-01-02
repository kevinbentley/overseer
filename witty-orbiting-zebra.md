# Overseer Web Frontend Implementation Plan

## Summary
Add a FastAPI + HTMX + Jinja2 web frontend with Kanban board and list views. Standalone entry point (`overseer-web`).

## Tech Stack
- **Backend**: FastAPI + Uvicorn
- **Templates**: Jinja2 with HTMX for interactivity
- **Styling**: Pico CSS (classless, minimal)
- **Drag-and-drop**: SortableJS

## Project Structure

```
src/overseer/web/
├── __init__.py          # Entry point (main function for uvicorn)
├── app.py               # FastAPI app, routes, dependencies
├── templates/
│   ├── base.html        # Layout with nav, modal container
│   ├── index.html       # Main page with view toggle
│   └── components/
│       ├── kanban.html      # Kanban board (4 columns)
│       ├── list.html        # Table view
│       ├── task_card.html   # Single task (kanban)
│       ├── task_row.html    # Single task (list)
│       └── task_form.html   # Create/edit modal
└── static/
    ├── css/styles.css   # Kanban grid, task badges
    └── js/
        ├── htmx.min.js
        └── sortable.min.js
```

## Dependencies to Add

```toml
# pyproject.toml
dependencies = [
    ...existing...,
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "jinja2>=3.1.0",
    "python-multipart>=0.0.6",
]

[project.scripts]
overseer = "overseer.cli:main"
overseer-web = "overseer.web:main"
```

## API Routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Redirect to `/tasks` |
| GET | `/tasks?view=kanban\|list` | Full page with view |
| GET | `/partials/kanban` | HTMX: kanban fragment |
| GET | `/partials/list` | HTMX: list fragment |
| GET | `/tasks/new` | HTMX: create form modal |
| POST | `/tasks` | Create task |
| GET | `/tasks/{id}` | Task detail |
| PATCH | `/tasks/{id}/status` | Update status (drag-drop) |
| DELETE | `/tasks/{id}` | Delete task |

## Key HTMX Patterns

1. **View toggle**: `hx-get="/partials/kanban"` swaps main content
2. **Drag-and-drop**: SortableJS `onEnd` triggers `htmx.ajax('PATCH', ...)`
3. **Create modal**: `hx-target="#modal-content"` opens dialog
4. **Delete**: `hx-delete` with `hx-swap="outerHTML"` removes card

## Implementation Steps

### Phase 1: Setup
- [ ] Create `src/overseer/web/` directory
- [ ] Add dependencies to `pyproject.toml`
- [ ] Create `__init__.py` with `main()` entry point
- [ ] Create `app.py` with FastAPI app and store dependencies
- [ ] Download HTMX and SortableJS to static/js/

### Phase 2: Templates
- [ ] Create `base.html` with Pico CSS, HTMX, nav
- [ ] Create `index.html` with view toggle container
- [ ] Create `components/kanban.html` (4-column grid)
- [ ] Create `components/list.html` (table)
- [ ] Create `components/task_card.html` and `task_row.html`
- [ ] Create `static/css/styles.css` (kanban grid, badges)

### Phase 3: Routes
- [ ] Implement GET `/tasks` with view param
- [ ] Implement GET `/partials/kanban` and `/partials/list`
- [ ] Implement POST `/tasks` (create)
- [ ] Implement PATCH `/tasks/{id}/status` (drag-drop)
- [ ] Implement DELETE `/tasks/{id}`
- [ ] Create `components/task_form.html`

### Phase 4: Polish
- [ ] Add SortableJS initialization script
- [ ] Modal open/close handling
- [ ] Error handling and flash messages
- [ ] Mobile responsive CSS
- [ ] Write tests in `tests/test_web.py`

## Critical Files to Modify/Create

**Modify:**
- `pyproject.toml` - Add dependencies and entry point

**Create:**
- `src/overseer/web/__init__.py`
- `src/overseer/web/app.py`
- `src/overseer/web/templates/*.html` (6 files)
- `src/overseer/web/static/css/styles.css`
- `src/overseer/web/static/js/htmx.min.js`
- `src/overseer/web/static/js/sortable.min.js`
- `tests/test_web.py`

## Usage

```bash
# Install updated package
pip install -e .

# Run web server
overseer-web

# Or with custom port
OVERSEER_WEB_PORT=9000 overseer-web

# Access at http://127.0.0.1:8000
```
