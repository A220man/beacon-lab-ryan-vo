# Architecture Documentation

## Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                     │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Dashboard │  │ Skill Table │  │ Discovery Form   │  │
│  │  App.tsx  │  │ SkillTable   │  │                   │  │
│  └──────────┘  └──────────────┘  └──────────────────┘  │
│         │                                               │
│         ▼ api/client.ts (typed HTTP)                    │
└─────────────────────────────────────────────────────────┘
           │ HTTP /api/v1/skills
           ▼
┌─────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                    │
│                                                         │
│  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │  api/skills.py   │  │   services/skill_service  │  │
│  │  (router)        │──│   (business logic)        │  │
│  └──────────────────┘  └──────────────────────────┘  │
│                                      │                 │
│         ┌────────────────────────────┼─────────┐       │
│         ▼                            ▼         ▼       │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────┐ │
│  │ core/        │  │ db/database.py   │  │ core/    │ │
│  │ engine.py    │  │ (SQLite + FTS)  │  │ validators│ │
│  │ (discovery)  │  │                  │  │ .py      │ │
│  └──────────────┘  └──────────────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────┘
           │                    │              │
           ▼                    ▼              ▼
┌──────────────────┐  ┌─────────────────┐  ┌──────────┐
│  Filesystem      │  │ SQLite DB file  │  │ lint_skill│
│  (SKILL.md)      │  │ (WAL mode)      │  │  checks  │
└──────────────────┘  └─────────────────┘  └──────────┘
```

## Design Principles

1. **Thin API layer**: `skills.py` contains only HTTP boundary logic
   — serialization, status codes, query parameters. All business logic
   lives in `SkillService`.

2. **Service encapsulation**: `SkillService` wraps the discovery engine
   and database layer. It opens its own connections per call, allowing
   SQLite WAL mode for concurrent read access.

3. **Separation of concerns**:
   - Discovery engine (`core/engine.py`): filesystem I/O, frontmatter
     parsing, structural validation, topic/scope derivation.
   - Content validators (`core/validators.py`): completeness scoring
     and authoring lint (not pass/fail gates).
   - Persistence (`db/database.py`): schema, migrations, queries.
   - Service (`services/skill_service.py`): orchestration layer.

4. **Pydantic models** (`core/models.py`) are the API contract — dataclasses
   are never leaked across the HTTP boundary.

## Data Flow

### Discovery
1. Client → `POST /discover` with `{"repository_path": "..."}`
2. API route → `SkillService.discover_and_index()`
3. Service → `discover_skills(path)` (engine)
4. Engine → walks directories, finds `SKILL.md`, parses frontmatter,
   validates structure, derives topic/scope
5. Service → `database.save_discovery(conn, report)` (persists to SQLite)
6. Service → returns report dict
7. API → serializes to `DiscoveryReport` Pydantic model
8. Client ← JSON response

### Search
1. Client → `GET /search?q=...`
2. API route → `database.search_indexed_skills(conn, query, ...)`
3. API → serializes results to `SearchResponse`
4. Client ← JSON response

## Database Schema

| Table | Columns | Description |
|---|---|---|
| `discovery_runs` | `id`, `root_path`, `started_at`, `total_found`, `total_valid`, `total_invalid`, `errors` | One row per discovery run |
| `skills` | `id`, `run_id`, `path`, `name`, `description`, `topic`, `scope`, `valid`, `errors`, `content_length`, `discovered_at`, `root_path` | One row per discovered skill |

All timestamps are UTC ISO 8601 strings. The `errors` column is stored
as JSON.

## Deployment

- Backend: `Dockerfile` uses `python:3.12-slim` base, nonroot user.
- Frontend: `Dockerfile` uses multi-stage build (node → nginx).
- Compose: backend + frontend + Keycloak (Keycloak not yet wired).
- CI: GitHub Actions runs pytest, frontend build/test, Docker builds.