"""Content-level validators for SKILL.md files.

While :func:`app.core.engine.validate_skill` checks structural correctness
(frontmatter present, required fields, type checks), this module inspects
the *body* of a skill document to assess its completeness and quality.

The completeness score is a deterministic, offline metric: 0-100 based on
which standard sections a skill includes. This is used as a lightweight
quality signal — not as a pass/fail gate — to help users identify skills
that may need more documentation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Section headers commonly found in agent skills, in order of importance.
# These are derived from the open-standard agent skills specification and
# the patterns used in the reference android/skills repository.
REQUIRED_SECTIONS: list[tuple[str, int]] = [
    ("Prerequisites", 25),
    ("Usage", 25),
    ("Installation", 15),
    ("Examples", 15),
    ("Troubleshooting", 10),
    ("References", 10),
]

# Regex to find markdown headers (h1-h4)
_HEADER_RE = re.compile(r"^#{1,4}\s+(.+?)\s*#*\s*$", re.MULTILINE)


@dataclass
class ValidationReport:
    """Report on the content quality of a SKILL.md body."""

    score: int
    found_sections: list[str] = field(default_factory=list)
    missing_sections: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    word_count: int = 0


def validate_content(body: str) -> ValidationReport:
    """Validate the body content of a SKILL.md file.

    Computes a completeness score based on which standard sections are
    present, and provides recommendations for improvement.

    Args:
        body: The body text of the SKILL.md file (after frontmatter).

    Returns:
        A :class:`ValidationReport` with score, found/missing sections,
        and recommendations.
    """
    headers = [m.group(1).strip() for m in _HEADER_RE.finditer(body)]
    header_lower = {h.lower() for h in headers}

    found: list[str] = []
    missing: list[str] = []
    score = 0

    for section, weight in REQUIRED_SECTIONS:
        if section.lower() in header_lower:
            found.append(section)
            score += weight
        else:
            missing.append(section)

    recommendations = _build_recommendations(missing, score)

    word_count = len(body.split())

    return ValidationReport(
        score=min(score, 100),
        found_sections=found,
        missing_sections=missing,
        recommendations=recommendations,
        word_count=word_count,
    )


def _build_recommendations(missing: list[str], score: int) -> list[str]:
    """Generate human-readable recommendations based on missing sections."""
    recs: list[str] = []

    if "Prerequisites" in missing:
        recs.append(
            "Add a 'Prerequisites' section listing what the user needs before "
            "using this skill (e.g., SDK versions, installed tools)."
        )

    if "Usage" in missing:
        recs.append(
            "Add a 'Usage' section with examples of how to invoke this skill."
        )

    if "Installation" in missing:
        recs.append(
            "Add an 'Installation' section with instructions. Per the "
            "Prerequisites pattern, inform the user rather than instructing "
            "the agent to auto-install system tools."
        )

    if "Examples" in missing and score > 25:
        recs.append(
            "Include concrete examples showing the skill in action."
        )

    if "Troubleshooting" in missing and score < 50:
        recs.append(
            "Consider adding a 'Troubleshooting' section for common issues."
        )

    if score < 50:
        recs.append(
            "This skill's completeness score is below 50. Consider adding "
            "missing sections to improve discoverability and usability."
        )

    return recs


def lint_skill(content: str) -> list[str]:
    """Run lightweight linting checks on a SKILL.md file's full content.

    Returns a list of lint messages (empty if no issues found). Unlike
    :func:`validate_content`, this checks for common authoring mistakes
    rather than section completeness.

    Checks:
        - Frontmatter delimiter alignment
        - Title (h1) presence and uniqueness
        - Excessive blank lines
        - Link format (http/https URLs)
    """
    issues: list[str] = []

    if not content.startswith("---"):
        issues.append("File does not start with YAML frontmatter delimiter")
        return issues  # Can't do further frontmatter checks

    # Check for h1 title
    body_start = content.find("\n---\n")
    if body_start == -1:
        issues.append("Could not locate body section after frontmatter")
        body = content
    else:
        body = content[body_start + 5:]  # skip \n---\n

    h1_headers = re.findall(r"^#\s+(.+)", body, re.MULTILINE)
    if len(h1_headers) == 0:
        issues.append("No h1 title found in body")
    elif len(h1_headers) > 1:
        issues.append("Multiple h1 titles found — use a single h1 title")

    # Check for excessive consecutive blank lines (3+)
    if re.search(r"\n{4,}", body):
        issues.append("Excessive blank lines (3 or more consecutive)")

    # Check for bare URLs (should use markdown link syntax)
    bare_urls = re.findall(r"(?<!\]\()https?://\S+", body)
    if bare_urls:
        issues.append(
            f"Found {len(bare_urls)} bare URL(s) — use markdown link syntax "
            "[text](url) instead"
        )

    return issues