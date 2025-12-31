// src/context/AuthContext.tsx
import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {jwtDecode} from 'jwt-decode';
import * as authService from '../services/auth';
import apiClient from '../services/apiClient';

interface User {
  id: number;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (email, password) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({children}: {children: ReactNode}) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadToken = async () => {
      try {
        const storedToken = await AsyncStorage.getItem('userToken');
        if (storedToken) {
          const decoded: {sub: string} = jwtDecode(storedToken);
          setUser({id: parseInt(decoded.sub, 10)});
          setToken(storedToken);
          apiClient.setToken(storedToken);
        }
      } catch (e) {
        console.error('Failed to load token from storage', e);
      } finally {
        setIsLoading(false);
      }
    };

    loadToken();
  }, []);

  const login = async (email, password) => {
    const data = await authService.login(email, password);
    const {access_token} = data;
    const decoded: {sub: string} = jwtDecode(access_token);
    setUser({id: parseInt(decoded.sub, 10)});
    setToken(access_token);
    apiClient.setToken(access_token);
    await AsyncStorage.setItem('userToken', access_token);
  };

  const logout = async () => {
    setUser(null);
    setToken(null);
    apiClient.setToken(null);
    await AsyncStorage.removeItem('userToken');
  };

  return (
    <AuthContext.Provider value={{user, token, login, logout, isLoading}}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
