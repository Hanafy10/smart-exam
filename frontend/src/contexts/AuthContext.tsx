'use client';
import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { User } from '@/lib/types';
import {
  login as apiLogin,
  getCurrentUser,
  refreshToken as apiRefreshToken,
  registerAuthRefresh,
  isTokenExpired,
  getTokenRemainingMs,
  triggerTokenRefresh,
} from '@/lib/api';

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [refreshTokenStr, setRefreshTokenStr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    setToken(null);
    setRefreshTokenStr(null);
    setUser(null);
    if (typeof window !== 'undefined') {
      localStorage.removeItem('smartexam_token');
      localStorage.removeItem('smartexam_refresh_token');
      localStorage.removeItem('smartexam_user');
    }
  }, []);

  const handleTokenRefresh = useCallback(async (): Promise<string | null> => {
    const currentRefresh = typeof window !== 'undefined' ? localStorage.getItem('smartexam_refresh_token') : null;
    if (!currentRefresh || isTokenExpired(currentRefresh, 0)) {
      logout();
      return null;
    }
    try {
      const data = await apiRefreshToken(currentRefresh);
      setToken(data.access_token);
      setRefreshTokenStr(data.refresh_token);
      localStorage.setItem('smartexam_token', data.access_token);
      localStorage.setItem('smartexam_refresh_token', data.refresh_token);
      return data.access_token;
    } catch {
      logout();
      return null;
    }
  }, [logout]);

  useEffect(() => {
    registerAuthRefresh(handleTokenRefresh);
  }, [handleTokenRefresh]);

  useEffect(() => {
    let cancelled = false;

    async function initAuth() {
      registerAuthRefresh(handleTokenRefresh);
      const storedToken = localStorage.getItem('smartexam_token');
      const storedRefresh = localStorage.getItem('smartexam_refresh_token');
      const storedUser = localStorage.getItem('smartexam_user');

      if (storedToken && storedUser) {
        try {
          const parsedUser: User = JSON.parse(storedUser);
          if (!isTokenExpired(storedToken)) {
            if (!cancelled) {
              setToken(storedToken);
              setRefreshTokenStr(storedRefresh);
              setUser(parsedUser);
            }
          } else if (storedRefresh && !isTokenExpired(storedRefresh, 0)) {
            const refreshedToken = await triggerTokenRefresh();
            if (!cancelled && refreshedToken) {
              setUser(parsedUser);
            }
          } else {
            if (!cancelled) {
              logout();
            }
          }
        } catch {
          if (!cancelled) {
            logout();
          }
        }
      } else if (storedToken || storedRefresh || storedUser) {
        if (!cancelled) {
          logout();
        }
      }

      if (!cancelled) {
        setLoading(false);
      }
    }

    initAuth();
    return () => {
      cancelled = true;
    };
  }, [handleTokenRefresh, logout]);

  useEffect(() => {
    if (!token) return;
    const remainingMs = getTokenRemainingMs(token);
    if (remainingMs <= 0) return;
    const refreshDelay = Math.max(5000, remainingMs - 60000);
    const timer = setTimeout(() => {
      triggerTokenRefresh();
    }, refreshDelay);
    return () => clearTimeout(timer);
  }, [token]);

  const login = async (username: string, password: string): Promise<User> => {
    const data = await apiLogin(username, password);
    localStorage.setItem('smartexam_token', data.access_token);
    localStorage.setItem('smartexam_refresh_token', data.refresh_token);
    setToken(data.access_token);
    setRefreshTokenStr(data.refresh_token);

    const userData = await getCurrentUser(data.access_token);
    setUser(userData);
    localStorage.setItem('smartexam_user', JSON.stringify(userData));
    return userData;
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
