"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth";

const LINKS = [
  { href: "/dashboard", label: "Practice" },
  { href: "/history", label: "History" },
  { href: "/progress", label: "Progress" },
];

export default function Nav() {
  const { user, meta, apiDown, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  return (
    <header className="border-b border-slate-200 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
      {apiDown && (
        <div role="alert" className="bg-red-100 px-4 py-2 text-center text-sm text-red-900 dark:bg-red-950 dark:text-red-200">
          {apiDown}{" "}
          <button type="button" className="font-medium underline" onClick={() => window.location.reload()}>
            Retry
          </button>
        </div>
      )}
      {meta?.ai_mode === "demo" && (
        <div className="bg-amber-100 px-4 py-1 text-center text-xs text-amber-900 dark:bg-amber-900/40 dark:text-amber-200" data-testid="demo-banner">
          Demo mode: questions and feedback are canned because no Gemini API key is configured. Transcription and
          delivery metrics are real.
        </div>
      )}
      <nav className="mx-auto flex max-w-5xl items-center gap-4 px-4 py-3">
        <Link href={user ? "/dashboard" : "/"} className="font-semibold text-slate-900 dark:text-white">
          Mock<span className="text-indigo-600">Interview</span>
        </Link>
        {user && (
          <div className="flex items-center gap-1 text-sm">
            {LINKS.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={`rounded-md px-2 py-1 ${
                  pathname.startsWith(l.href)
                    ? "bg-slate-100 font-medium text-slate-900 dark:bg-slate-800 dark:text-white"
                    : "text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white"
                }`}
              >
                {l.label}
              </Link>
            ))}
          </div>
        )}
        <div className="ml-auto flex items-center gap-3 text-sm">
          {user ? (
            <>
              <span className="hidden text-slate-500 sm:inline">{user.name}</span>
              <button
                type="button"
                onClick={async () => {
                  await logout();
                  router.push("/login");
                }}
                className="rounded-md border border-slate-300 px-2 py-1 text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                Log out
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="text-slate-600 hover:text-slate-900 dark:text-slate-300">
                Log in
              </Link>
              <Link href="/signup" className="rounded-md bg-indigo-600 px-3 py-1.5 font-medium text-white hover:bg-indigo-500">
                Sign up
              </Link>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}
