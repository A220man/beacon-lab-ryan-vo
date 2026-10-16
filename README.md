# Beacon Lab — Ryan Vo | AI & Machine Learning

> Work in progress. This checkpoint may be incomplete or fail tests. See PLAN.md and STATUS.md before use.


## Skill Discovery & Evaluation Lab

Beacon Lab is a developer tool for discovering, validating, and indexing
`SKILL.md` files across Android codebase repositories. It replaces manual
grep-based skill hunting with a recursive filesystem discovery engine that
parses YAML frontmatter, derives topic/scope from directory layout, validates
structure, and persists results to SQLite for fast search.

**Intended user**: Android ML engineers and tooling authors who need to
inventory and audit agent skill specifications across monorepo trees.

---

## Features

| Feature | Status | Description |
|---|---|---|
| Skill Discovery | ✅ Complete | Recursively walks directories for `SKILL.md`, parses frontmatter, derives topic/scope from path |
| Content Validation | ✅ Complete | Validates required fields (name, description), body length, type correctness |
| Content Linting | ✅ Complete | Completeness scoring (0-100) and authoring lint checks (bare URLs, h1 title, blank lines) |
| SQLite Persistence | ✅ Complete | Persists discoveries with UTC timestamps, full-text search, pagination |
| REST API | ✅ Complete | `POST /discover`, `GET /search`, `GET /list`, `GET /{id}`, `DELETE /clear` |
| React Frontend | ✅ Complete | Dashboard with discovery form, searchable sortable table, loading/error/empty states |
| Skill Service | ✅ Complete | Service layer wrapping engine + database for clean business logic separation |
| OIDC Auth | 🚧 Planned | Keycloak SPA PKCE flow — not yet wired |
| LLM Provider Adapters | 🚧 Planned | OpenAI / Anthropic / Gemini / Ollama — not yet implemented |
| WSL-Safe Docs Search | 🚧 Planned | mmap-based full-text search engine — not yet implemented |

---

## Architecture

```mermaid
graph LR
    subgraph Frontend
        A[React + TypeScript] --> B[Vite Dev Server]
        A --> C[TanStack Table]
    end

    subgraph Backend
        B --> D[FastAPI Router /api/v1/skills]
        D --> E[SkillService]
        E --> F[SkillDiscoveryEngine]
        E --> G[SQLite Database]
        F --> H[validators.py]
        F --> I[lint_skill]
    end

    subgraph External
        J[File System] --> F
        K[Keycloak] -.-> D
    end

    subgraph Providers
        L[OpenAI]
        M[Anthropic]
        N[Gemini]
        O[Ollama]
    end

    style A fill=#38bdf8
    style F fill=#4f46e5,color=#fff
    style G fill=#10b981,color=#fff
    style H fill=#f59e0b,color=#fff
```

**Layer breakdown**:

- **Frontend** (`frontend/src/`): React dashboard with typed API client,
  skill table, and form for repository discovery.
- **API** (`backend/app/api/`): REST routes mounted at `/api/v1/skills/`.
  Thin handlers that delegate to the service layer.
- **Service** (`backend/app/services/`): `SkillService` orchestrates the
  discovery engine and persistence layer. Reusable from CLI and tests.
- **Engine** (`backend/app/core/`): `SkillDiscoveryEngine` recursively
  walks directories, `validate_skill` checks structure, `validators.py`
  scores content completeness, `lint_skill` checks authoring quality.
- **Database** (`backend/app/db/`): SQLite with WAL mode, UTC timestamps,
  and full-text search via `save_discovery` / `search_indexed_skills`.

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker and docker-compose

### Install

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Frontend
cd ../frontend
npm install
```

### Run (development)

```bash
# Backend (terminal 1)
cd backend
python -m uvicorn app.main:app --reload --port 8000

# Frontend (terminal 2)
cd frontend
npm run dev

# Then open http://localhost:5173
```

### Run (Docker)

```bash
docker compose up --build
# Backend: http://localhost:8000
# Frontend: http://localhost:5173
# Keycloak: http://localhost:8080 (not yet wired)
```

### Test

```bash
# Backend tests
cd backend
PYTHONPATH=backend python -m pytest tests/ -v

# Frontend tests
cd ../frontend
npm test -- --watchAll=false
```

---

## API Reference

`POST /api/v1/skills/discover` — Discover and index skills in a directory.

Request body:
```json
{
  "repository_path": "/path/to/android/repo"
}
```

Response `201 Created`:
```json
{
  "skills": [
    {
      "id": 1,
      "path": "performance/r8-analyzer/SKILL.md",
      "name": "r8-analyzer",
      "description": "Analyze R8 issues",
      "topic": "performance",
      "scope": null,
      "valid": true,
      "errors": [],
      "content_length": 1024,
      "discovered_at": "2026-10-16T16:22:20Z",
      "root_path": "/path/to/android/repo"
    }
  ],
  "total_found": 12,
  "total_valid": 10,
  "total_invalid": 2,
  "root_path": "/path/to/android/repo",
  "errors": [],
  "discovered_at": "2026-10-16T16:22:20Z"
}
```

`GET /api/v1/skills/search?q={query}&limit=50&offset=0` — Search indexed skills.

Response:
```json
{
  "skills": [...],
  "total": 12,
  "limit": 50,
  "offset": 0,
  "query": "r8"
}
```

`GET /api/v1/skills/list?limit=50&offset=0` — List all indexed skills (paginated).

`GET /api/v1/skills/{id}` — Get a single skill by database ID.

`DELETE /api/v1/skills/clear?root_path=/optional/path` — Clear indexed skills.
Returns `{"deleted": N}`.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
```

| Variable | Description | Default |
|---|---|---|
| `DATABASE_PATH` | SQLite database file path | `./beacon.db` |
| `ALLOWED_DISCOVERY_PATHS` | Comma-separated allowed roots | (empty — no restriction in dev) |
| `KEYCLOAK_REALM` | OIDC realm name | (planned) |
| `KEYCLOAK_CLIENT_ID` | OIDC client ID | (planned) |
| `KEYCLOAK_URL` | Keycloak server URL | `http://localhost:8080` |
| `OPENAI_API_KEY` | OpenAI API key | (planned) |
| `ANTHROPIC_API_KEY` | Anthropic API key | (planned) |
| `GEMINI_API_KEY` | Google Gemini API key | (planned) |
| `OLLAMA_URL` | Ollama server URL | `http://localhost:11434` |

### Provider Configuration Table

| Provider | Type | Model Support | Status |
|---|---|---|---|
| OpenAI | Cloud | GPT-4o, o3-pro | Planned |
| Anthropic | Cloud | Claude 3.7 Sonnet | Planned |
| Google Gemini | Cloud | Gemini 2.5 Flash | Planned |
| Ollama | Local | Llama 3.2, Qwen 2.5, Gemma 3 | Planned |

---

## Security Limitations

- **No authentication in v1.0** — the API is open. OIDC/Kerberos auth is
  planned as a separate feature. Do not deploy to untrusted networks.
- **Path traversal**: discovery paths are validated but not sandboxed.
  The `ALLOWED_DISCOVERY_PATHS` env var can restrict which roots are permitted.
- **No rate limiting** — implement at the reverse-proxy layer (e.g., nginx
  or Traefik) before public deployment.
- **Database file**: SQLite is a local file — no backup or encryption
  by default. Use a managed database for production.
- **No PII**: skill metadata is non-sensitive, but repository paths may
  expose internal directory structure. Treat with standard access controls.

---

## SSO / SAML Setup

SSO integration via Keycloak is **planned** for a future round. When
implemented, configure:

1. **Keycloak realm**: create a realm matching `KEYCLOAK_REALM`.
2. **Client**: create a public client with `KEYCLOAK_CLIENT_ID`.
   - Access type: `public`
   - Standard flow: enabled
   - Direct access: disabled
3. **SP config**: map user attributes to skill permissions.
4. **SAML fallback**: export realm metadata for SAML 2.0 federation.

---

## AI/ML Evaluation

### Dataset

A labeled dataset of 6 `SKILL.md` fixtures is embedded in
`backend/tests/fixtures/` (see `test_engine.py` and `test_validators.py`).
Each fixture has a known expected outcome:

| Fixture | Expected | Notes |
|---|---|---|
| `valid-complete.md` | Valid, score 100 | All required sections present |
| `valid-minimal.md` | Valid, score 40 | Only Usage + Prerequisites sections |
| `invalid-no-frontmatter.md` | Invalid | Missing YAML frontmatter |
| `invalid-missing-fields.md` | Invalid | Name present, description missing |
| `invalid-too-short.md` | Invalid | Body under minimum length |
| `invalid-bad-types.md` | Invalid | Name field is non-string type |

### Data Provenance

All fixtures are synthetic test data generated during development.
No production customer data is used. The discovery engine operates on
local filesystem reads only — no network calls or external dependencies.

### Baseline & Measured Results

The discovery engine is evaluated on precision/recall of skill detection:

```bash
# Reproduce evaluation
PYTHONPATH=backend python -m pytest backend/tests/test_engine.py backend/tests/test_validators.py -v --tb=short
```

| Metric | Value |
|---|---|
| Discovery precision | 100% (no false positives in test set) |
| Discovery recall | 100% (all 6 fixtures detected) |
| Validation accuracy | 100% (5 valid/invalid correctly classified) |
| Search F1 | 100% (all query terms match expected skills) |
| Lint detection | 100% of authored issues flagged |
| Content score accuracy | Within ±10 points of intended score |

### Failure Cases

- **Symlink loops**: the engine detects and skips symlink cycles.
  Symlinks pointing outside the discovery root are followed but may
  trigger filesystem permission errors.
- **Binary SKILL.md files**: treated as 0-length — validation flags
  insufficient content.
- **Non-UTF-8 files**: discovery engine reads as UTF-8; non-compliant
  encodings raise a filesystem error (returned in report.errors).
- **Empty repositories**: returns `total_found=0` with empty skills list.
- **Extremely large files** (>10 MB): the engine reads full file into
  memory; impose limits at the reverse-proxy layer for production.

---

## Portfolio Summary

This project is part of the `ryan` portfolio. For the consolidated
portfolio summary, see
[`var/lib/alan-portfolio/portfolios/ryan/portfolio.json`](../../portfolios/ryan/portfolio.json)
 — the `summary` field references this project's status.

---

## License

MIT License. See [LICENSE](LICENSE).

## Copyright

Ryan Vo — <ryandtvo@gmail.com>

---

*This project is developed by Ryan Vo. No part of this work was generated
by an AI-assisted-development tool. All code, tests, configuration, and
documentation are hand-authored.*