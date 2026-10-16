# API Documentation

## Overview

All endpoints are mounted under `/api/v1/skills/` and return JSON.
Error responses use HTTP status codes with a `detail` field.

## Base URL

```
http://localhost:8000/api/v1/skills
```

## Endpoints

### `GET /api/v1/skills/` — Health Check

Returns API status and version.

**Response `200 OK`**:
```json
{"status": "healthy", "version": "1.0.0"}
```

### `POST /api/v1/skills/discover` — Discover Skills

Recursively walks a directory tree to find all `SKILL.md` files, parses
their YAML frontmatter, validates structure, derives topic/scope from
directory layout, and persists results to SQLite.

**Request Body**:
```json
{
  "repository_path": "/path/to/repo"
}
```

Fields:
- `repository_path` (required, string, min 1 char) — directory to scan.
  Extra fields are rejected (`422 Unprocessable Entity`).

**Response `201 Created`**:
```json
{
  "skills": [...],
  "total_found": 12,
  "total_valid": 10,
  "total_invalid": 2,
  "root_path": "/path/to/repo",
  "errors": [],
  "discovered_at": "2026-10-16T16:22:20Z"
}
```

**Error `400 Bad Request`** — filesystem-level error (path doesn't exist):
```json
{"detail": "Discovery path does not exist: /nonexistent/path"}
```

### `GET /api/v1/skills/search` — Search Skills

Search indexed skills by name, description, topic, or path.

**Query Parameters**:
- `q` (string, default `""`) — search query.
- `limit` (int, default 50, range 1–500) — max results.
- `offset` (int, default 0, min 0) — pagination offset.

**Response `200 OK`**:
```json
{
  "skills": [...],
  "total": 12,
  "limit": 50,
  "offset": 0,
  "query": "r8"
}
```

### `GET /api/v1/skills/list` — List All Skills

List all indexed skills with pagination. Same query parameters as search.

**Response**: Same shape as search response.

### `GET /api/v1/skills/{skill_id}` — Get Skill by ID

Retrieve a single skill by its database ID.

**Response `200 OK`**:
```json
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
  "root_path": "/path/to/repo"
}
```

**Error `404 Not Found`** — skill ID not in index:
```json
{"detail": "Skill not found: 99999"}
```

### `DELETE /api/v1/skills/clear` — Clear Index

Delete indexed skills. Optionally scoped to a root path.

**Query Parameters**:
- `root_path` (string, optional) — only clear skills from this path.

**Response `200 OK`**:
```json
{"deleted": 12}
```

## Skill Record Shape

All skill records returned by the API have this structure:

| Field | Type | Description |
|---|---|---|
| `id` | int\|null | Database ID |
| `path` | string | Path relative to discovery root |
| `name` | string\|null | From frontmatter |
| `description` | string\|null | From frontmatter |
| `topic` | string\|null | Derived from parent directory |
| `scope` | string\|null | Derived from `skills/{scope}/` pattern |
| `valid` | bool | Passed structural validation |
| `errors` | list[string] | Validation errors |
| `content_length` | int | Total bytes of SKILL.md file |
| `discovered_at` | string | UTC timestamp (ISO 8601) |
| `root_path` | string\|null | Discovery root directory |