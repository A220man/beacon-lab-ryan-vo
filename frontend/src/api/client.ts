/**
 * Typed API client for Beacon Lab's backend.
 *
 * All paths are relative (e.g., "/api/v1/skills/...") so the same client
 * works in development (via Vite proxy) and production (via reverse proxy).
 */
import type { DiscoveryReport, SearchResponse, SearchResult, DiscoveryRequest } from '../types';

const API_BASE = '/api/v1/skills';

/**
 * Discover and validate all SKILL.md files in the given directory.
 * Returns a full DiscoveryReport including per-skill validation status.
 */
export async function discoverSkills(request: DiscoveryRequest): Promise<DiscoveryReport> {
  const response = await fetch(`${API_BASE}/discover`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error_body = await response.json().catch(() => ({}));
    throw new Error(error_body.detail || `HTTP ${response.status}`);
  }

  return response.json() as Promise<DiscoveryReport>;
}

/**
 * Search the indexed skill database by name, topic, description, or path.
 */
export async function searchSkills(query: string, limit = 50, offset = 0): Promise<SearchResponse> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
    offset: String(offset),
  });

  const response = await fetch(`${API_BASE}/search?${params}`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json() as Promise<SearchResponse>;
}

/**
 * List all indexed skills without a query filter.
 */
export async function listSkills(limit = 50, offset = 0): Promise<SearchResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });

  const response = await fetch(`${API_BASE}/list?${params}`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json() as Promise<SearchResponse>;
}

/**
 * Get details for a single skill by its database ID.
 */
export async function getSkill(id: number): Promise<SearchResult & { errors: string[]; root_path: string | null }> {
  const response = await fetch(`${API_BASE}/${id}`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json() as Promise<SearchResult & { errors: string[]; root_path: string | null }>;
}

/**
 * Clear the skill index. If rootPath is provided, only skills from
 * that path are deleted.
 */
export async function clearIndex(rootPath?: string): Promise<{ deleted: number }> {
  const url = new URL(`${window.location.origin}${API_BASE}/clear`);
  if (rootPath) {
    url.searchParams.set('root_path', rootPath);
  }
  const response = await fetch(url.toString(), { method: 'DELETE' });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json() as Promise<{ deleted: number }>;
}