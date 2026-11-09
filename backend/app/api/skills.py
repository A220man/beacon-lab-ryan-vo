"""REST API for skill discovery and search.

Endpoints:
    POST   /api/v1/skills/discover  — Discover and index skills in a directory
    GET    /api/v1/skills/search   — Search indexed skills (query param: q)
    GET    /api/v1/skills/list     — List all indexed skills (paginated)
    GET    /api/v1/skills/{id}     — Get a single skill by ID
    DELETE /api/v1/skills/clear     — Clear indexed skills (optional root_path)
"""
from __future__ import annotations

import json
import os
from typing import Any
from fastapi import APIRouter, HTTPException, Query
from app.core.engine import discover_skills
from app.db import database
from app.core.validators import lint_skill, validate_content
from app.core.models import DiscoveryRequest, DiscoveryReport, SearchResponse, SearchResult, ValidationRequest, ValidationResponse, SkillRecord


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
        run_id = database.save_discovery(conn, report)

    # Re-fetch skills from database for this discovery run to get assigned IDs
    with database.get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, path, name, description, topic, scope, valid, errors,
                   content_length, discovered_at, root_path
            FROM skills
            WHERE discovery_run_id = ?
            ORDER BY COALESCE(topic, '') ASC, COALESCE(name, path) ASC
            """,
            (run_id,),
        ).fetchall()

    # Convert to SkillRecord with IDs
    skills_with_ids = []
    for row in rows:
        row_dict = dict(row)
        row_dict["errors"] = json.loads(row_dict["errors"]) if row_dict.get("errors") else []
        row_dict["valid"] = bool(row_dict["valid"])
        skill = SkillRecord(
            id=row_dict["id"],
            path=row_dict["path"],
            name=row_dict["name"],
            description=row_dict["description"],
            topic=row_dict["topic"],
            scope=row_dict["scope"],
            valid=row_dict["valid"],
            errors=row_dict["errors"],
            content_length=row_dict["content_length"],
            discovered_at=row_dict["discovered_at"],
            root_path=row_dict["root_path"],
        )
        skills_with_ids.append(skill)

    return DiscoveryReport(
        skills=skills_with_ids,
        total_found=report.total_found,
        total_valid=report.total_valid,
        total_invalid=report.total_invalid,
        root_path=report.root_path,
        errors=report.errors,
        discovered_at=report.discovered_at,
    )


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



@router.post("/validate", response_model=ValidationResponse)
def validate(request: ValidationRequest) -> ValidationResponse:
    """Validate and lint a SKILL.md file's content.

    Returns a completeness score (0-100), missing sections, word count,
    recommendations, and optional lint issues.
    """
    report = validate_content(request.content)
    lint_issues: list[str] = []
    if request.include_lint:
        lint_issues = lint_skill(request.content)
    return ValidationResponse(
        score=report.score,
        missing_sections=report.missing_sections,
        word_count=report.word_count,
        recommendations=report.recommendations,
        lint_issues=lint_issues,
    )


@router.get("/{skill_id}/lint", response_model=ValidationResponse)
def lint_skill_by_id(
    skill_id: int,
    include_lint: bool = Query(default=True, description="Whether to run lint checks"),
) -> ValidationResponse:
    """Get lint report for a discovered skill by ID.

    Fetches the skill's file content from disk and runs validation/linting.
    """
    db_path = database.get_db_path()
    with database.get_connection(db_path) as conn:
        skill = database.get_skill_by_id(conn, skill_id)

    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill not found: id={skill_id}")

    # Resolve the full path to the SKILL.md file
    root_path = skill.get("root_path") or "."
    skill_path = skill.get("path", "")
    full_path = os.path.join(root_path, skill_path)

    if not os.path.exists(full_path):
        raise HTTPException(
            status_code=404,
            detail=f"Skill file not found on disk: {full_path}",
        )

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    report = validate_content(content)
    lint_issues_list: list[str] = []
    if include_lint:
        lint_issues_list = lint_skill(content)
    return ValidationResponse(
        score=report.score,
        missing_sections=report.missing_sections,
        word_count=report.word_count,
        recommendations=report.recommendations,
        lint_issues=lint_issues_list,
    )