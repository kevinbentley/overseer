"""Overseer Web Frontend - FastAPI + HTMX Kanban board."""

import os
import uvicorn


def main():
    """Entry point for overseer-web command."""
    port = int(os.environ.get("OVERSEER_WEB_PORT", "8000"))
    host = os.environ.get("OVERSEER_WEB_HOST", "127.0.0.1")

    uvicorn.run(
        "overseer.web.app:app",
        host=host,
        port=port,
        reload=os.environ.get("OVERSEER_WEB_RELOAD", "").lower() == "true",
    )


if __name__ == "__main__":
    main()
