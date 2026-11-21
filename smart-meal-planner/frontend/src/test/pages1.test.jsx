import React from 'react';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

const toastMock = vi.hoisted(() => {
  const fn = vi.fn(() => 'toast-id');
  fn.success = vi.fn();
  fn.error = vi.fn();
  fn.loading = vi.fn(() => 'toast-id');
  return fn;
});
vi.mock('react-hot-toast', () => ({ default: toastMock, toast: toastMock }));

vi.mock('../services/api', () => ({
  default: { post: vi.fn(), get: vi.fn(), delete: vi.fn() },
}));

import api from '../services/api';
import AuthContext from '../context/AuthContext';
import LoginPage from '../pages/LoginPage';
import RegisterPage from '../pages/RegisterPage';
import HomePage from '../pages/HomePage';
import DealsPage from '../pages/DealsPage';

const LocationProbe = () => {
  const { pathname } = useLocation();
  return <div data-testid="location">{pathname}</div>;
};

const renderWithRouter = (ui, { route = '/', auth = {} } = {}) => {
  return render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="*" element={<>{ui}<LocationProbe /></>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>
  );
};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  vi.spyOn(console, 'error').mockImplementation(() => {});
  vi.spyOn(console, 'warn').mockImplementation(() => {});
  vi.spyOn(console, 'log').mockImplementation(() => {});
});

const deal = (overrides = {}) => ({
  id: 1,
  product: { name: 'Chicken Breast', category: 'Meat', unit_type: 'kg' },
  store: { name: 'Metro' },
  loyalty_program: 'PC Optimum',
  loyalty_points: 1000,
  effective_price: 4.0,
  quality_level: 'good',
  quality_score: 80,
  image_url: null,
  sale_info: null,
  distance: null,
  discount_pct: 25,
  price: 5.0,
  original_price: 8.0,
  valid_until: '2026-12-31',
  ...overrides,
});

// ---------------------------------------------------------------------------
// LoginPage
// ---------------------------------------------------------------------------

describe('LoginPage', () => {
  it('logs in and navigates to the plan page', async () => {
    const login = vi.fn().mockResolvedValue({ data: { access_token: 't' } });
    renderWithRouter(<LoginPage />, { auth: { login } });
    fireEvent.change(document.querySelector('input[name="username"]'), {
      target: { value: 'a@b.c' },
    });
    fireEvent.change(document.querySelector('input[type="password"]'), {
      target: { value: 'secret' },
    });
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Login' })));
    expect(login).toHaveBeenCalledWith('a@b.c', 'secret');
    expect(screen.getByTestId('location')).toHaveTextContent('/plan');
  });

  it('shows an error when login fails', async () => {
    const login = vi.fn().mockRejectedValue(new Error('bad creds'));
    renderWithRouter(<LoginPage />, { auth: { login } });
    fireEvent.change(document.querySelector('input[name="username"]'), {
      target: { value: 'a@b.c' },
    });
    fireEvent.change(document.querySelector('input[type="password"]'), {
      target: { value: 'wrong' },
    });
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Login' })));
    expect(await screen.findByText('Invalid email or password')).toBeInTheDocument();
    expect(console.error).toHaveBeenCalled();
    expect(screen.getByTestId('location')).toHaveTextContent('/');
  });
});

// ---------------------------------------------------------------------------
// RegisterPage
// ---------------------------------------------------------------------------

describe('RegisterPage', () => {
  const fill = () => {
    const inputs = document.querySelectorAll('input');
    fireEvent.change(inputs[0], { target: { value: 'new@user.c' } });
    fireEvent.change(inputs[1], { target: { value: 'pw123' } });
    fireEvent.change(inputs[2], { target: { value: 'H2X 1Y2' } });
  };

  it('registers with no dietary restrictions and navigates to login', async () => {
    const register = vi.fn().mockResolvedValue({});
    renderWithRouter(<RegisterPage />, { auth: { register } });
    fill();
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Register' })));
    expect(register).toHaveBeenCalledWith('new@user.c', 'pw123', 'H2X 1Y2', 4, []);
    expect(screen.getByTestId('location')).toHaveTextContent('/login');
  });

  it('lowercases the chosen dietary preference and parses household size', async () => {
    const register = vi.fn().mockResolvedValue({});
    renderWithRouter(<RegisterPage />, { auth: { register } });
    fill();
    const selects = document.querySelectorAll('select');
    fireEvent.change(selects[0], { target: { value: '2' } });
    fireEvent.change(selects[1], { target: { value: 'Vegan' } });
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Register' })));
    expect(register).toHaveBeenCalledWith('new@user.c', 'pw123', 'H2X 1Y2', 2, ['vegan']);
  });

  it('shows an error when registration fails', async () => {
    const register = vi.fn().mockRejectedValue(new Error('taken'));
    renderWithRouter(<RegisterPage />, { auth: { register } });
    fill();
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Register' })));
    expect(await screen.findByText('Failed to register')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// HomePage
// ---------------------------------------------------------------------------

describe('HomePage', () => {
  it('shows the last scraped info and active deal count', async () => {
    api.get.mockResolvedValue({
      last_scraped_at: '2026-11-21T10:00:00Z', total_active_deals: 42,
    });
    renderWithRouter(<HomePage />);
    expect(await screen.findByText(/Last updated:/)).toBeInTheDocument();
    expect(screen.getByText(/42 active deals/)).toBeInTheDocument();
    expect(screen.getByText('Scrape Local Flyers Now')).toBeInTheDocument();
  });

  it('shows the ready message when there is no scrape data', async () => {
    api.get.mockResolvedValue(null);
    renderWithRouter(<HomePage />);
    expect(await screen.findByText('Flyers ready for weekly sync')).toBeInTheDocument();
  });

  it('warns when the last-scraped fetch fails', async () => {
    api.get.mockRejectedValue(new Error('down'));
    renderWithRouter(<HomePage />);
    await waitFor(() => expect(console.warn).toHaveBeenCalled());
    expect(screen.getByText('Flyers ready for weekly sync')).toBeInTheDocument();
  });

  it('scrapes flyers and refreshes the info', async () => {
    api.get.mockResolvedValue({
      last_scraped_at: '2026-11-21T10:00:00Z', total_active_deals: 42,
    });
    api.post.mockResolvedValue({ timestamp: '2026-11-21T11:00:00Z' });
    renderWithRouter(<HomePage />);
    await screen.findByText(/Last updated:/);
    await act(async () => fireEvent.click(screen.getByText('Scrape Local Flyers Now')));
    expect(api.post).toHaveBeenCalledWith('/scrape/trigger');
    expect(toastMock.loading).toHaveBeenCalled();
    expect(toastMock.success).toHaveBeenCalledWith(
      'Quebec weekly flyers scraped & updated successfully!', { id: 'toast-id' }
    );
    expect(api.get).toHaveBeenCalledTimes(2);
  });

  it('shows an error toast when scraping fails', async () => {
    api.get.mockResolvedValue(null);
    api.post.mockRejectedValue(new Error('scrape down'));
    renderWithRouter(<HomePage />);
    await screen.findByText('Flyers ready for weekly sync');
    await act(async () => fireEvent.click(screen.getByText('Scrape Local Flyers Now')));
    expect(toastMock.error).toHaveBeenCalledWith(
      'Failed to scrape flyers. Please try again or check logs.', { id: 'toast-id' }
    );
    expect(console.error).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// DealsPage
// ---------------------------------------------------------------------------

describe('DealsPage', () => {
  const deals = [
    deal(),
    deal({ id: 2, product: { name: 'Salmon', category: 'Fish', unit_type: 'kg' }, store: { name: 'IGA' }, loyalty_program: 'Scene+', quality_level: 'excellent', price: 12.0, discount_pct: 10 }),
  ];

  it('shows a loading state, then the deals', async () => {
    api.get.mockResolvedValue(deals);
    renderWithRouter(<DealsPage />);
    expect(screen.getByText('Loading deals...')).toBeInTheDocument();
    expect(await screen.findByText('Chicken Breast')).toBeInTheDocument();
    expect(screen.getByText('Salmon')).toBeInTheDocument();
    expect(screen.getByText('Found 2 active deals near you')).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith(expect.stringContaining('/deals?'));
    expect(api.get.mock.calls[0][0]).toContain('postal_code=H4T1V6');
  });

  it('uses the stored postal code', async () => {
    localStorage.setItem('user_postal_code', 'H2X1Y2');
    api.get.mockResolvedValue([]);
    renderWithRouter(<DealsPage />);
    await screen.findByText(/No deals found/);
    expect(api.get.mock.calls[0][0]).toContain('postal_code=H2X1Y2');
  });

  it('filters by text, loyalty and quality, and re-sorts', async () => {
    api.get.mockResolvedValue(deals);
    renderWithRouter(<DealsPage />);
    await screen.findByText('Chicken Breast');
    fireEvent.change(screen.getByPlaceholderText('Search deals...'), {
      target: { value: 'salmon' },
    });
    expect(screen.queryByText('Chicken Breast')).toBeNull();
    expect(screen.getByText('Salmon')).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText('Search deals...'), { target: { value: '' } });
    fireEvent.change(screen.getByLabelText('Filter by loyalty program'), {
      target: { value: 'Scene+' },
    });
    expect(screen.queryByText('Chicken Breast')).toBeNull();
    fireEvent.change(screen.getByLabelText('Filter by loyalty program'), { target: { value: '' } });
    fireEvent.change(screen.getByLabelText('Filter by deal quality'), {
      target: { value: 'excellent' },
    });
    expect(screen.queryByText('Chicken Breast')).toBeNull();
    expect(screen.getByText('Salmon')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Filter by deal quality'), { target: { value: '' } });
    fireEvent.change(screen.getByPlaceholderText('Postal Code'), {
      target: { value: 'h2x' },
    });
    expect(screen.getByPlaceholderText('Postal Code').value).toBe('H2X');
    const sort = document.querySelectorAll('select')[0];
    fireEvent.change(sort, { target: { value: 'discount_pct' } });
    // The postal-code change above already triggered a refetch, so the
    // sort change is the third fetch.
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(3));
    expect(api.get.mock.calls[2][0]).toContain('sort_by=discount_pct');
  });

  it('shows the empty state and seeds data', async () => {
    api.get.mockResolvedValue([]);
    api.post.mockResolvedValue({});
    renderWithRouter(<DealsPage />);
    await screen.findByText(/No deals found/);
    await act(async () => fireEvent.click(screen.getByText('Seed Mock Data')));
    expect(api.post).toHaveBeenCalledWith('/data/seed');
  });

  it('logs seed failures', async () => {
    api.get.mockResolvedValue([]);
    api.post.mockRejectedValue(new Error('seed down'));
    renderWithRouter(<DealsPage />);
    await screen.findByText(/No deals found/);
    await act(async () => fireEvent.click(screen.getByText('Seed Mock Data')));
    expect(console.error).toHaveBeenCalled();
  });

  it('empties the list when fetching fails', async () => {
    api.get.mockRejectedValue(new Error('down'));
    renderWithRouter(<DealsPage />);
    expect(await screen.findByText(/No deals found/)).toBeInTheDocument();
    expect(console.warn).toHaveBeenCalled();
  });
});
