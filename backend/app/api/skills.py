"""REST API for skill discovery and search.

Endpoints:
    POST   /api/v1/skills/discover  — Discover and index skills in a directory
    GET    /api/v1/skills/search   — Search indexed skills (query param: q)
    GET    /api/v1/skills/list     — List all indexed skills (paginated)
    GET    /api/v1/skills/{id}     — Get a single skill by ID
    DELETE /api/v1/skills/clear     — Clear indexed skills (optional root_path)
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.core.engine import discover_skills
from app.core.models import DiscoveryRequest, DiscoveryReport, SearchResponse, SearchResult
from app.db import database

router = APIRouter()


@router.post("/discover", response_model=DiscoveryReport, status_code=201)
def discover(request: DiscoveryRequest) -> DiscoveryReport:
    """Discover and validate all SKILL.md files in *repository_path*.

    Recursively walks the directory tree — not limited to a ``skills/``
    directory — to find skills at any depth. Results are validated and
    persisted in SQLite for later search.

    Returns the full :class:`DiscoveryReport` including per-skill validation
    status and errors.
    """
    report = discover_skills(request.repository_path)

    if report.errors:
        # Filesystem-level errors (e.g. path doesn't exist) — return 400
        # with details. Skill-level validation errors are returned in the report
        # because they are useful, not fatal.
        raise HTTPException(status_code=400, detail=report.errors[0])

    # Persist to database
    db_path = database.get_db_path()
    with database.get_connection(db_path) as conn:
        database.save_discovery(conn, report)

    return report


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(default="", description="Search query (matches name, description, topic, path)"),
    limit: int = Query(default=50, ge=1, le=500, description="Maximum results"),
    offset: int = Query(default=0, ge=0, description="Result offset for pagination"),
) -> SearchResponse:
    """Search indexed skills by name, description, topic, or path.

    Matching is case-insensitive and substring-based.
    """
    db_path = database.get_db_path()
    with database.get_connection(db_path) as conn:
        rows, total = database.search_indexed_skills(conn, q, limit=limit, offset=offset)

    skills = [SearchResult(**row) for row in rows]
    return SearchResponse(
        skills=skills,
        total=total,
        limit=limit,
        offset=offset,
        query=q,
    )


@router.get("/list", response_model=SearchResponse)
def list_skills(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> SearchResponse:
    """List all indexed skills with pagination."""
    db_path = database.get_db_path()
    with database.get_connection(db_path) as conn:
        rows, total = database.search_indexed_skills(conn, "", limit=limit, offset=offset)

    skills = [SearchResult(**row) for row in rows]
    return SearchResponse(
        skills=skills,
        total=total,
        limit=limit,
        offset=offset,
        query="",
    )


@router.get("/{skill_id}", response_model=dict[str, Any])
def get_skill(skill_id: int) -> dict[str, Any]:
    """Get a single skill by ID."""
    db_path = database.get_db_path()
    with database.get_connection(db_path) as conn:
        skill = database.get_skill_by_id(conn, skill_id)

    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill not found: id={skill_id}")

    return skill


@router.delete("/clear")
def clear_index(
    root_path: str | None = Query(default=None, description="Only clear skills from this root path"),
) -> dict[str, int]:
    """Clear indexed skills.

    If *root_path* is provided, only skills discovered from that path are
    deleted. Otherwise all indexed skills are removed.
    """
    db_path = database.get_db_path()
    with database.get_connection(db_path) as conn:
        deleted = database.clear_skills(conn, root_path=root_path)

    return {"deleted": deleted}