"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import { api, ApiError } from "./api";
import type { Meta, User } from "./types";

type AuthState = {
  user: User | null;
  meta: Meta | null;
  loading: boolean;
  /** Set when the API can't be reached (not when the visitor is simply logged out). */
  apiDown: string | null;
  setUser: (u: User | null) => void;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiDown, setApiDown] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const down = "Can't reach the interview server right now. Please try again in a minute.";
    api<User>("/auth/me")
      .then((u) => alive && setUser(u))
      .catch((e) => {
        if (!alive) return;
        setUser(null);
        if (!(e instanceof ApiError && e.status === 401)) setApiDown(down);
      })
      .finally(() => alive && setLoading(false));
    api<Meta>("/meta")
      .then((m) => alive && setMeta(m))
      .catch(() => alive && setApiDown(down));
    return () => {
      alive = false;
    };
  }, []);

  const logout = useCallback(async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, meta, loading, apiDown, setUser, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** Redirects to /login when the visitor isn't signed in. Returns the user once known. */
export function useRequireUser(): User | null {
  const { user, loading, apiDown } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  useEffect(() => {
    if (!loading && !user && !apiDown) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [loading, user, apiDown, router, pathname]);
  return user;
}

/** Calls fn; on a 401 (session expired) sends the user to the login page. */
export function useOn401() {
  const { setUser } = useAuth();
  return useCallback(
    (err: unknown) => {
      if (err instanceof ApiError && err.status === 401) setUser(null);
    },
    [setUser],
  );
}
