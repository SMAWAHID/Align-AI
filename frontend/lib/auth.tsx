"use client";

/**
 * Session state for the whole app.
 *
 * The token lives in localStorage (see api-client), but the *user* is always
 * re-fetched from /auth/me on mount rather than cached alongside it — a stored
 * token can be expired or revoked, and trusting a cached profile would render a
 * signed-in shell that 401s on the first real request.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";

import {
  fetchMe,
  login as apiLogin,
  setToken,
  signup as apiSignup,
  getToken,
  type AuthUser,
} from "@/lib/api-client";

export type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  user: AuthUser | null;
  status: AuthStatus;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, fullName: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  useEffect(() => {
    let cancelled = false;

    if (!getToken()) {
      setStatus("anonymous");
      return;
    }

    fetchMe()
      .then((u) => {
        if (cancelled) return;
        setUser(u);
        setStatus("authenticated");
      })
      .catch(() => {
        if (cancelled) return;
        // Expired or revoked — drop it so the UI does not flicker signed-in.
        setToken(null);
        setUser(null);
        setStatus("anonymous");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const res = await apiLogin(email, password);
    setToken(res.access_token);
    setUser(res.user);
    setStatus("authenticated");
  }, []);

  const signUp = useCallback(
    async (email: string, password: string, fullName: string) => {
      const res = await apiSignup(email, password, fullName);
      setToken(res.access_token);
      setUser(res.user);
      setStatus("authenticated");
    },
    [],
  );

  const signOut = useCallback(() => {
    setToken(null);
    setUser(null);
    setStatus("anonymous");
  }, []);

  const value = useMemo(
    () => ({ user, status, signIn, signUp, signOut }),
    [user, status, signIn, signUp, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
