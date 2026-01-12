'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  TokenData,
  getTokens,
  saveTokens,
  clearAuth,
  clearClientCredentials,
  isTokenExpired,
  saveClientCredentials,
  getClientCredentials,
  initializeAuth
} from '@/lib/auth';
import { API_URL } from '@/lib/api-v2';

// Default credentials - must match backend (main.py)
export const DEFAULT_CLIENT_ID = 'vas-portal';
export const DEFAULT_CLIENT_SECRET = 'vas-portal-secret-2024';

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  tokens: TokenData | null;
  clientId: string | null;
  login: (clientId: string, clientSecret: string) => Promise<boolean>;
  loginWithDefaults: () => Promise<boolean>;
  logout: () => void;
  getAccessToken: () => string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

/**
 * Validate token by making a lightweight API call
 * Returns true if token is valid, false otherwise
 */
async function validateTokenWithBackend(token: string): Promise<boolean> {
  try {
    // Use a lightweight endpoint to validate token
    const response = await fetch(`${API_URL}/v2/streams?limit=1`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });
    return response.ok || response.status !== 401;
  } catch {
    // Network error - assume token might be valid, let actual calls fail
    return true;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [tokens, setTokens] = useState<TokenData | null>(null);
  const [clientId, setClientId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Auto-login with default credentials
  const loginWithDefaultCredentials = async (): Promise<boolean> => {
    console.log('Attempting auto-login with default credentials...');
    const apiUrl = API_URL;
    const success = await initializeAuth(apiUrl, DEFAULT_CLIENT_ID, DEFAULT_CLIENT_SECRET);
    if (success) {
      setTokens(getTokens());
      setClientId(DEFAULT_CLIENT_ID);
      console.log('Auto-login successful with default credentials');
      return true;
    }
    console.log('Auto-login failed - backend may not have default client seeded');
    return false;
  };

  // Load tokens from localStorage on mount and VALIDATE with backend
  useEffect(() => {
    const loadAuth = async () => {
      const storedTokens = getTokens();
      const credentials = getClientCredentials();

      if (storedTokens && !isTokenExpired(storedTokens)) {
        // Token exists and not expired - validate with backend
        const isValid = await validateTokenWithBackend(storedTokens.access_token);
        if (isValid) {
          setTokens(storedTokens);
          setClientId(credentials?.clientId || null);
        } else {
          // Token rejected by backend (stale after rebuild) - try auto-login
          console.log('Stored token rejected by backend - attempting auto-login');
          clearAuth();
          clearClientCredentials();
          await loginWithDefaultCredentials();
        }
      } else if (storedTokens && credentials) {
        // Token expired, try to refresh using stored credentials
        const apiUrl = API_URL;
        const success = await initializeAuth(apiUrl, credentials.clientId, credentials.clientSecret);
        if (success) {
          setTokens(getTokens());
          setClientId(credentials.clientId);
        } else {
          // Refresh failed - try auto-login with defaults
          console.log('Token refresh failed - attempting auto-login');
          clearAuth();
          clearClientCredentials();
          await loginWithDefaultCredentials();
        }
      } else {
        // No stored credentials - try auto-login with defaults
        await loginWithDefaultCredentials();
      }

      setIsLoading(false);
    };

    loadAuth();
  }, []);

  // Auto-refresh token before expiry
  useEffect(() => {
    if (!tokens) return;

    const refreshInterval = setInterval(async () => {
      if (isTokenExpired(tokens)) {
        const credentials = getClientCredentials();
        if (credentials) {
          const apiUrl = API_URL;
          const success = await initializeAuth(apiUrl, credentials.clientId, credentials.clientSecret);
          if (success) {
            setTokens(getTokens());
          } else {
            logout();
          }
        } else {
          logout();
        }
      }
    }, 60000); // Check every minute

    return () => clearInterval(refreshInterval);
  }, [tokens]);

  const login = async (newClientId: string, clientSecret: string): Promise<boolean> => {
    setIsLoading(true);
    try {
      const apiUrl = API_URL;
      const success = await initializeAuth(apiUrl, newClientId, clientSecret);

      if (success) {
        const newTokens = getTokens();
        setTokens(newTokens);
        setClientId(newClientId);
        return true;
      }
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const loginWithDefaults = async (): Promise<boolean> => {
    setIsLoading(true);
    try {
      return await loginWithDefaultCredentials();
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    clearAuth();
    clearClientCredentials();
    setTokens(null);
    setClientId(null);
  };

  const getAccessToken = (): string | null => {
    if (!tokens || isTokenExpired(tokens)) {
      return null;
    }
    return tokens.access_token;
  };

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated: !!tokens && !isTokenExpired(tokens),
        isLoading,
        tokens,
        clientId,
        login,
        loginWithDefaults,
        logout,
        getAccessToken
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
