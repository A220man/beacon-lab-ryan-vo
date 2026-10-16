"""Beacon Lab backend application.

Beacon Lab is an AI/ML developer tool (AI infrastructure) that discovers,
validates, and indexes agent skills (SKILL.md files) across arbitrary
repository layouts to help LLM agents find prompt modules beyond
predefined directory patterns.
"""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import init_database
from app.api.skills import router as skills_router

VERSION = "1.0.0"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    This factory pattern is used so that both Docker and local commands
    use the same entrypoint: ``uvicorn app.main:app``.
    """
    app = FastAPI(
        title="Beacon Lab",
        description=(
            "AI/ML developer tool for discovering, validating, and indexing "
            "agent skills (SKILL.md files) across arbitrary repository layouts."
        ),
        version=VERSION,
        contact={
            "name": "Ryan Vo",
            "email": "ryandtvo@gmail.com",
        },
    )

    # CORS — allow frontend origin (operator-configurable via env)
    frontend_origin = os.environ.get("FRONTEND_URL", "http://127.0.0.1:5173")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(skills_router, prefix="/api/v1/skills", tags=["skills"])

    # Initialize database on startup
    db_path = os.environ.get("DATABASE_PATH", "./data/beacon.db")
    db_dir = os.path.dirname(db_path)
    if db_dir:
        Path(db_dir).mkdir(parents=True, exist_ok=True)
    init_database(db_path)

    # Health check
    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "service": "beacon-lab", "version": VERSION}

    return app


# Module-level app instance for uvicorn
app = create_app()