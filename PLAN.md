# Product development plan

Each round completes one feature or repair. Future items are planned, not implemented claims.

## Current round

skill-discovery

## Roadmap

### skill-discovery — Skill Discovery Engine

Status: in_progress

Acceptance:
- Backend recursively walks an arbitrary directory tree and finds all SKILL.md files
- Each SKILL.md is parsed for YAML frontmatter (name, description) and validated
- Topic and scope are derived from directory structure (e.g. performance/r8-analyzer/SKILL.md)
- Discovery results are persisted in SQLite with UTC timestamps
- POST /api/v1/skills/discover returns a full DiscoveryReport with valid/invalid breakdown
- GET /api/v1/skills/search returns paginated results from the index
- Frontend dashboard lets a user enter a path, run discovery, and search results
- At least 12 backend tests and 3 frontend tests pass

Implementation: `backend/app/core/engine.py`, `backend/app/core/models.py`, `backend/app/api/skills.py`, `backend/app/db/database.py`, `backend/app/main.py`, `frontend/src/api/client.ts`, `frontend/src/components/SkillDashboard.tsx`, `frontend/src/components/SkillTable.tsx`

Tests: `backend/tests/test_engine.py`, `backend/tests/test_api.py`, `frontend/tests/dashboard.test.tsx`

### oidc-auth — OIDC Authentication via Keycloak

Status: planned

Acceptance:
- SPA PKCE login flow with state + nonce + PKCE
- Token validation against issuer/audience
- Role-based authorization (viewer/analyst/admin) on all endpoints
- Logout endpoint with session cleanup
- Unauthenticated and role-denial tests pass

### llm-providers — LLM Provider Adapters

Status: planned

Acceptance:
- OpenAI-compatible adapter (httpx)
- Anthropic messages adapter
- Gemini generateContent adapter
- LLM_API_KEY only credential; provider/model/base_url configurable
- Bounded timeouts and redacted errors
- Network calls mocked in CI

### docs-search — WSL-Safe Documentation Search

Status: planned

Acceptance:
- Lucene-independent search that works without mmap
- Graceful degradation on platforms without mincore
- Cross-platform full-text search of skill content

### skill-linter — Advanced Skill Linter

Status: planned

Acceptance:
- Completeness score based on required sections
- Lint rules for common skill authoring mistakes
- Export lint report as JSON

