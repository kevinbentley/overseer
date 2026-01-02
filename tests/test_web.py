"""Tests for the Overseer web frontend."""

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from overseer.web.app import app, get_store
from overseer.store import JsonTaskStore
from overseer.models import TaskType, TaskStatus


@pytest.fixture
def temp_overseer_dir():
    """Create a temporary .overseer directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = JsonTaskStore(tmpdir)
        store.initialize()
        yield tmpdir, store


@pytest.fixture
def client(temp_overseer_dir):
    """Test client with overridden store dependency."""
    tmpdir, store = temp_overseer_dir

    def override_get_store():
        return store

    app.dependency_overrides[get_store] = override_get_store

    with TestClient(app) as client:
        yield client, store

    app.dependency_overrides.clear()


class TestMainRoutes:
    """Test main page routes."""

    def test_root_redirects_to_tasks(self, client):
        """Root path should redirect to /tasks."""
        test_client, _ = client
        response = test_client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/tasks"

    def test_tasks_page_kanban_view(self, client):
        """Tasks page with kanban view should load."""
        test_client, _ = client
        response = test_client.get("/tasks?view=kanban")
        assert response.status_code == 200
        assert b"kanban-board" in response.content

    def test_tasks_page_list_view(self, client):
        """Tasks page with list view should load."""
        test_client, _ = client
        response = test_client.get("/tasks?view=list")
        assert response.status_code == 200
        assert b"task-table" in response.content


class TestPartialRoutes:
    """Test HTMX partial routes."""

    def test_kanban_partial(self, client):
        """Kanban partial should return board HTML."""
        test_client, _ = client
        response = test_client.get("/partials/kanban")
        assert response.status_code == 200
        assert b"kanban-board" in response.content

    def test_list_partial(self, client):
        """List partial should return table HTML."""
        test_client, _ = client
        response = test_client.get("/partials/list")
        assert response.status_code == 200
        assert b"task-table" in response.content

    def test_new_task_form(self, client):
        """New task form should return form HTML."""
        test_client, _ = client
        response = test_client.get("/tasks/new")
        assert response.status_code == 200
        assert b"task-form" in response.content


class TestTaskCRUD:
    """Test task CRUD operations."""

    def test_create_task(self, client):
        """Creating a task should return task card HTML."""
        test_client, store = client
        response = test_client.post(
            "/tasks",
            data={
                "title": "Test task",
                "task_type": "feature",
                "status": "backlog",
                "context": "Test context",
            },
        )
        assert response.status_code == 200
        assert b"Test task" in response.content
        assert b"TASK-1" in response.content

        # Verify task was created in store
        tasks = store.list_tasks()
        assert len(tasks) == 1
        assert tasks[0].title == "Test task"

    def test_update_task_status(self, client):
        """Updating task status should return updated card."""
        test_client, store = client

        # Create a task first
        task = store.create_task("Test task", TaskType.FEATURE)

        response = test_client.patch(
            f"/tasks/{task.id}/status",
            data={"status": "active"},
        )
        assert response.status_code == 200

        # Verify status was updated
        updated = store.get_task(task.id)
        assert updated.status == TaskStatus.ACTIVE

    def test_delete_task(self, client):
        """Deleting a task should return empty response."""
        test_client, store = client

        # Create a task first
        task = store.create_task("Test task", TaskType.FEATURE)
        task_id = task.id

        response = test_client.delete(f"/tasks/{task_id}")
        assert response.status_code == 200
        assert response.content == b""

        # Verify task was deleted
        assert store.get_task(task_id) is None

    def test_delete_nonexistent_task(self, client):
        """Deleting nonexistent task should return 404."""
        test_client, _ = client
        response = test_client.delete("/tasks/TASK-999")
        assert response.status_code == 404

    def test_update_nonexistent_task(self, client):
        """Updating nonexistent task should return 404."""
        test_client, _ = client
        response = test_client.patch(
            "/tasks/TASK-999/status",
            data={"status": "active"},
        )
        assert response.status_code == 404


class TestTaskDisplay:
    """Test task display in views."""

    def test_tasks_grouped_by_status(self, client):
        """Tasks should be grouped by status in kanban view."""
        test_client, store = client

        # Create tasks with different statuses
        store.create_task("Active task", TaskType.FEATURE, status=TaskStatus.ACTIVE)
        store.create_task("Backlog task", TaskType.BUG, status=TaskStatus.BACKLOG)
        store.create_task("Done task", TaskType.CHORE, status=TaskStatus.DONE)

        response = test_client.get("/partials/kanban")
        content = response.content.decode()

        assert "Active task" in content
        assert "Backlog task" in content
        assert "Done task" in content

    def test_task_with_jira_key(self, client):
        """Task with Jira key should display badge."""
        test_client, store = client

        store.create_task("Jira task", TaskType.FEATURE, jira_key="PROJ-123")

        response = test_client.get("/partials/kanban")
        assert b"PROJ-123" in response.content
        assert b"badge-jira" in response.content
