"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Alert, Card, fmtDate, fmtScore, scoreTone, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useOn401, useRequireUser } from "@/lib/auth";
import type { InterviewSummary } from "@/lib/types";

export default function History() {
  const user = useRequireUser();
  const on401 = useOn401();
  const [rows, setRows] = useState<InterviewSummary[] | null>(null);
  const [role, setRole] = useState("all");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    api<InterviewSummary[]>("/interviews")
      .then(setRows)
      .catch((e) => {
        on401(e);
        setError("Could not load your interviews.");
      });
  }, [user, on401]);

  const roles = useMemo(() => [...new Set((rows ?? []).map((r) => r.role))].sort(), [rows]);
  const shown = (rows ?? []).filter((r) => role === "all" || r.role === role);

  async function remove(iv: InterviewSummary) {
    if (!window.confirm(`Delete the ${iv.level} ${iv.role} interview from ${fmtDate(iv.created_at)}? This can't be undone.`))
      return;
    try {
      await api(`/interviews/${iv.id}`, { method: "DELETE" });
      setRows((prev) => prev?.filter((r) => r.id !== iv.id) ?? null);
    } catch (e) {
      on401(e);
      setError(e instanceof ApiError ? e.message : "Delete failed");
    }
  }

  if (!user || (!rows && !error)) return <Spinner />;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Interview history</h1>
        {roles.length > 1 && (
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            aria-label="Filter by role"
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-800"
          >
            <option value="all">All roles</option>
            {roles.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        )}
      </div>
      {error && <Alert>{error}</Alert>}
      <Card className="overflow-x-auto p-0">
        {shown.length === 0 ? (
          <p className="p-5 text-sm text-slate-500">
            No interviews yet. <Link href="/dashboard" className="text-indigo-600 hover:underline">Start one</Link>.
          </p>
        ) : (
          <table className="w-full text-sm" data-testid="history-table">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500 dark:bg-slate-800/60">
              <tr>
                <th className="px-4 py-2">Date</th>
                <th className="px-4 py-2">Role</th>
                <th className="px-4 py-2">Answered</th>
                <th className="px-4 py-2 text-right">Overall</th>
                <th className="px-4 py-2 text-right">Content</th>
                <th className="px-4 py-2 text-right">Clarity</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {shown.map((iv) => (
                <tr key={iv.id}>
                  <td className="whitespace-nowrap px-4 py-2">{fmtDate(iv.completed_at ?? iv.created_at)}</td>
                  <td className="px-4 py-2">
                    {iv.level} {iv.role}
                  </td>
                  <td className="px-4 py-2">
                    {iv.answered_count}/{iv.question_count}
                    {iv.status === "in_progress" && <span className="ml-2 text-xs text-amber-600">in progress</span>}
                  </td>
                  {[iv.overall_score, iv.content_score, iv.clarity_score].map((v, i) => (
                    <td key={i} className={`px-4 py-2 text-right font-semibold tabular-nums ${scoreTone(v)}`}>
                      {fmtScore(v)}
                    </td>
                  ))}
                  <td className="whitespace-nowrap px-4 py-2 text-right">
                    <Link
                      href={iv.status === "completed" ? `/interview/${iv.id}/results` : `/interview/${iv.id}`}
                      className="font-medium text-indigo-600 hover:underline"
                    >
                      {iv.status === "completed" ? "View" : "Continue"}
                    </Link>
                    <button type="button" onClick={() => remove(iv)} className="ml-3 text-slate-400 hover:text-red-600">
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
