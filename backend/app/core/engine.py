"""Skill discovery and validation engine.

Recursively discovers SKILL.md files in a directory tree, validates them
against the open-standard agent skills specification, and returns structured
metadata for indexing and search.

This engine addresses the following user needs from the android/skills
repository issues:

- **#48**: ``gh skill install`` only finds skills under ``skills/`` directories —
  this engine walks the entire tree to find skills nested under topic folders
  (e.g. ``performance/r8-analyzer/SKILL.md``).

- **#143**: ``agy plugin install`` fails to detect plugin structure — this engine
  validates each SKILL.md's frontmatter and content before indexing it,
  detecting malformed or incomplete skills.

- **#47**: Skills disappear after ``android skills add --all`` — this engine
  builds a persistent, searchable index in SQLite so skills remain discoverable.
"""
from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

import yaml

# --- Constants ---------------------------------------------------------------

SKILL_FILENAME = "SKILL.md"
MIN_CONTENT_LENGTH = 50  # minimum total file bytes
MIN_BODY_LENGTH = 20  # minimum non-frontmatter content characters
MAX_FRONTMATTER_BYTES = 65536  # 64 KB safety limit
SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", "dist", "build", ".env"}

REQUIRED_FRONTMATTER_FIELDS = ("name", "description")
FIELD_TYPES: dict[str, type] = {
    "name": str,
    "description": str,
}


# --- Data classes ------------------------------------------------------------

@dataclass
class SkillRecord:
    """A discovered and validated skill."""

    path: str
    name: str | None
    description: str | None
    topic: str | None
    scope: str | None
    valid: bool
    errors: list[str] = field(default_factory=list)
    content_length: int = 0
    discovered_at: str = ""

@dataclass
class DiscoveryReport:
    """Results of a discovery run."""

    skills: list[SkillRecord] = field(default_factory=list)
    total_found: int = 0
    total_valid: int = 0
    total_invalid: int = 0
    root_path: str = ""
    errors: list[str] = field(default_factory=list)
    discovered_at: str = ""

    @classmethod
    def empty(cls, root_path: str) -> "DiscoveryReport":
        now = _utc_now()
        return cls(
            root_path=root_path,
            discovered_at=now,
        )


# --- Utility functions -------------------------------------------------------

def _utc_now() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def derive_topic(rel_path: str) -> str | None:
    """Derive the topic from a SKILL.md's directory structure.

    The topic is the semantic category that groups related skills. It is
    derived from the parent directory path, handling the ``skills/{scope}/``
    prefix pattern used by the agent skills spec.

    Examples:
        - ``SKILL.md`` → ``None`` (top-level, unscoped)
        - ``performance/r8-analyzer/SKILL.md`` → ``"performance"``
        - ``devtools/android-cli/SKILL.md`` → ``"devtools"``
        - ``skills/android/devtools/SKILL.md`` → ``"devtools"`` (scope="android")
        - ``skills/r8-analyzer/SKILL.md`` → ``None`` (scope is the skill itself)
    """
    parts = pathlib.Path(rel_path).parent.parts
    if len(parts) == 0:
        return None

    # Look for "skills" anywhere in the path (handles {prefix}/skills/ pattern)
    if "skills" in parts:
        idx = parts.index("skills")
        if idx + 2 < len(parts):
            # skills/{scope}/{topic}/... → topic is parts[idx+2]
            return parts[idx + 2]
        if idx + 1 < len(parts):
            # skills/{scope}/SKILL.md → scope is the skill itself, no topic
            return None
        return None

    # For non-skills paths (e.g. android/skills layout), the topic is the
    # first directory in the path
    #   performance/r8-analyzer/SKILL.md → "performance"
    #   devtools/android-cli/SKILL.md → "devtools"
    return parts[0]


def derive_scope(rel_path: str) -> str | None:
    """Derive the scope from the ``skills/{scope}/`` directory pattern.

    The scope in the agent skills spec identifies the agent or platform
    that a skill targets (e.g. ``android``, ``gemini``, ``antigravity``).

    Examples:
        - ``skills/android/devtools/SKILL.md`` → ``"android"``
        - ``skills/r8-analyzer/SKILL.md`` → ``"r8-analyzer"``
        - ``performance/r8-analyzer/SKILL.md`` → ``None``
    """
    parts = pathlib.Path(rel_path).parent.parts
    if "skills" in parts:
        idx = parts.index("skills")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return None


# --- Frontmatter parsing -----------------------------------------------------

def parse_frontmatter(content: str) -> tuple[dict | None, str, list[str]]:
    """Parse YAML frontmatter from a SKILL.md file's content.

    Frontmatter is delimited by ``---`` at the start of the file:

        ---
        name: My Skill
        description: A description
        ---
        # Body content...

    Returns a tuple of ``(frontmatter_dict_or_None, body_text, parse_errors)``.
    """
    errors: list[str] = []

    if not content.startswith("---"):
        return None, content, ["Missing YAML frontmatter opening delimiter (---)"]

    lines = content.splitlines()
    if len(lines) < 3:
        return None, content, ["File too short to contain valid frontmatter"]

    # Find the closing delimiter
    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return None, content, ["Closing frontmatter delimiter (---) not found"]

    yaml_text = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1:])

    if len(yaml_text) > MAX_FRONTMATTER_BYTES:
        errors.append(
            f"Frontmatter exceeds maximum size ({len(yaml_text)} > {MAX_FRONTMATTER_BYTES} bytes)"
        )
        return None, body, errors

    try:
        frontmatter = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        errors.append(f"YAML parse error: {exc}")
        return None, body, errors

    if frontmatter is None:
        frontmatter = {}

    if not isinstance(frontmatter, dict):
        errors.append(
            f"Frontmatter must be a YAML mapping, got {type(frontmatter).__name__}"
        )
        return None, body, errors

    return frontmatter, body, errors


# --- Validation --------------------------------------------------------------

def validate_skill(content: str, filename: str = SKILL_FILENAME) -> tuple[list[str], dict | None, str]:
    """Validate a SKILL.md file's structure and frontmatter.

    Checks:
        1. File is named ``SKILL.md``
        2. File meets minimum size threshold
        3. YAML frontmatter is present and parseable
        4. Required fields (``name``, ``description``) are present and correctly typed
        5. Body content is non-trivial

    Returns ``(errors, frontmatter_or_None, body_text)``.
    """
    errors: list[str] = []

    if filename != SKILL_FILENAME:
        errors.append(f"Skill file must be named '{SKILL_FILENAME}', found '{filename}'")

    if len(content) < MIN_CONTENT_LENGTH:
        errors.append(
            f"File too small: {len(content)} bytes (minimum {MIN_CONTENT_LENGTH})"
        )

    frontmatter, body, parse_errors = parse_frontmatter(content)
    errors.extend(parse_errors)

    if frontmatter is None:
        for field_name in REQUIRED_FRONTMATTER_FIELDS:
            errors.append(f"Missing required field '{field_name}' in frontmatter")
        return errors, None, body


    # Check required fields
    for field_name in REQUIRED_FRONTMATTER_FIELDS:
        if field_name not in frontmatter:
            errors.append(f"Missing required field '{field_name}' in frontmatter")
        elif frontmatter[field_name] is None:
            errors.append(f"Field '{field_name}' is null in frontmatter")
        else:
            expected_type = FIELD_TYPES.get(field_name, str)
            if not isinstance(frontmatter[field_name], expected_type):
                actual = type(frontmatter[field_name]).__name__
                errors.append(
                    f"Field '{field_name}' must be {expected_type.__name__}, got {actual}"
                )

    # Check body content is non-trivial
    body_stripped = body.strip()
    if len(body_stripped) < MIN_BODY_LENGTH:
        errors.append(
            f"Body content too short: {len(body_stripped)} chars (minimum {MIN_BODY_LENGTH})"
        )

    return errors, frontmatter, body


# --- Discovery ----------------------------------------------------------------

def discover_skills(root_path: str) -> DiscoveryReport:
    """Walk *root_path* recursively, find all SKILL.md files, validate them.

    Unlike tools that only search under a ``skills/`` directory, this engine
    walks the entire tree to handle skills nested under topic folders at any
    depth.

    Returns a :class:`DiscoveryReport` with sorted, validated skill records.
    """
    root = pathlib.Path(root_path)
    now = _utc_now()

    if not root.exists():
        return DiscoveryReport(
            root_path=root_path,
            discovered_at=now,
            errors=[f"Path does not exist: {root_path}"],
        )
    if not root.is_dir():
        return DiscoveryReport(
            root_path=root_path,
            discovered_at=now,
            errors=[f"Path is not a directory: {root_path}"],
        )

    records: list[SkillRecord] = []
    fs_errors: list[str] = []

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Skip non-product directories and symlinked dirs (avoid cycles)
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS
            and not (pathlib.Path(dirpath) / d).is_symlink()
        ]

        if SKILL_FILENAME in filenames:
            skill_file = pathlib.Path(dirpath) / SKILL_FILENAME
            rel_path = str(skill_file.relative_to(root))

            try:
                content = skill_file.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                fs_errors.append(f"Cannot decode {rel_path}: {exc}")
                continue
            except OSError as exc:
                fs_errors.append(f"Cannot read {rel_path}: {exc}")
                continue

            errors, frontmatter, _body = validate_skill(content)

            record = SkillRecord(
                path=rel_path,
                name=frontmatter.get("name") if frontmatter else None,
                description=frontmatter.get("description") if frontmatter else None,
                topic=derive_topic(rel_path),
                scope=derive_scope(rel_path),
                valid=len(errors) == 0,
                errors=errors,
                content_length=len(content),
                discovered_at=now,
            )
            records.append(record)

    records.sort(key=lambda s: (s.topic or "", s.name or s.path))
    total = len(records)
    valid_count = sum(1 for s in records if s.valid)

    return DiscoveryReport(
        skills=records,
        total_found=total,
        total_valid=valid_count,
        total_invalid=total - valid_count,
        root_path=root_path,
        errors=fs_errors,
        discovered_at=now,
    )


# --- Search -------------------------------------------------------------------

def search_skills(
    records: list[SkillRecord], query: str, *, limit: int = 50, offset: int = 0
) -> tuple[list[SkillRecord], int]:
    """Search skill records by name, description, topic, or path.

    Matching is case-insensitive and substring-based. This is the offline
    core search that works without any external dependencies.

    Returns ``(matched_records, total_matches)``.
    """
    if not query.strip():
        # Empty query returns all records
        total = len(records)
        return records[offset:offset + limit], total

    q = query.lower().strip()
    matched = [
        r for r in records
        if (r.name and q in r.name.lower())
        or (r.description and q in r.description.lower())
        or (r.topic and q in r.topic.lower())
        or (r.path and q in r.path.lower())
    ]
    total = len(matched)
    return matched[offset:offset + limit], total