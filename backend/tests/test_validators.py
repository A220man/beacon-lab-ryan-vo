"""Tests for the content-level skill validators."""
from app.core.validators import (
    validate_content,
    lint_skill,
    ValidationReport,
    REQUIRED_SECTIONS,
)


COMPLETE_BODY = """# Complete Skill

A comprehensive example skill document.

## Prerequisites

- Android Studio
- Android CLI 1.0+

## Usage

Run the skill like this:

```android docs search "MediaCodec"```

## Installation

Install via Android CLI.

## Examples

Example 1: Basic search.

## Troubleshooting

Common issues and fixes.

## References

- https://developer.android.com/docs
"""

PARTIAL_BODY = """# Partial Skill

A skill with fewer sections.

## Usage

Run the skill.
"""

MINIMAL_BODY = """# Minimal Skill

No standard sections here.
"""

NO_H1_BODY = """## No H1 Title

This skill has no h1 heading.
"""


# --- validate_content tests ---

def test_validate_content_complete_skill():
    """A body with all required sections scores 100."""
    report = validate_content(COMPLETE_BODY)
    assert report.score == 100
    assert "Prerequisites" in report.found_sections
    assert "Usage" in report.found_sections
    assert "Installation" in report.found_sections
    assert report.missing_sections == []


def test_validate_content_partial_skill():
    """A body missing sections scores lower."""
    report = validate_content(PARTIAL_BODY)
    assert report.score < 100
    assert "Prerequisites" in report.missing_sections
    assert "Usage" in report.found_sections
    assert len(report.recommendations) > 0


def test_validate_content_no_sections():
    """A body with no recognized sections scores 0."""
    report = validate_content(MINIMAL_BODY)
    assert report.score == 0
    assert len(report.missing_sections) == 6
    assert len(report.recommendations) > 0


def test_validate_content_word_count():
    """Word count is computed correctly."""
    report = validate_content(COMPLETE_BODY)
    assert report.word_count > 0


def test_validate_content_score_caps_at_100():
    """Score never exceeds 100."""
    # Create a body with all sections plus extras
    body = COMPLETE_BODY + "\n## Extra Section\n\nMore content.\n"
    report = validate_content(body)
    assert report.score == 100


# --- lint_skill tests ---

def test_lint_skill_no_frontmatter():
    """File without frontmatter delimiter is flagged."""
    issues = lint_skill("# No Frontmatter\n\nBody text here.\n")
    assert len(issues) >= 1
    assert any("frontmatter" in i.lower() for i in issues)


def test_lint_skill_bare_url():
    """Bare URLs are flagged for markdown link syntax."""
    content = "---\nname: test\ndescription: test\n---\n\nSee https://example.com for info.\n"
    issues = lint_skill(content)
    assert any("bare url" in i.lower() for i in issues)


def test_lint_skill_multiple_h1():
    """Multiple h1 headings are flagged."""
    content = "---\nname: test\ndescription: test\n---\n\n# First Title\n\n# Second Title\n\nContent here.\n"
    issues = lint_skill(content)
    assert any("h1" in i.lower() for i in issues)


def test_lint_skill_excessive_blanks():
    """Excessive blank lines are flagged."""
    content = "---\nname: test\ndescription: test\n---\n\n# Title\n\n\n\n\nContent.\n"
    issues = lint_skill(content)
    assert any("blank" in i.lower() for i in issues)


def test_lint_skill_clean_file():
    """A well-formed file produces no lint issues."""
    content = (
        "---\nname: clean-skill\ndescription: A clean skill\n---\n\n"
        "# Clean Skill\n\n"
        "This is a well-formed skill with proper formatting.\n\n"
        "## Usage\n\nRun it.\n"
    )
    issues = lint_skill(content)
    assert issues == []


def test_lint_skill_no_title():
    """Missing h1 title is flagged."""
    content = "---\nname: test\ndescription: test\n---\n\nNo h1 here.\n"
    issues = lint_skill(content)
    assert any("h1" in i.lower() for i in issues)