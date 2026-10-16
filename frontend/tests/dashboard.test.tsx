import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { SkillDashboard } from '../src/components/SkillDashboard';

const mockDiscover = vi.fn();
const mockSearch = vi.fn();

vi.mock('../src/api/client', () => ({
  discoverSkills: (...args: unknown[]) => mockDiscover(...args),
  searchSkills: (...args: unknown[]) => mockSearch(...args),
}));

const mockReport = {
  skills: [
    {
      id: 1,
      path: 'performance/r8-analyzer/SKILL.md',
      name: 'r8-analyzer',
      description: 'Analyze R8 optimization issues',
      topic: 'performance',
      scope: null,
      valid: true,
      errors: [],
      content_length: 500,
      discovered_at: '2026-01-01T00:00:00Z',
      root_path: null,
    },
    {
      id: 2,
      path: 'SKILL.md',
      name: null,
      description: null,
      topic: null,
      scope: null,
      valid: false,
      errors: ['Missing required field name in frontmatter'],
      content_length: 10,
      discovered_at: '2026-01-01T00:00:00Z',
      root_path: null,
    },
  ],
  total_found: 2,
  total_valid: 1,
  total_invalid: 1,
  root_path: '/fake/path',
  errors: [],
  discovered_at: '2026-01-01T00:00:00Z',
};

const mockSearchResponse = {
  skills: mockReport.skills,
  total: 2,
  limit: 50,
  offset: 0,
  query: '',
};

describe('SkillDashboard', () => {
  beforeEach(() => {
    mockDiscover.mockReset();
    mockSearch.mockReset();
    mockSearch.mockResolvedValue(mockSearchResponse);
  });

  it('renders the discovery form with an empty state', () => {
    render(<SkillDashboard />);
    expect(screen.getByText('Skill Discovery')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/repository path/i)).toBeInTheDocument();
    expect(screen.getByText(/enter a repository path/i)).toBeInTheDocument();
  });

  it('discovers skills when the form is submitted', async () => {
    mockDiscover.mockResolvedValue(mockReport);

    render(<SkillDashboard />);

    const input = screen.getByPlaceholderText(/repository path/i);
    const button = screen.getByText('Discover Skills');

    fireEvent.change(input, { target: { value: '/fake/path' } });
    fireEvent.click(button);

    // Results are shown after discovery completes
    await waitFor(() => {
      expect(screen.getByText(/Found: 2/)).toBeInTheDocument();
      expect(screen.getByText(/Valid: 1/)).toBeInTheDocument();
      expect(screen.getByText(/Invalid: 1/)).toBeInTheDocument();
    });

    // Skill names appear in the table
    expect(screen.getByText('r8-analyzer')).toBeInTheDocument();
  });

  it('shows an error when the path is empty', async () => {
    render(<SkillDashboard />);

    const button = screen.getByText('Discover Skills');
    fireEvent.click(button);

    expect(await screen.findByText(/please enter a repository path/i)).toBeInTheDocument();
  });

  it('shows an error when discovery fails', async () => {
    mockDiscover.mockRejectedValue(new Error('HTTP 400: Path does not exist'));
    render(<SkillDashboard />);

    const input = screen.getByPlaceholderText(/repository path/i);
    fireEvent.change(input, { target: { value: '/bad/path' } });
    fireEvent.click(screen.getByText('Discover Skills'));

    expect(await screen.findByText(/path does not exist/i)).toBeInTheDocument();
  });

  it('filters skills via the search bar', async () => {
    mockDiscover.mockResolvedValue(mockReport);
    mockSearch.mockResolvedValue({
      skills: [mockReport.skills[0]],
      total: 1,
      limit: 50,
      offset: 0,
      query: 'r8',
    });

    render(<SkillDashboard />);

    const input = screen.getByPlaceholderText(/repository path/i);
    fireEvent.change(input, { target: { value: '/fake/path' } });
    fireEvent.click(screen.getByText('Discover Skills'));

    await waitFor(() => {
      expect(screen.getByText(/Found: 2/)).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/search skills/i);
    fireEvent.change(searchInput, { target: { value: 'r8' } });

    await waitFor(() => {
      expect(screen.getByText(/Showing 1 of 1 indexed/)).toBeInTheDocument();
    });
  });
});