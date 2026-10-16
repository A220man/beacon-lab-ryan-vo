/**
 * TypeScript types mirroring the backend API response schemas.
 * These are derived from the actual FastAPI route definitions and
 * Pydantic response models in backend/app/core/models.py.
 */

/** A discovered skill record from the discovery engine. */
export interface SkillRecord {
  id: number | null;
  path: string;
  name: string | null;
  description: string | null;
  topic: string | null;
  scope: string | null;
  valid: boolean;
  errors: string[];
  content_length: number;
  discovered_at: string;
  root_path: string | null;
}

/** Full discovery report returned by POST /discover. */
export interface DiscoveryReport {
  skills: SkillRecord[];
  total_found: number;
  total_valid: number;
  total_invalid: number;
  root_path: string;
  errors: string[];
  discovered_at: string;
}

/** A single search result (from the indexed database, may include an ID). */
export interface SearchResult {
  id: number;
  path: string;
  name: string | null;
  description: string | null;
  topic: string | null;
  scope: string | null;
  valid: boolean;
  errors: string[];
  content_length: number;
  discovered_at: string;
}

/** Paginated search response from GET /search. */
export interface SearchResponse {
  skills: SearchResult[];
  total: number;
  limit: number;
  offset: number;
  query: string;
}

/** Request payload for POST /discover. */
export interface DiscoveryRequest {
  repository_path: string;
}