import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('axios', () => ({
  default: { post: vi.fn(), get: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

import axios from 'axios';
import authService from '../services/authService';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe('authService', () => {
  it('registers with the expected payload', async () => {
    axios.post.mockResolvedValue({ data: { id: 1 } });
    await authService.register('a@b.c', 'pw', 'H1H1H1', 2, ['vegan']);
    expect(axios.post).toHaveBeenCalledWith(
      'http://localhost:8000/auth/register',
      { email: 'a@b.c', password: 'pw', postal_code: 'H1H1H1', household_size: 2, dietary_preferences: ['vegan'] }
    );
  });

  it('logs in with urlencoded credentials', async () => {
    axios.post.mockResolvedValue({ data: { access_token: 't' } });
    await authService.login('a@b.c', 'pw');
    const [url, params, config] = axios.post.mock.calls[0];
    expect(url).toBe('http://localhost:8000/auth/login/access-token');
    expect(params.get('username')).toBe('a@b.c');
    expect(params.get('password')).toBe('pw');
    expect(config.headers['Content-Type']).toBe('application/x-www-form-urlencoded');
  });

  it('logout removes the stored user and getCurrentUser reads it back', () => {
    localStorage.setItem('user', JSON.stringify({ id: 1 }));
    expect(authService.getCurrentUser()).toEqual({ id: 1 });
    authService.logout();
    expect(localStorage.getItem('user')).toBeNull();
    expect(authService.getCurrentUser()).toBeNull();
  });
});
