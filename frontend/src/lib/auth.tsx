"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import { api, ApiError } from "./api";
import type { Meta, User } from "./types";

type AuthState = {
  user: User | null;
  meta: Meta | null;
  loading: boolean;
  setUser: (u: User | null) => void;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api<User>("/auth/me")
      .then((u) => alive && setUser(u))
      .catch(() => alive && setUser(null))
      .finally(() => alive && setLoading(false));
    api<Meta>("/meta")
      .then((m) => alive && setMeta(m))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  const logout = useCallback(async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, meta, loading, setUser, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** Redirects to /login when the visitor isn't signed in. Returns the user once known. */
export function useRequireUser(): User | null {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  useEffect(() => {
    if (!loading && !user) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [loading, user, router, pathname]);
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
