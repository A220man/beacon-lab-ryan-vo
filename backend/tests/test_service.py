"""Tests for the SkillService layer."""
import pathlib

import pytest

from app.services.skill_service import SkillService
from app.db import database


@pytest.fixture
def service(tmp_path, monkeypatch):
    """Create a SkillService with an isolated database."""
    db_path = str(tmp_path / "test_service.db")
    monkeypatch.setenv("DATABASE_PATH", db_path)
    database.init_database(db_path)
    return SkillService()


@pytest.fixture
def sample_repo(tmp_path):
    """Create a sample repo with a couple of SKILL.md files."""
    repo = tmp_path / "service_repo"
    repo.mkdir()
    (repo / "performance" / "r8-analyzer").mkdir(parents=True)
    (repo / "performance" / "r8-analyzer" / "SKILL.md").write_text(
        "---\nname: r8-analyzer\ndescription: Analyze R8 issues\n---\n\n"
        "# R8 Analyzer\n\nValid body content here.\n"
    )
    (repo / "SKILL.md").write_text(
        "---\nname: top-skill\n---\n\nMissing description.\n"
    )
    return repo


def test_service_discover_and_index(service, sample_repo):
    """Service discovers and persists skills, returning a report dict."""
    data = service.discover_and_index(str(sample_repo))
    assert data["total_found"] == 2
    assert data["total_valid"] == 1
    assert data["total_invalid"] == 1
    assert len(data["skills"]) == 2
    assert data["discovery_run_id"] > 0


def test_service_discover_invalid_path_raises(service):
    """Service raises ValueError for nonexistent paths."""
    with pytest.raises(ValueError, match="does not exist"):
        service.discover_and_index("/nonexistent/path/xyz")


def test_service_search(service, sample_repo):
    """Service search returns matching skills."""
    service.discover_and_index(str(sample_repo))
    result = service.search("r8")
    assert result["total"] >= 1
    assert any("r8-analyzer" in (s["name"] or "") for s in result["skills"])


def test_service_list_all(service, sample_repo):
    """Service list returns all indexed skills."""
    service.discover_and_index(str(sample_repo))
    result = service.list(limit=50, offset=0)
    assert result["total"] == 2
    assert len(result["skills"]) == 2


def test_service_get_by_id(service, sample_repo):
    """Service get_by_id returns a skill dict with id and errors."""
    service.discover_and_index(str(sample_repo))

    # Get the ID from the list response
    listed = service.list(limit=1, offset=0)
    skill_id = listed["skills"][0]["id"]
    assert skill_id is not None

    skill = service.get_by_id(skill_id)
    assert skill is not None
    assert skill["path"] is not None
    assert "errors" in skill


def test_service_get_by_id_not_found(service):
    """Service returns None for unknown ID."""
    assert service.get_by_id(99999) is None


def test_service_clear_all(service, sample_repo):
    """Service clears all indexed skills."""
    service.discover_and_index(str(sample_repo))
    deleted = service.clear()
    assert deleted == 2

    # Verify cleared
    result = service.list()
    assert result["total"] == 0