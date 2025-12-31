// src/context/__mocks__/AuthContext.tsx
import React, {createContext, useContext, ReactNode} from 'react';

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
  const user: User = {id: 1};
  const token = 'mock-token';

  const login = async (email, password) => {};
  const logout = () => {};

  return (
    <AuthContext.Provider
      value={{user, token, login, logout, isLoading: false}}>
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
