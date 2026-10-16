"""Unit tests for the skill discovery and validation engine.

Covers: topic/scope derivation, frontmatter parsing, skill validation,
recursive discovery, and offline search — all deterministic, no network.
"""
from __future__ import annotations

import pathlib

import pytest

from app.core.engine import (
    SkillRecord,
    DiscoveryReport,
    derive_topic,
    derive_scope,
    discover_skills,
    parse_frontmatter,
    search_skills,
    validate_skill,
    SKILL_FILENAME,
)
from backend.tests.conftest import VALID_SKILL_R8


# --- Topic derivation --------------------------------------------------------

def test_derive_topic_plain_path():
    """Topic is derived from the immediate parent directory."""
    assert derive_topic("performance/r8-analyzer/SKILL.md") == "performance"


def test_derive_topic_with_skills_prefix():
    """Topic skips the skills/{scope}/ prefix pattern."""
    assert derive_topic("skills/android/devtools/SKILL.md") == "devtools"
    assert derive_topic("skills/gemini/appfunctions/SKILL.md") == "appfunctions"


def test_derive_topic_top_level():
    """Top-level SKILL.md has no topic."""
    assert derive_topic("SKILL.md") is None

def test_derive_topic_nested_deep():
    """For deeply nested skills without 'skills/' prefix, topic is first directory."""
    assert derive_topic("a/b/c/d/e/SKILL.md") == "a"


def test_derive_topic_skills_with_scope_only():
    """skills/{scope}/SKILL.md has no topic (scope is the skill)."""
    assert derive_topic("skills/android/SKILL.md") is None


# --- Scope derivation --------------------------------------------------------

def test_derive_scope_with_skills_prefix():
    """Scope is the directory after 'skills'."""
    assert derive_scope("skills/android/devtools/SKILL.md") == "android"
    assert derive_scope("skills/gemini/appfunctions/SKILL.md") == "gemini"


def test_derive_scope_no_prefix():
    """No scope when 'skills' directory is not in the path."""
    assert derive_scope("performance/r8-analyzer/SKILL.md") is None
    assert derive_scope("SKILL.md") is None


def test_derive_scope_skills_with_scope_only():
    """skills/{scope}/SKILL.md → scope is {scope}."""
    assert derive_scope("skills/android/SKILL.md") == "android"


# --- Frontmatter parsing -----------------------------------------------------

def test_parse_frontmatter_valid():
    """Valid frontmatter is parsed into a dict with body text."""
    content = "---\nname: test-skill\ndescription: A test skill\n---\n\n# Body\n\nContent here.\n"
    fm, body, errors = parse_frontmatter(content)
    assert errors == []
    assert fm == {"name": "test-skill", "description": "A test skill"}
    assert "# Body" in body


def test_parse_frontmatter_missing_delimiter():
    """File without leading --- returns an error."""
    content = "# Just a skill\n\nNo frontmatter.\n"
    fm, body, errors = parse_frontmatter(content)
    assert fm is None
    assert len(errors) == 1
    assert "opening delimiter" in errors[0]


def test_parse_frontmatter_missing_closing():
    """File with opening but no closing --- returns an error."""
    content = "---\nname: test\ndescription: test\n# No closing delimiter\n"
    fm, body, errors = parse_frontmatter(content)
    assert fm is None
    assert len(errors) == 1
    assert "Closing" in errors[0]


def test_parse_frontmatter_malformed_yaml():
    """Invalid YAML syntax in frontmatter returns parse errors."""
    content = "---\nname: test\ndescription: Test\nitems: [unclosed\n---\n\nBody content here that is long enough.\n"
    fm, body, errors = parse_frontmatter(content)
    assert fm is None
    assert len(errors) >= 1
    assert any("YAML" in e or "parse" in e.lower() for e in errors)


def test_parse_frontmatter_null_value():
    """Frontmatter field with explicit null value is handled."""
    content = "---\nname: test\ndescription: null\n---\n\nBody content here that is long enough.\n"
    fm, body, errors = parse_frontmatter(content)
    assert errors == []
    assert fm is not None
    assert fm["name"] == "test"
    assert fm["description"] is None


# --- Skill validation --------------------------------------------------------

def test_validate_skill_valid():
    """A well-formed SKILL.md passes validation."""
    content = "---\nname: good-skill\ndescription: A well-formed skill\n---\n\n# Good Skill\n\nThis is a valid skill file with sufficient content.\n"
    errors, fm, body = validate_skill(content)
    assert errors == []
    assert fm is not None
    assert fm["name"] == "good-skill"
    assert "# Good Skill" in body


def test_validate_skill_missing_name():
    """Missing name field produces a validation error."""
    content = "---\ndescription: No name here\n---\n\nBody content with enough text to pass.\n"
    errors, fm, body = validate_skill(content)
    assert any("'name'" in e for e in errors)


def test_validate_skill_missing_description():
    """Missing description field produces a validation error."""
    content = "---\nname: no-desc\n---\n\nBody content with enough text to pass.\n"
    errors, fm, body = validate_skill(content)
    assert any("'description'" in e for e in errors)


def test_validate_skill_no_frontmatter():
    """No frontmatter at all produces validation errors."""
    content = "# Broken Skill\n\nThis file has no frontmatter delimiters.\n"
    errors, fm, body = validate_skill(content)
    assert len(errors) >= 2  # missing delimiter + missing fields
    assert fm is None


def test_validate_skill_too_small():
    """File smaller than minimum size produces a size error."""
    content = "tiny"
    errors, fm, body = validate_skill(content)
    assert any("too small" in e.lower() for e in errors)


def test_validate_skill_wrong_type_name():
    """Non-string name field produces a type error."""
    content = "---\nname: 12345\ndescription: Desc\n---\n\nBody content with enough text to pass.\n"
    # name: 12345 parses as integer in YAML
    errors, fm, body = validate_skill(content)
    assert any("must be" in e and "name" in e for e in errors)


# --- Discovery ----------------------------------------------------------------

def test_discover_skills_finds_nested_skills(sample_repo: pathlib.Path):
    """Discovery finds SKILL.md files at any depth, not just skills/ dir."""
    report = discover_skills(str(sample_repo))
    assert report.total_found == 6
    assert report.total_valid == 3
    assert report.total_invalid == 3
    assert len(report.skills) == 6
    # Valid skills should include nested paths
    paths = [s.path for s in report.skills]
    assert "performance/r8-analyzer/SKILL.md" in paths
    assert "devtools/android-cli/SKILL.md" in paths
    assert "skills/android/devtools/SKILL.md" in paths


def test_discover_skills_topic_derivation(sample_repo: pathlib.Path):
    """Topics are correctly derived from directory structure."""
    report = discover_skills(str(sample_repo))
    skills_by_path = {s.path: s for s in report.skills}
    assert skills_by_path["performance/r8-analyzer/SKILL.md"].topic == "performance"
    assert skills_by_path["devtools/android-cli/SKILL.md"].topic == "devtools"
    assert skills_by_path["skills/android/devtools/SKILL.md"].topic == "devtools"
    assert skills_by_path["skills/android/devtools/SKILL.md"].scope == "android"


def test_discover_skills_nonexistent_path():
    """Nonexistent path returns an error report with no skills."""
    report = discover_skills("/nonexistent/path/that/does/not/exist")
    assert report.total_found == 0
    assert len(report.errors) == 1
    assert "does not exist" in report.errors[0]


def test_discover_skills_non_directory(tmp_path: pathlib.Path):
    """A file path (not directory) returns an error report."""
    f = tmp_path / "file.txt"
    f.write_text("not a directory")
    report = discover_skills(str(f))
    assert report.total_found == 0
    assert len(report.errors) == 1
    assert "not a directory" in report.errors[0]


def test_discover_skills_empty_repo(empty_repo: pathlib.Path):
    """An empty repo with no SKILL.md returns zero results."""
    report = discover_skills(str(empty_repo))
    assert report.total_found == 0
    assert report.total_valid == 0
    assert report.errors == []


def test_discover_skills_sorting(sample_repo: pathlib.Path):
    """Discovery results are sorted by topic then name."""
    report = discover_skills(str(sample_repo))
    # Verify sorting: devtools skills come before performance skills
    topics = [s.topic or "" for s in report.skills]
    assert topics == sorted(topics)


def test_discover_skills_timestamp_present(sample_repo: pathlib.Path):
    """Each record has a UTC timestamp."""
    report = discover_skills(str(sample_repo))
    for skill in report.skills:
        assert skill.discovered_at
        assert skill.discovered_at.endswith("Z")  # UTC


# --- Search -------------------------------------------------------------------

def test_search_skills_by_name(sample_repo: pathlib.Path):
    """Search finds skills matching the query in name, description, topic, or path."""
    report = discover_skills(str(sample_repo))
    results, total = search_skills(report.skills, "r8")
    assert total >= 1
    assert any("r8" in (s.name or "").lower() for s in results)


def test_search_skills_by_topic(sample_repo: pathlib.Path):
    """Search matches by topic."""
    report = discover_skills(str(sample_repo))
    results, total = search_skills(report.skills, "performance")
    assert total == 1
    assert results[0].topic == "performance"


def test_search_skills_by_description(sample_repo: pathlib.Path):
    """Search matches by description."""
    report = discover_skills(str(sample_repo))
    results, total = search_skills(report.skills, "android")
    assert total >= 1
    assert any("android" in (s.description or "").lower() for s in results)


def test_search_skills_empty_query(sample_repo: pathlib.Path):
    """Empty query returns all records."""
    report = discover_skills(str(sample_repo))
    results, total = search_skills(report.skills, "")
    assert total == report.total_found
    assert len(results) == report.total_found


def test_search_skills_no_match(sample_repo: pathlib.Path):
    """Query with no matches returns empty results."""
    report = discover_skills(str(sample_repo))
    results, total = search_skills(report.skills, "nonexistent-skill-name-12345")
    assert total == 0
    assert len(results) == 0


def test_search_skills_pagination(sample_repo: pathlib.Path):
    """Search respects limit and offset for pagination."""
    report = discover_skills(str(sample_repo))
    all_results, all_total = search_skills(report.skills, "")
    assert all_total == len(report.skills)

    # Paginate with limit=2
    page1, _ = search_skills(report.skills, "", limit=2, offset=0)
    assert len(page1) == 2
    page2, _ = search_skills(report.skills, "", limit=2, offset=2)
    assert len(page2) == min(2, all_total - 2)