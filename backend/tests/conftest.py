"""Shared pytest fixtures for backend tests."""
from __future__ import annotations

import os
import pathlib
import tempfile

import pytest
from fastapi.testclient import TestClient

# Set a default test database path BEFORE importing app modules,
# so the module-level `app = create_app()` in main.py uses a temp path.
_TEST_DB_DIR = tempfile.mkdtemp(prefix="beacon_test_")
os.environ.setdefault(
    "DATABASE_PATH",
    os.path.join(_TEST_DB_DIR, "test_beacon.db"),
)


# --- Sample skill content helpers -------------------------------------------

VALID_SKILL_R8 = """---
name: r8-analyzer
description: Analyze R8 optimization issues and suggest fixes
version: 1.0.0
---

# R8 Analyzer

This skill helps developers analyze R8 optimization issues.

## Prerequisites

- Android project with R8 enabled

## Usage

Run the skill to analyze your build output.
"""

VALID_SKILL_ANDROID_CLI = """---
name: android-cli
description: Use the Android CLI tool for development tasks
version: 1.0.0
---

# Android CLI

This skill covers using the Android CLI tool for various development tasks.

## Prerequisites

- Android CLI installed and in PATH

## Usage

Invoke the android tool for common development tasks.
"""

VALID_SKILL_DEVTOOLS = """---
name: android-devtools
description: Android development tools and debugging techniques
---

# Android Devtools

Scoped skill under skills/android/devtools.
"""

INVALID_NO_DESCRIPTION = """---
name: top-level-skill
---

This skill has no description field.
"""

INVALID_NO_FRONTMATTER = """# Broken Skill

No frontmatter here. Just markdown content.
"""

INVALID_TINY = "tiny"

INVALID_YAML = """---
name: broken-yaml
description: This has invalid YAML
  : : :
---

Body content here that is long enough.
"""


# --- Fixtures ----------------------------------------------------------------

@pytest.fixture
def sample_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a sample repository with SKILL.md files at various depths.

    Layout mirrors the android/skills repo structure:
        - skills nested under topic folders (performance/r8-analyzer/)
        - skills with scope pattern (skills/android/devtools/)
        - top-level skill
        - broken skills (no frontmatter, tiny, malformed YAML)
    """
    repo = tmp_path / "sample_repo"
    repo.mkdir()

    # Valid skill: performance/r8-analyzer/SKILL.md
    d = repo / "performance" / "r8-analyzer"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(VALID_SKILL_R8)

    # Valid skill: devtools/android-cli/SKILL.md
    d = repo / "devtools" / "android-cli"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(VALID_SKILL_ANDROID_CLI)

    # Valid skill: skills/android/devtools/SKILL.md (with scope)
    d = repo / "skills" / "android" / "devtools"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(VALID_SKILL_DEVTOOLS)

    # Invalid: top-level SKILL.md (missing description)
    (repo / "SKILL.md").write_text(INVALID_NO_DESCRIPTION)

    # Invalid: broken/no-frontmatter/SKILL.md (no frontmatter)
    d = repo / "broken" / "no-frontmatter"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(INVALID_NO_FRONTMATTER)

    # Invalid: tiny/SKILL.md (too small)
    d = repo / "tiny"
    d.mkdir()
    (d / "SKILL.md").write_text(INVALID_TINY)

    return repo


@pytest.fixture
def empty_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create an empty repository with no SKILL.md files."""
    repo = tmp_path / "empty_repo"
    repo.mkdir()
    (repo / "some_file.txt").write_text("not a skill")
    (repo / "README.md").write_text("# README")
    return repo


@pytest.fixture
def temp_db_path(tmp_path: pathlib.Path) -> str:
    """Provide a temporary database path unique per test."""
    return str(tmp_path / "test_beacon.db")


@pytest.fixture
def client(temp_db_path: str, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Provide a FastAPI TestClient with an isolated database."""
    monkeypatch.setenv("DATABASE_PATH", temp_db_path)
    from app.main import create_app
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client