import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, AuthenticationRequest } from './types';
import apiClient from './api';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (request: AuthenticationRequest) => Promise<void>;
  logout: () => void;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for existing token on mount
    const savedToken = apiClient.getToken();
    if (savedToken) {
      setToken(savedToken);
      // You might want to validate the token here or fetch user info
      // For now, we'll just mark as authenticated
    }
    setLoading(false);
  }, []);

  const login = async (request: AuthenticationRequest) => {
    try {
      const newToken = await apiClient.authenticate(request);
      setToken(newToken);
      setUser(request.user);
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  };

  const logout = () => {
    apiClient.logout();
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token,
        login,
        logout,
        loading,
      }}
    >
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