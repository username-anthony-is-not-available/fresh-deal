import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ScrapingDashboardPage from '../pages/ScrapingDashboardPage';
import { BrowserRouter } from 'react-router-dom';
import api from '../services/api';

// Mock the API service
vi.mock('../services/api');

// Mock Lucide icons to avoid rendering issues in tests
vi.mock('lucide-react', () => ({
  Play: () => <div data-testid="play-icon" />,
  RefreshCw: () => <div data-testid="refresh-icon" />,
  CheckCircle: () => <div data-testid="check-circle-icon" />,
  XCircle: () => <div data-testid="x-circle-icon" />,
  Clock: () => <div data-testid="clock-icon" />,
  Database: () => <div data-testid="database-icon" />,
  Loader2: () => <div data-testid="loader-icon" />,
  Trash2: () => <div data-testid="trash-icon" />,
  Square: () => <div data-testid="square-icon" />,
  StopCircle: () => <div data-testid="stop-icon" />,
  Zap: () => <div data-testid="zap-icon" />,
  Globe: () => <div data-testid="globe-icon" />,
  Activity: () => <div data-testid="activity-icon" />,
  AlertTriangle: () => <div data-testid="alert-triangle-icon" />,
  ShieldAlert: () => <div data-testid="shield-alert-icon" />,
}));

const mockHealthMetrics = [
  {
    store_name: 'metro',
    success_rate: 95.5,
    avg_duration_seconds: 12.4,
    total_items_scraped: 450,
    last_run: '2024-01-01T12:00:00Z',
    status: 'healthy',
    total_runs: 20,
    error_breakdown: {},
    last_error: null
  },
  {
    store_name: 'walmart',
    success_rate: 45.0,
    avg_duration_seconds: 30.2,
    total_items_scraped: 120,
    last_run: '2024-01-01T11:00:00Z',
    status: 'critical',
    total_runs: 20,
    error_breakdown: { 'Bot Block': 11 },
    last_error: '[BOT_BLOCK] Blocked by Incapsula'
  }
];

const mockHealthSummary = {
  overall_status: 'degraded',
  overall_success_rate: 70.2,
  total_scrapers: 2,
  healthy_scrapers: 1,
  critical_scrapers: 1,
  timestamp: '2024-01-01T12:05:00Z'
};

describe('ScrapingDashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockImplementation((url) => {
      if (url === '/deals') return Promise.resolve([]);
      if (url === '/admin/scrapers/health') return Promise.resolve(mockHealthMetrics);
      if (url === '/admin/scrapers/health/summary') return Promise.resolve(mockHealthSummary);
      return Promise.resolve({});
    });
  });

  const renderDashboard = () => {
    return render(
      <BrowserRouter>
        <ScrapingDashboardPage />
      </BrowserRouter>
    );
  };

  it('renders system health summary', async () => {
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/System Status/i)).toBeDefined();
      expect(screen.getByText(/DEGRADED/i)).toBeDefined();
      expect(screen.getByText(/70.2%/)).toBeDefined();
      expect(screen.getByText(/1 \/ 2/)).toBeDefined();
    }, { timeout: 3000 });
  });

  it('renders scraper reliability table', async () => {
    renderDashboard();

    // Wait for loading to finish
    await waitFor(() => {
      expect(screen.queryByText(/Loading metrics/i)).toBeNull();
    }, { timeout: 5000 });

    // Use getAllByText and check that at least one is in the table (or just check existence of specific metrics)
    expect(screen.getAllByText(/metro/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/walmart/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/95.5%/)).toBeDefined();
    expect(screen.getByText(/45%/)).toBeDefined();
    // Status badges are often repeated if they appear elsewhere, but let's just ensure they exist
    expect(screen.getAllByText(/HEALTHY/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/CRITICAL/i).length).toBeGreaterThan(0);
  });

  it('calls reset circuit breaker endpoint when reset button is clicked', async () => {
    api.post.mockResolvedValue({ message: 'Success' });
    renderDashboard();

    await waitFor(() => {
      const resetButtons = screen.getAllByTitle('Reset Circuit Breaker');
      expect(resetButtons.length).toBe(1); // Only for walmart (critical)
      fireEvent.click(resetButtons[0]);
    });

    expect(api.post).toHaveBeenCalledWith('/admin/scrapers/walmart/reset');
  });
});
