import { useState } from 'react';
import { SkillTable } from './SkillTable';
import { discoverSkills, searchSkills } from '../api/client';
import type { DiscoveryReport, SearchResult } from '../types';

type ViewState = 'empty' | 'loading' | 'error' | 'results';

export function SkillDashboard() {
  const [repoPath, setRepoPath] = useState('');
  const [viewState, setViewState] = useState<ViewState>('empty');
  const [discoverReport, setDiscoverReport] = useState<DiscoveryReport | null>(null);
  const [indexedResults, setIndexedResults] = useState<SearchResult[]>([]);
  const [indexedTotal, setIndexedTotal] = useState(0);
  const [error, setError] = useState('');

  const loadIndex = async () => {
    const resp = await searchSkills('');
    setIndexedResults(resp.skills);
    setIndexedTotal(resp.total);
  };

  const handleDiscover = async () => {
    if (!repoPath.trim()) {
      setError('Please enter a repository path.');
      setViewState('error');
      return;
    }
    setViewState('loading');
    setError('');
    try {
      const report = await discoverSkills({ repository_path: repoPath });
      setDiscoverReport(report);
      await loadIndex();
      setViewState('results');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setViewState('error');
    }
  };

  const handleSearch = async (query: string) => {
    if (!query.trim()) {
      await loadIndex();
      return;
    }
    setViewState('loading');
    try {
      const resp = await searchSkills(query);
      setIndexedResults(resp.skills);
      setIndexedTotal(resp.total);
      setViewState('results');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setViewState('error');
    }
  };

  const handleExport = () => {
    if (!discoverReport) return;
    const dataStr = JSON.stringify(discoverReport, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'beacon-skills-report.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleClear = async () => {
    await fetch('/api/v1/skills/clear', { method: 'DELETE' });
    setIndexedResults([]);
    setIndexedTotal(0);
    setDiscoverReport(null);
    setViewState('empty');
  };

  return (
    <section className="dashboard">
      <h2>Skill Discovery</h2>
      <p className="help-text">
        Beacon Lab recursively discovers SKILL.md files at any depth — not
        limited to a <code>skills/</code> directory — and validates each
        against the open-standard agent skills spec.
      </p>

      <div className="discover-form">
        <input
          type="text"
          value={repoPath}
          onChange={(e) => setRepoPath(e.target.value)}
          placeholder="Enter repository path (e.g., /path/to/skills-repo)"
          className="input"
          onKeyDown={(e) => { if (e.key === 'Enter') handleDiscover(); }}
          aria-label="Repository path"
        />
        <button
          onClick={handleDiscover}
          className="btn btn-primary"
          disabled={viewState === 'loading'}
        >
          {viewState === 'loading' ? 'Discovering…' : 'Discover Skills'}
        </button>
      </div>

      {viewState === 'loading' && (
        <div className="loading-state" role="status">
          <div className="spinner" aria-label="Loading"></div>
          <p>Discovering and validating skills…</p>
        </div>
      )}

      {viewState === 'error' && (
        <div className="error-state" role="alert">
          <p><strong>Error:</strong> {error}</p>
        </div>
      )}

      {viewState === 'empty' && (
        <div className="empty-state">
          <p>Enter a repository path and click “Discover Skills” to begin.</p>
        </div>
      )}

      {viewState === 'results' && discoverReport && (
        <>
          <div className="summary-bar">
            <span className="summary-stat">Found: {discoverReport.total_found}</span>
            <span className="summary-stat valid">Valid: {discoverReport.total_valid}</span>
            <span className="summary-stat invalid">Invalid: {discoverReport.total_invalid}</span>
          </div>

          {discoverReport.errors.length > 0 && (
            <div className="error-list" role="alert">
              {discoverReport.errors.map((e, i) => <p key={i}>{e}</p>)}
            </div>
          )}

          <div className="search-bar">
            <input
              type="search"
              placeholder="Search skills by name, topic, or description…"
              className="input"
              onChange={(e) => handleSearch(e.target.value)}
              aria-label="Search skills"
            />
          </div>

          <p className="index-info">
            Showing {indexedResults.length} of {indexedTotal} indexed skills.
          </p>

          <SkillTable skills={indexedResults} />

          <div className="actions">
            <button onClick={handleExport} className="btn btn-secondary">
              Export Report (JSON)
            </button>
            <button
              onClick={handleClear}
              className="btn btn-secondary"
              style={{ marginLeft: '0.5rem' }}
            >
              Clear Index
            </button>
          </div>
        </>
      )}
    </section>
  );
}