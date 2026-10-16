"""Service layer for skill discovery, indexing, and search.

This module encapsulates the business logic of managing skills: it wraps
the discovery engine and the database layer into a clean service API that
the REST routes delegate to. Keeping this logic separate from the API
handlers makes it reusable from CLI tools and testable without HTTP.
"""
from __future__ import annotations

import pathlib
from contextlib import contextmanager
from typing import Any

import sqlite3

from app.core.engine import discover_skills
from app.db import database
from app.db.database import get_connection


class SkillService:
    """High-level operations for the skill index.

    Each method opens its own database connection (SQLite handles
    concurrent reads efficiently via WAL mode) and returns typed results.
    """

    def discover_and_index(self, repository_path: str) -> dict[str, Any]:
        """Run the discovery engine on *repository_path* and persist results.

        Returns a dict suitable for JSON serialization with the discovery
        report fields. Raises ValueError if the path is invalid.
        """
        report = discover_skills(repository_path)

        if report.errors:
            raise ValueError(report.errors[0])

        db_path = database.get_db_path()
        with database.get_connection(db_path) as conn:
            run_id = database.save_discovery(conn, report)

        # Serialize the report for the API response
        skills = [self._serialize_skill(s, report.root_path) for s in report.skills]
        return {
            "skills": skills,
            "total_found": report.total_found,
            "total_valid": report.total_valid,
            "total_invalid": report.total_invalid,
            "root_path": report.root_path,
            "errors": report.errors,
            "discovered_at": report.discovered_at,
            "discovery_run_id": run_id,
        }

    def search(
        self, query: str, *, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """Search indexed skills by name, description, topic, or path."""
        db_path = database.get_db_path()
        with database.get_connection(db_path) as conn:
            rows, total = database.search_indexed_skills(
                conn, query, limit=limit, offset=offset
            )
        return {
            "skills": rows,
            "total": total,
            "limit": limit,
            "offset": offset,
            "query": query,
        }

    def list(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """List all indexed skills with pagination."""
        return self.search("", limit=limit, offset=offset)

    def get_by_id(self, skill_id: int) -> dict[str, Any] | None:
        """Retrieve a single skill by database ID."""
        db_path = database.get_db_path()
        with database.get_connection(db_path) as conn:
            return database.get_skill_by_id(conn, skill_id)

    def clear(self, root_path: str | None = None) -> int:
        """Delete indexed skills. If *root_path* is given, only delete skills
        discovered from that path. Returns the number of rows deleted.
        """
        db_path = database.get_db_path()
        with database.get_connection(db_path) as conn:
            return database.clear_skills(conn, root_path=root_path)

    @staticmethod
    def _serialize_skill(skill, root_path: str) -> dict[str, Any]:
        """Convert a SkillRecord dataclass to a dict for API responses."""
        return {
            "id": None,
            "path": skill.path,
            "root_path": root_path,
            "name": skill.name,
            "description": skill.description,
            "topic": skill.topic,
            "scope": skill.scope,
            "valid": skill.valid,
            "errors": skill.errors,
            "content_length": skill.content_length,
            "discovered_at": skill.discovered_at,
        }


# Module-level singleton for convenience
service = SkillService()