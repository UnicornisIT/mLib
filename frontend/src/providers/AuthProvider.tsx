"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { AuthStatus, PasswordChange, User, UserProfileUpdate } from "@/lib/types";

type SetupPayload = { username: string; password: string; library_path?: string; import_path?: string };
type AuthContextValue = {
  user: User | null;
  loading: boolean;
  setupRequired: boolean;
  login: (username: string, password: string) => Promise<void>;
  setup: (payload: SetupPayload) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  updateProfile: (payload: UserProfileUpdate) => Promise<User>;
  changePassword: (payload: PasswordChange) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [setupRequired, setSetupRequired] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const status = await api<AuthStatus>("/auth/status");
      setSetupRequired(status.setup_required);
      if (status.authenticated) setUser(await api<User>("/auth/me"));
      else setUser(null);
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 401)) console.error(error);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Initial authentication check synchronizes the client with the server session.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      setupRequired,
      refresh,
      login: async (username, password) => {
        const authenticated = await api<User>("/auth/login", { method: "POST", body: { username, password } });
        setUser(authenticated);
      },
      setup: async (payload) => {
        const authenticated = await api<User>("/auth/setup", { method: "POST", body: payload });
        setUser(authenticated);
        setSetupRequired(false);
      },
      logout: async () => {
        await api<void>("/auth/logout", { method: "POST" });
        setUser(null);
      },
      updateProfile: async (payload) => {
        const updated = await api<User>("/auth/me", { method: "PATCH", body: payload });
        setUser(updated);
        return updated;
      },
      changePassword: async (payload) => {
        await api<void>("/auth/me/password", { method: "PUT", body: payload });
      },
    }),
    [loading, refresh, setupRequired, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
