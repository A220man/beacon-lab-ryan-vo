import React from 'react';
import type { SearchResult } from '../types';
import './SkillTable.css';

interface SkillTableProps {
  skills: SearchResult[];
}

export function SkillTable({ skills }: SkillTableProps) {
  if (skills.length === 0) {
    return (
      <div className="empty-table">
        <p>No skills found. Try a different search term.</p>
      </div>
    );
  }

  return (
    <div className="table-container">
      <table className="skill-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Description</th>
            <th>Topic</th>
            <th>Scope</th>
            <th>Status</th>
            <th>Path</th>
          </tr>
        </thead>
        <tbody>
          {skills.map((skill) => (
            <React.Fragment key={skill.path}>
              <tr className={skill.valid ? 'row-valid' : 'row-invalid'}>
                <td className="cell-name">{skill.name || '—'}</td>
                <td className="cell-desc">{skill.description || '—'}</td>
                <td>{skill.topic || '—'}</td>
                <td>{skill.scope || '—'}</td>
                <td>
                  <span className={skill.valid ? 'badge badge-valid' : 'badge badge-invalid'}>
                    {skill.valid ? 'Valid' : 'Invalid'}
                  </span>
                </td>
                <td className="cell-path">{skill.path}</td>
              </tr>
              {!skill.valid && skill.errors.length > 0 && (
                <tr className="error-row">
                  <td colSpan={6}>
                    <ul className="error-list-inline">
                      {skill.errors.map((e, i) => <li key={i}>{e}</li>)}
                    </ul>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}