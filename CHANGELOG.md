# Changelog

## 1.0.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

All notable changes to Beacon Lab are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] — 2026-10-16

### Added
- Skill Discovery Engine: recursively walks directory trees to find all `SKILL.md` files, parses YAML frontmatter, validates structure, and derives topic/scope from directory layout
- SQLite persistence layer for discovered skills with UTC timestamps, pagination, and full-text search
- REST API: `POST /api/v1/skills/discover`, `GET /api/v1/skills/search`, `GET /api/v1/skills/list`, `GET /api/v1/skills/{id}`, `DELETE /api/v1/skills/clear`
- React + TypeScript frontend dashboard with discovery form, searchable sortable skill table, and loading/error/empty states
- Backend test suite: engine unit tests (validation, topic derivation, discovery), API integration tests (HTTP boundary), persistence tests
- Frontend test suite: component behavior tests for dashboard and search
- SkillService layer: business logic separation wrapping discovery engine + SQLite persistence
- Content validators: completeness scoring (0-100) and authoring lint (bare URLs, h1 title, blank lines)
- Dockerfile for backend (nonroot) and frontend (nonroot)
- docker-compose.yaml with backend, frontend, and Keycloak services (Keycloak not yet wired)
- CI workflow: pytest backend, npm frontend build/test, Docker builds
- .env.example with blank credentials
- Architecture diagram and API documentation in README
- AI/ML evaluation section with labeled dataset and metrics

### Known Limitations
- No authentication (OIDC/Keycloak integration is planned)
- No LLM provider adapters (planned)
- No WSL-safe documentation search engine (the discovery engine uses simple file I/O, not mmap)
- No advanced skill linter (planned)