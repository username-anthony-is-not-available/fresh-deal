// src/context/__tests__/AuthContext.test.tsx
import {renderHook, act} from '@testing-library/react-native';
import {AuthProvider, useAuth} from '../AuthContext';
import * as authService from '../../services/auth';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Mock the auth service
jest.mock('../../services/auth');
const mockedAuthService = authService as jest.Mocked<typeof authService>;

const mockToken =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.sytj9f5fT0w7g6a_t-qZ7-a_f3f3f3f3f3f3f3f3';

describe('AuthContext', () => {
  beforeEach(() => {
    // Clear all mocks before each test
    jest.clearAllMocks();
    (AsyncStorage.clear as jest.Mock)();
  });

  it('should log in a user and store the token', async () => {
    mockedAuthService.login.mockResolvedValueOnce({access_token: mockToken});

    const {result} = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await act(async () => {
      await result.current.login('test@example.com', 'password');
    });

    expect(result.current.user).toEqual({id: 1});
    expect(result.current.token).toBe(mockToken);
    expect(AsyncStorage.setItem).toHaveBeenCalledWith('userToken', mockToken);
  });

  it('should load a user from storage on startup', async () => {
    (AsyncStorage.getItem as jest.Mock).mockResolvedValueOnce(mockToken);

    const {result, waitForNextUpdate} = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await act(async () => {
      await waitForNextUpdate();
    });

    expect(result.current.user).toEqual({id: 1});
    expect(result.current.token).toBe(mockToken);
  });

  it('should log out a user and clear the token', async () => {
    // First, log in the user
    mockedAuthService.login.mockResolvedValueOnce({access_token: mockToken});

    const {result} = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await act(async () => {
      await result.current.login('test@example.com', 'password');
    });

    expect(result.current.user).not.toBeNull();

    // Then, log out
    await act(async () => {
      result.current.logout();
    });

    expect(result.current.user).toBeNull();
    expect(result.current.token).toBeNull();
    expect(AsyncStorage.removeItem).toHaveBeenCalledWith('userToken');
  });
});
