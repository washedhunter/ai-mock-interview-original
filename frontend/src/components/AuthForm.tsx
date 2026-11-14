"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { api, ApiError, json } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { User } from "@/lib/types";

import { Alert, Card } from "./ui";

function safeNext(next: string | null): string {
  // Only same-site paths: never redirect to another origin.
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
}

export default function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const { user, setUser } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) router.replace(next);
  }, [user, next, router]);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, string> = {
        email: String(form.get("email") ?? ""),
        password: String(form.get("password") ?? ""),
      };
      if (mode === "signup") body.name = String(form.get("name") ?? "");
      const u = await api<User>(`/auth/${mode}`, json(body));
      setUser(u);
      router.replace(next);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  const input =
    "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200 dark:border-slate-600 dark:bg-slate-800 dark:text-white";

  return (
    <div className="mx-auto max-w-sm">
      <Card>
        <h1 className="mb-4 text-xl font-semibold">{mode === "login" ? "Log in" : "Create your account"}</h1>
        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          {mode === "signup" && (
            <label className="flex flex-col gap-1 text-sm">
              Name
              <input name="name" required maxLength={100} autoComplete="name" className={input} />
            </label>
          )}
          <label className="flex flex-col gap-1 text-sm">
            Email
            <input name="email" type="email" required autoComplete="email" className={input} />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Password
            <input
              name="password"
              type="password"
              required
              minLength={mode === "signup" ? 8 : 1}
              maxLength={128}
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
              className={input}
            />
            {mode === "signup" && <span className="text-xs text-slate-500">At least 8 characters.</span>}
          </label>
          {error && <Alert>{error}</Alert>}
          <button
            type="submit"
            disabled={busy}
            className="mt-1 rounded-lg bg-indigo-600 px-4 py-2 font-medium text-white hover:bg-indigo-500 disabled:opacity-60"
          >
            {busy ? "Please wait…" : mode === "login" ? "Log in" : "Sign up"}
          </button>
        </form>
        <p className="mt-4 text-sm text-slate-500">
          {mode === "login" ? (
            <>
              No account?{" "}
              <Link className="text-indigo-600 hover:underline" href={`/signup?next=${encodeURIComponent(next)}`}>
                Sign up
              </Link>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <Link className="text-indigo-600 hover:underline" href={`/login?next=${encodeURIComponent(next)}`}>
                Log in
              </Link>
            </>
          )}
        </p>
      </Card>
    </div>
  );
}
