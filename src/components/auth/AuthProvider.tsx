"use client";

import type { ReactNode } from "react";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { ApiError } from "@/lib/api/errors";
import * as authApi from "@/lib/api/auth";
import type { CurrentUser } from "@/lib/api/types";

interface AuthContextValue {
  user: CurrentUser | null;
  loading: boolean;
  error: string | null;
  refreshUser: () => Promise<void>;
  login: (username: string, password: string) => Promise<CurrentUser>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshUser = useCallback(async () => {
    setLoading(true);
    try {
      const response = await authApi.getCurrentUser();
      setUser(response.user);
      setError(null);
    } catch (caught) {
      setUser(null);
      if (caught instanceof ApiError && caught.status === 401) {
        setError(null);
      } else {
        setError(caught instanceof Error ? caught.message : "无法读取当前用户");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void refreshUser();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [refreshUser]);

  const login = useCallback(async (username: string, password: string) => {
    const response = await authApi.login(username, password);
    setUser(response.user);
    setError(null);
    return response.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      setUser(null);
    }
  }, []);

  const value = useMemo(
    () => ({ user, loading, error, refreshUser, login, logout }),
    [error, loading, login, logout, refreshUser, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return value;
}
