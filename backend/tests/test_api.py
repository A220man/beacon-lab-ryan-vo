"""Integration tests for the skills API.

These tests cross the real HTTP boundary using FastAPI's TestClient,
exercising the complete request/response cycle including the database
persistence layer.
"""
from __future__ import annotations

import pathlib

import pytest
from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    """GET /health returns service info."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "beacon-lab"
    assert "version" in data
    assert data["status"] == "ok"


def test_discover_endpoint_returns_results(client: TestClient, sample_repo: pathlib.Path):
    """POST /discover returns discovered and validated skills."""
    resp = client.post(
        "/api/v1/skills/discover",
        json={"repository_path": str(sample_repo)},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["root_path"] == str(sample_repo)
    assert data["total_found"] == 6
    assert data["total_valid"] == 3
    assert data["total_invalid"] == 3
    assert len(data["skills"]) == 6
    assert data["errors"] == []
    # Verify discovered_at timestamp is present
    assert data["discovered_at"]
    assert data["skills"][0]["discovered_at"]


def test_discover_endpoint_nonexistent_path_returns_400(client: TestClient):
    """POST /discover with a bad path returns 400."""
    resp = client.post(
        "/api/v1/skills/discover",
        json={"repository_path": "/nonexistent/path/xyz"},
    )
    assert resp.status_code == 400
    assert "does not exist" in resp.json()["detail"]


def test_discover_endpoint_rejects_extra_fields(client: TestClient, sample_repo: pathlib.Path):
    """POST /discover rejects requests with extra fields (model forbids extras)."""
    resp = client.post(
        "/api/v1/skills/discover",
        json={"repository_path": str(sample_repo), "unexpected": "field"},
    )
    assert resp.status_code == 422


def test_search_after_discover(client: TestClient, sample_repo: pathlib.Path):
    """Discovered skills are searchable by name, topic, and description."""
    # Index skills
    resp = client.post(
        "/api/v1/skills/discover",
        json={"repository_path": str(sample_repo)},
    )
    assert resp.status_code == 201

    # Search by name
    resp = client.get("/api/v1/skills/search?q=r8")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["query"] == "r8"
    assert any("r8" in (s["name"] or "").lower() for s in data["skills"])

    # Search by topic
    resp = client.get("/api/v1/skills/search?q=performance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["skills"][0]["topic"] == "performance"

    # Search by path
    resp = client.get("/api/v1/skills/search?q=devtools")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert all("devtools" in s["path"] or s["topic"] == "devtools" for s in data["skills"])
    assert "devtools" in data["skills"][0]["path"] or data["skills"][0]["topic"] == "devtools"


def test_list_all_skills(client: TestClient, sample_repo: pathlib.Path):
    """GET /list returns all indexed skills."""
    client.post(
        "/api/v1/skills/discover",
        json={"repository_path": str(sample_repo)},
    )
    resp = client.get("/api/v1/skills/list?limit=50&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 6
    assert len(data["skills"]) == 6


def test_list_skills_pagination(client: TestClient, sample_repo: pathlib.Path):
    """GET /list respects pagination parameters."""
    client.post(
        "/api/v1/skills/discover",
        json={"repository_path": str(sample_repo)},
    )
    resp = client.get("/api/v1/skills/list?limit=3&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["limit"] == 3
    assert data["offset"] == 0
    assert data["total"] == 6
    assert len(data["skills"]) == 3

    resp = client.get("/api/v1/skills/list?limit=3&offset=3")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["skills"]) == 3


def test_get_skill_by_id(client: TestClient, sample_repo: pathlib.Path):
    """GET /{id} returns a single skill by ID."""
    client.post(
        "/api/v1/skills/discover",
        json={"repository_path": str(sample_repo)},
    )
    # Get all and use the first ID
    resp = client.get("/api/v1/skills/list?limit=1&offset=0")
    assert resp.status_code == 200
    skill_id = resp.json()["skills"][0]["id"]

    resp = client.get(f"/api/v1/skills/{skill_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == skill_id
    assert "path" in data
    assert "name" in data
    assert "errors" in data
    assert isinstance(data["errors"], list)


def test_get_skill_not_found(client: TestClient):
    """GET /{id} with unknown ID returns 404."""
    resp = client.get("/api/v1/skills/99999")
    assert resp.status_code == 404


def test_clear_all_skills(client: TestClient, sample_repo: pathlib.Path):
    """DELETE /clear removes all indexed skills."""
    client.post(
        "/api/v1/skills/discover",
        json={"repository_path": str(sample_repo)},
    )
    resp = client.get("/api/v1/skills/list")
    assert resp.json()["total"] == 6

    resp = client.delete("/api/v1/skills/clear")
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 6

    resp = client.get("/api/v1/skills/list")
    assert resp.json()["total"] == 0


def test_discover_persists_to_database(client: TestClient, sample_repo: pathlib.Path):
    """Discovery results are stored in the database and survive across requests."""
    resp = client.post(
        "/api/v1/skills/discover",
        json={"repository_path": str(sample_repo)},
    )
    assert resp.status_code == 201

    # Without calling discover again, search should find persistently stored results
    resp = client.get("/api/v1/skills/search?q=r8")
    assert resp.status_code == 200


def test_validate_skill_content(client: TestClient):
    """POST /validate returns completeness score and lint issues."""
    complete_skill = """---
name: test-skill
description: A test skill
---
# Test Skill

## Prerequisites
None

## Usage
Run it.

## Installation
pip install test

## Examples
test()

## Troubleshooting
None

## References
None
"""
    resp = client.post(
        "/api/v1/skills/validate",
        json={"content": complete_skill, "include_lint": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] == 100
    assert data["missing_sections"] == []
    assert data["word_count"] > 0
    assert isinstance(data["recommendations"], list)
    assert isinstance(data["lint_issues"], list)


def test_validate_skill_content_no_lint(client: TestClient):
    """POST /validate with include_lint=false skips lint checks."""
    skill = """---
name: test
description: test
---
# Test
## Usage
Run it.
"""
    resp = client.post(
        "/api/v1/skills/validate",
        json={"content": skill, "include_lint": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["lint_issues"] == []


def test_validate_skill_rejects_empty_content(client: TestClient):
    """POST /validate rejects empty content."""
    resp = client.post(
        "/api/v1/skills/validate",
        json={"content": "", "include_lint": True},
    )
    assert resp.status_code == 422


def test_validate_skill_lint_detects_issues(client: TestClient):
    """POST /validate detects lint issues like bare URLs."""
    skill = """---
name: test
description: test
---
# Test
## Usage
See https://example.com for details
"""
    resp = client.post(
        "/api/v1/skills/validate",
        json={"content": skill, "include_lint": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any("bare url" in issue.lower() for issue in data["lint_issues"])