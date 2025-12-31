// src/services/__tests__/apiClient.test.ts
import apiClient from '../apiClient';

// Mock the global fetch function
global.fetch = jest.fn();

const mockFetch = fetch as jest.Mock;

describe('apiClient', () => {
  beforeEach(() => {
    mockFetch.mockClear();
    apiClient.setToken(null); // Reset token before each test
  });

  it('should make a GET request without a token', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({data: 'test'}),
    });

    await apiClient.get('/test');

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/test'),
      expect.objectContaining({
        method: 'GET',
        headers: expect.any(Headers),
      }),
    );
    const headers = mockFetch.mock.calls[0][1].headers as Headers;
    expect(headers.has('Authorization')).toBe(false);
  });

  it('should make a GET request with a token', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({data: 'test'}),
    });

    apiClient.setToken('test-token');
    await apiClient.get('/test');

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/test'),
      expect.objectContaining({
        method: 'GET',
        headers: expect.any(Headers),
      }),
    );
    const headers = mockFetch.mock.calls[0][1].headers as Headers;
    expect(headers.get('Authorization')).toBe('Bearer test-token');
  });

  it('should throw an error on a failed request', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
    });

    await expect(apiClient.get('/test')).rejects.toThrow('HTTP error! status: 404');
  });
});
