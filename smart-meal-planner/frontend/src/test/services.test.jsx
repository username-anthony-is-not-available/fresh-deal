import React from 'react';
import { render, screen, act, renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const toastMock = vi.hoisted(() => {
  const fn = vi.fn();
  fn.success = vi.fn();
  fn.error = vi.fn();
  return fn;
});
vi.mock('react-hot-toast', () => ({ default: toastMock }));

const axiosInstance = vi.hoisted(() => {
  const requestHandlers = [];
  const responseHandlers = [];
  const instance = vi.fn((config) => instance.request(config));
  instance.request = vi.fn();
  instance.get = vi.fn();
  instance.post = vi.fn();
  instance.delete = vi.fn();
  instance.defaults = {};
  instance.interceptors = {
    request: {
      handlers: requestHandlers,
      use: (fulfilled, rejected) => {
        requestHandlers.push({ fulfilled, rejected });
      },
    },
    response: {
      handlers: responseHandlers,
      use: (fulfilled, rejected) => {
        responseHandlers.push({ fulfilled, rejected });
      },
    },
  };
  return instance;
});
const axiosMock = vi.hoisted(() => ({
  post: vi.fn(),
  get: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
  create: () => axiosInstance,
}));
vi.mock('axios', () => ({ default: axiosMock }));

vi.mock('../services/authService', () => ({
  default: {
    getCurrentUser: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    register: vi.fn(),
  },
}));

import axios from 'axios';
import toast from 'react-hot-toast';
import api from '../services/api';
import authService from '../services/authService';
import pantryService from '../services/pantryService';
import SettingsService from '../services/SettingsService';
import {
  getNutritionGoal,
  createOrUpdateNutritionGoal,
  getNutritionSummary,
  getDietaryProfiles,
  getRecommendedNutritionGoal,
  getNutritionCompliance,
} from '../services/nutritionService';
import {
  showSuccessToast,
  showErrorToast,
  showInfoToast,
} from '../utils/toast';
import { useNetworkStatus } from '../hooks/useNetworkStatus';
import { ThemeProvider, ThemeContext } from '../context/ThemeContext';
import { AuthProvider, useAuth } from '../context/AuthContext';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  console.error.mockRestore();
  vi.useRealTimers();
});

// ---------------------------------------------------------------------------
// api.js interceptors
// ---------------------------------------------------------------------------

describe('api interceptors', () => {
  const reqHandler = () => api.interceptors.request.handlers[0];
  const resHandler = () => api.interceptors.response.handlers[0];

  it('adds the Authorization header when a user token is stored', () => {
    localStorage.setItem('user', JSON.stringify({ access_token: 'tok123' }));
    const config = { headers: {} };
    const out = reqHandler().fulfilled(config);
    expect(out.headers.Authorization).toBe('Bearer tok123');
  });

  it('leaves the config alone when there is no stored user', () => {
    const config = { headers: {} };
    expect(reqHandler().fulfilled(config)).toBe(config);
    expect(config.headers.Authorization).toBeUndefined();
  });

  it('rejects request errors', async () => {
    const err = new Error('req fail');
    await expect(reqHandler().rejected(err)).rejects.toBe(err);
  });

  it('passes successful responses through as data', () => {
    expect(resHandler().fulfilled({ data: { a: 1 } })).toEqual({ a: 1 });
  });

  it('shows the detail message and rejects non-5xx errors', async () => {
    const err = { config: {}, response: { status: 404, data: { detail: 'Not found' } } };
    await expect(resHandler().rejected(err)).rejects.toBe(err);
    expect(toastMock.error).toHaveBeenCalledWith('Not found');
  });

  it('falls back to a generic message when there is no detail', async () => {
    const err = { config: {} };
    await expect(resHandler().rejected(err)).rejects.toBe(err);
    expect(toastMock.error).toHaveBeenCalledWith(
      'An unexpected error occurred. Please try again.'
    );
  });

  it('does not retry a 5xx error that was already retried', async () => {
    const err = { config: { _retry: true }, response: { status: 500, data: {} } };
    await expect(resHandler().rejected(err)).rejects.toBe(err);
    expect(toastMock.error).toHaveBeenCalledWith(
      'An unexpected error occurred. Please try again.'
    );
  });

  it('retries a first 5xx error after a delay', async () => {
    vi.useFakeTimers();
    api.request.mockRejectedValue(new Error('no network'));
    const err = { config: { url: '/x' }, response: { status: 500, data: {} } };
    const promise = resHandler().rejected(err);
    expect(err.config._retry).toBe(true);
    expect(toastMock.error).toHaveBeenCalledWith(
      'A server error occurred, retrying the request...'
    );
    const assertion = expect(promise).rejects.toThrow('no network');
    await vi.advanceTimersByTimeAsync(1000);
    await assertion;
  });
});

// ---------------------------------------------------------------------------
// pantryService / SettingsService
// ---------------------------------------------------------------------------

describe('pantryService', () => {
  it('delegates to the api instance', async () => {
    api.get.mockResolvedValue([]);
    api.post.mockResolvedValue({});
    api.delete.mockResolvedValue({});
    await pantryService.getIngredients(1);
    expect(api.get).toHaveBeenCalledWith('/pantry/1');
    await pantryService.addIngredients(1, [{ name: 'Rice' }]);
    expect(api.post).toHaveBeenCalledWith('/pantry/1/add', { items: [{ name: 'Rice' }] });
    await pantryService.deleteIngredient(1, 5);
    expect(api.delete).toHaveBeenCalledWith('/pantry/1/5');
    await pantryService.consumeLatestPlan(1);
    expect(api.post).toHaveBeenCalledWith('/pantry/1/consume-latest-plan');
  });
});

describe('SettingsService', () => {
  it('gets and patches user settings', async () => {
    axios.get.mockResolvedValue({ data: {} });
    axios.patch.mockResolvedValue({ data: {} });
    await SettingsService.getUserSettings(3);
    expect(axios.get).toHaveBeenCalledWith('http://localhost:8000/api/users/3');
    await SettingsService.updateUserSettings(3, { theme: 'dark' });
    expect(axios.patch).toHaveBeenCalledWith(
      'http://localhost:8000/api/users/3', { theme: 'dark' }
    );
  });
});

// ---------------------------------------------------------------------------
// nutritionService
// ---------------------------------------------------------------------------

describe('nutritionService', () => {
  it('returns response.data when present and the raw response otherwise', async () => {
    api.get
      .mockResolvedValueOnce({ data: { calories: 100 } })
      .mockResolvedValueOnce({ other: true });
    expect(await getNutritionGoal()).toEqual({ calories: 100 });
    expect(await getNutritionGoal()).toEqual({ other: true });
  });

  it('returns the nutrition summary payload on success', async () => {
    api.get.mockResolvedValueOnce({ data: [{ date: '2026-01-01', calories: 100 }] });
    expect(await getNutritionSummary('2026-01-01', '2026-01-07')).toEqual([
      { date: '2026-01-01', calories: 100 },
    ]);
    expect(api.get).toHaveBeenCalledWith(
      '/users/me/nutrition-summary',
      { params: { start_date: '2026-01-01', end_date: '2026-01-07' } }
    );
  });

  it('logs and rethrows on fetch errors', async () => {
    const err = new Error('boom');
    api.get.mockRejectedValue(err);
    api.post.mockRejectedValue(err);
    await expect(getNutritionGoal()).rejects.toBe(err);
    expect(console.error).toHaveBeenCalled();
    await expect(createOrUpdateNutritionGoal({})).rejects.toBe(err);
    await expect(getNutritionSummary('2026-01-01', '2026-01-07')).rejects.toBe(err);
    expect(api.get).toHaveBeenCalledWith(
      '/users/me/nutrition-summary',
      { params: { start_date: '2026-01-01', end_date: '2026-01-07' } }
    );
  });

  it('posts goals and reads profiles/recommendations/compliance', async () => {
    api.post.mockResolvedValue({ data: { ok: true } });
    api.get.mockResolvedValue({ data: [1, 2] });
    expect(await createOrUpdateNutritionGoal({ calories: 2000 })).toEqual({ ok: true });
    expect(api.post).toHaveBeenCalledWith('/users/me/nutrition-goal', { calories: 2000 });
    expect(await getDietaryProfiles()).toEqual([1, 2]);
    expect(await getRecommendedNutritionGoal({ age: 30 })).toEqual({ ok: true });
    expect(await getNutritionCompliance(14)).toEqual([1, 2]);
    expect(api.get).toHaveBeenCalledWith(
      '/users/me/nutrition-compliance', { params: { days: 14 } }
    );
    // Default compliance window is 7 days.
    await getNutritionCompliance();
    expect(api.get).toHaveBeenCalledWith(
      '/users/me/nutrition-compliance', { params: { days: 7 } }
    );
  });
});

// ---------------------------------------------------------------------------
// toast utils
// ---------------------------------------------------------------------------

describe('toast utils', () => {
  it('forwards to react-hot-toast', () => {
    showSuccessToast('yay');
    expect(toast.success).toHaveBeenCalledWith('yay');
    showErrorToast('oops');
    expect(toast.error).toHaveBeenCalledWith('oops');
    showInfoToast('note');
    expect(toast).toHaveBeenCalledWith('note', { icon: 'ℹ️' });
  });
});

// ---------------------------------------------------------------------------
// useNetworkStatus
// ---------------------------------------------------------------------------

describe('useNetworkStatus', () => {
  it('tracks online/offline events and cleans up', () => {
    const { result, unmount } = renderHook(() => useNetworkStatus());
    expect(result.current).toBe(navigator.onLine);
    act(() => window.dispatchEvent(new Event('offline')));
    expect(result.current).toBe(false);
    act(() => window.dispatchEvent(new Event('online')));
    expect(result.current).toBe(true);
    unmount();
  });
});

// ---------------------------------------------------------------------------
// ThemeContext
// ---------------------------------------------------------------------------

describe('ThemeContext', () => {
  const Consumer = () => {
    const { theme, toggleTheme } = React.useContext(ThemeContext);
    return (
      <button onClick={toggleTheme} data-testid="theme-btn">
        {theme}
      </button>
    );
  };

  it('defaults to light, toggles to dark and persists it', () => {
    render(<ThemeProvider><Consumer /></ThemeProvider>);
    expect(screen.getByTestId('theme-btn')).toHaveTextContent('light');
    expect(document.documentElement.classList.contains('light')).toBe(true);
    act(() => screen.getByTestId('theme-btn').click());
    expect(screen.getByTestId('theme-btn')).toHaveTextContent('dark');
    expect(localStorage.getItem('theme')).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    act(() => screen.getByTestId('theme-btn').click());
    expect(screen.getByTestId('theme-btn')).toHaveTextContent('light');
  });

  it('starts from the stored theme', () => {
    localStorage.setItem('theme', 'dark');
    render(<ThemeProvider><Consumer /></ThemeProvider>);
    expect(screen.getByTestId('theme-btn')).toHaveTextContent('dark');
  });
});

// ---------------------------------------------------------------------------
// AuthContext
// ---------------------------------------------------------------------------

describe('AuthContext', () => {
  const Probe = () => {
    const { user, currentUser, login, logout, register } = useAuth();
    return (
      <div>
        <span data-testid="user">{user ? user.email : 'none'}</span>
        <span data-testid="alias">{currentUser ? currentUser.email : 'none'}</span>
        <button data-testid="login" onClick={() => login('a@b.c', 'pw')}>login</button>
        <button data-testid="logout" onClick={logout}>logout</button>
        <button
          data-testid="register"
          onClick={() => register('a@b.c', 'pw', 'H1H1H1', 2, [])}
        >
          register
        </button>
      </div>
    );
  };

  it('loads the stored user on mount and logs in/out', async () => {
    authService.getCurrentUser.mockReturnValue({ email: 'stored@x.c' });
    authService.login.mockResolvedValue({ data: { access_token: 'tok', email: 'a@b.c' } });
    render(<AuthProvider><Probe /></AuthProvider>);
    expect(screen.getByTestId('user')).toHaveTextContent('stored@x.c');
    expect(screen.getByTestId('alias')).toHaveTextContent('stored@x.c');
    await act(async () => screen.getByTestId('login').click());
    expect(screen.getByTestId('user')).toHaveTextContent('a@b.c');
    expect(JSON.parse(localStorage.getItem('user')).access_token).toBe('tok');
    act(() => screen.getByTestId('logout').click());
    expect(screen.getByTestId('user')).toHaveTextContent('none');
    expect(authService.logout).toHaveBeenCalled();
  });

  it('does not set a user when login returns no token', async () => {
    authService.getCurrentUser.mockReturnValue(null);
    authService.login.mockResolvedValue({ data: {} });
    render(<AuthProvider><Probe /></AuthProvider>);
    await act(async () => screen.getByTestId('login').click());
    expect(screen.getByTestId('user')).toHaveTextContent('none');
    expect(localStorage.getItem('user')).toBeNull();
  });

  it('register delegates to the service', async () => {
    authService.getCurrentUser.mockReturnValue(null);
    authService.register.mockResolvedValue({ data: { id: 9 } });
    render(<AuthProvider><Probe /></AuthProvider>);
    await act(async () => screen.getByTestId('register').click());
    expect(authService.register).toHaveBeenCalledWith('a@b.c', 'pw', 'H1H1H1', 2, []);
  });
});
