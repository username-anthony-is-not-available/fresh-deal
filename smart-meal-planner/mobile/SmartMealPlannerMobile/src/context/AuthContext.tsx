// src/context/AuthContext.tsx
import React, {createContext, useContext, ReactNode} from 'react';

interface User {
  id: number;
  name: string;
}

interface AuthContextType {
  user: User | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({children}: {children: ReactNode}) => {
  // Placeholder for a real authentication logic
  const user: User = {id: 1, name: 'Demo User'};

  return (
    <AuthContext.Provider value={{user}}>{children}</AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
