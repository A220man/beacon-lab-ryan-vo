"""Pydantic models for the Beacon Lab API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SkillRecord(BaseModel):
    """A discovered and validated skill record."""
    model_config = {"from_attributes": True}

    id: int | None = None
    path: str = Field(..., description="Path to SKILL.md relative to discovery root")
    name: str | None = Field(default=None, description="Skill name from frontmatter")
    description: str | None = Field(default=None, description="Skill description from frontmatter")
    topic: str | None = Field(default=None, description="Topic derived from parent directory")
    scope: str | None = Field(default=None, description="Scope derived from skills/{scope}/ pattern")
    valid: bool = Field(..., description="Whether the skill passed validation")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    content_length: int = Field(..., description="Total bytes of the SKILL.md file")
    discovered_at: str = Field(..., description="UTC timestamp of discovery")
    root_path: str | None = None


class DiscoveryReport(BaseModel):
    """Result of a discovery run."""
    skills: list[SkillRecord] = Field(..., description="Discovered skills, sorted by topic then name")
    total_found: int = Field(..., description="Total SKILL.md files found")
    total_valid: int = Field(..., description="Valid skills passing validation")
    total_invalid: int = Field(..., description="Invalid skills with errors")
    root_path: str = Field(..., description="Directory that was searched")
    errors: list[str] = Field(default_factory=list, description="Filesystem-level errors")
    discovered_at: str = Field(..., description="UTC timestamp of discovery")


class DiscoveryRequest(BaseModel):
    """Request to discover skills in a directory."""
    model_config = {"extra": "forbid"}
    repository_path: str = Field(..., min_length=1, description="Directory path to scan recursively")


class DiscoverResponse(BaseModel):
    """Response from discovery API."""
    report: DiscoveryReport


class SearchResult(BaseModel):
    """A search result item."""
    model_config = {"from_attributes": True}

    id: int
    path: str
    name: str | None
    description: str | None
    topic: str | None
    scope: str | None
    valid: bool
    errors: list[str] = Field(default_factory=list)
    content_length: int
    discovered_at: str


class SearchResponse(BaseModel):
    """Search results with pagination."""
    skills: list[SearchResult]
    total: int
    limit: int
    offset: int
    query: str