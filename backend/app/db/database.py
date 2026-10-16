"""SQLite database layer for persistent skill indexing.

Uses parameterized SQL throughout to prevent injection. All timestamps
are stored as UTC ISO 8601 strings.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Generator

from app.core.engine import DiscoveryReport, SkillRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS discovery_runs (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    root_path TEXT NOT NULL,
    started_at TEXT NOT NULL,
    total_found INTEGER NOT NULL,
    total_valid INTEGER NOT NULL,
    total_invalid INTEGER NOT NULL,
    errors TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS skills (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    discovery_run_id INTEGER NOT NULL REFERENCES discovery_runs(id),
    path           TEXT NOT NULL,
    root_path      TEXT NOT NULL,
    name           TEXT,
    description    TEXT,
    topic          TEXT,
    scope          TEXT,
    valid          INTEGER NOT NULL,
    errors         TEXT NOT NULL,
    content_length INTEGER NOT NULL,
    discovered_at  TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now', 'utc'))
);

CREATE INDEX IF NOT EXISTS idx_skills_name  ON skills(name);
CREATE INDEX IF NOT EXISTS idx_skills_topic ON skills(topic);
CREATE INDEX IF NOT EXISTS idx_skills_root  ON skills(root_path);
CREATE INDEX IF NOT EXISTS idx_skills_valid ON skills(valid);
CREATE INDEX IF NOT EXISTS idx_skills_path  ON skills(path);
"""


def get_db_path() -> str:
    """Return the configured database path."""
    return os.environ.get("DATABASE_PATH", "./data/beacon.db")


def init_database(db_path: str | None = None) -> None:
    """Initialize the SQLite database with the full schema."""
    path = db_path or get_db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


@dataclass
class DBConfig:
    """Database configuration holder."""
    path: str = ""

    def __post_init__(self) -> None:
        if not self.path:
            self.path = get_db_path()


@contextmanager
def get_connection(db_path: str | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite connections."""
    path = db_path or get_db_path()
    # Allow concurrent reads from FastAPI
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_discovery(conn: sqlite3.Connection, report: DiscoveryReport) -> int:
    """Persist a discovery report to the database.

    Inserts the discovery run record, then inserts all skill records.
    Uses a transaction — either all rows are inserted or none.

    Returns the discovery run ID.
    """
    cursor = conn.cursor()

    errors_json = json.dumps(report.errors)
    cursor.execute(
        """
        INSERT INTO discovery_runs (root_path, started_at, total_found, total_valid, total_invalid, errors)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            report.root_path,
            report.discovered_at,
            report.total_found,
            report.total_valid,
            report.total_invalid,
            errors_json,
        ),
    )
    run_id = cursor.lastrowid

    for skill in report.skills:
        errors_json = json.dumps(skill.errors)
        cursor.execute(
            """
            INSERT INTO skills
                (discovery_run_id, path, root_path, name, description, topic,
                 scope, valid, errors, content_length, discovered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                skill.path,
                report.root_path,
                skill.name,
                skill.description,
                skill.topic,
                skill.scope,
                1 if skill.valid else 0,
                errors_json,
                skill.content_length,
                report.discovered_at,
            ),
        )

    conn.commit()
    return run_id


def search_indexed_skills(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Search the skills index by name, description, topic, or path.

    Returns ``(rows, total_count)``.
    """
    q = query.lower().strip() if query else ""

    if q:
        like_pattern = f"%{q}%"
        where_clause = """
            WHERE name LIKE ?
               OR COALESCE(description, '') LIKE ?
               OR COALESCE(topic, '') LIKE ?
               OR path LIKE ?
        """
        params: list[Any] = [like_pattern, like_pattern, like_pattern, like_pattern]
    else:
        where_clause = ""
        params = []

    # Get total count
    count_sql = f"SELECT COUNT(*) FROM skills {where_clause}"
    total = conn.execute(count_sql, params).fetchone()[0]

    # Get paginated results
    params.extend([limit, offset])
    results = conn.execute(
        f"""
        SELECT id, path, name, description, topic, scope, valid, errors,
               content_length, discovered_at
        FROM skills
        {where_clause}
        ORDER BY COALESCE(topic, '') ASC, COALESCE(name, path) ASC
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()

    rows = []
    for row in results:
        row_dict = dict(row)
        row_dict["errors"] = json.loads(row_dict["errors"]) if row_dict.get("errors") else []
        row_dict["valid"] = bool(row_dict["valid"])
        rows.append(row_dict)

    return rows, total


def get_skill_by_id(conn: sqlite3.Connection, skill_id: int) -> dict[str, Any] | None:
    """Retrieve a single skill by ID."""
    row = conn.execute(
        """
        SELECT id, path, name, description, topic, scope, valid, errors,
               content_length, discovered_at, root_path
        FROM skills
        WHERE id = ?
        """,
        (skill_id,),
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["errors"] = json.loads(result["errors"]) if result.get("errors") else []
    result["valid"] = bool(result["valid"])
    return result


def clear_skills(conn: sqlite3.Connection, *, root_path: str | None = None) -> int:
    """Delete indexed skills. If *root_path* is given, only delete skills
    discovered from that path. Otherwise delete all.

    Returns the number of rows deleted.
    """
    cursor = conn.cursor()
    if root_path:
        cursor.execute("DELETE FROM skills WHERE root_path = ?", (root_path,))
        deleted = cursor.rowcount
        cursor.execute("DELETE FROM discovery_runs WHERE root_path = ?", (root_path,))
    else:
        cursor.execute("DELETE FROM skills")
        deleted = cursor.rowcount
        cursor.execute("DELETE FROM discovery_runs")
    conn.commit()
    return deleted