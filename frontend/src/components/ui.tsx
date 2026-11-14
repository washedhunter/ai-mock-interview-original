import type { ReactNode } from "react";

export function scoreTone(score: number | null | undefined): string {
  if (score == null) return "text-slate-400";
  if (score >= 75) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 55) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

export function fmtScore(score: number | null | undefined): string {
  return score == null ? "–" : String(Math.round(score));
}

export function Score({ label, value, big = false }: { label: string; value: number | null | undefined; big?: boolean }) {
  return (
    <div className="flex flex-col items-center rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/60">
      <span className={`${big ? "text-4xl" : "text-2xl"} font-semibold tabular-nums ${scoreTone(value)}`}>
        {fmtScore(value)}
      </span>
      <span className="text-xs text-slate-500">{label}</span>
    </div>
  );
}

export function Bar({ label, value, max = 10 }: { label: string; value: number; max?: number }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="w-24 shrink-0 text-slate-600 dark:text-slate-300">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
        <div className="h-full rounded-full bg-indigo-500" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-right tabular-nums text-slate-700 dark:text-slate-200">
        {value}/{max}
      </span>
    </div>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900 ${className}`}>
      {children}
    </section>
  );
}

export function Alert({ children, tone = "error" }: { children: ReactNode; tone?: "error" | "info" }) {
  const cls =
    tone === "error"
      ? "border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200"
      : "border-indigo-200 bg-indigo-50 text-indigo-900 dark:border-indigo-900 dark:bg-indigo-950 dark:text-indigo-200";
  return (
    <div role={tone === "error" ? "alert" : "status"} className={`rounded-lg border px-3 py-2 text-sm ${cls}`}>
      {children}
    </div>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-500" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600" aria-hidden />
      {label}
    </div>
  );
}

export function Tag({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300">
      {children}
    </span>
  );
}

export function fmtDate(iso: string | null): string {
  if (!iso) return "–";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
