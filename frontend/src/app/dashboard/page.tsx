"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Alert, Card, fmtDate, fmtScore, scoreTone, Spinner } from "@/components/ui";
import { api, ApiError, json } from "@/lib/api";
import { useAuth, useOn401, useRequireUser } from "@/lib/auth";
import type { Interview, InterviewSummary } from "@/lib/types";

export default function Dashboard() {
  const user = useRequireUser();
  const { meta, apiDown } = useAuth();
  const on401 = useOn401();
  const router = useRouter();
  const [recent, setRecent] = useState<InterviewSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!user) return;
    api<InterviewSummary[]>("/interviews")
      .then(setRecent)
      .catch((e) => {
        on401(e);
        setRecent([]);
      });
  }, [user, on401]);

  async function onStart(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setCreating(true);
    setError(null);
    try {
      const iv = await api<Interview>(
        "/interviews",
        json({ role: f.get("role"), level: f.get("level"), num_questions: Number(f.get("num_questions")) }),
      );
      router.push(`/interview/${iv.id}`);
    } catch (err) {
      on401(err);
      setError(err instanceof ApiError ? err.message : "Could not start the interview");
      setCreating(false);
    }
  }

  if (apiDown) return <Alert>{apiDown}</Alert>;
  if (!user || !meta) return <Spinner />;
  const inProgress = recent?.filter((r) => r.status === "in_progress") ?? [];
  const select =
    "rounded-lg border border-slate-300 bg-white px-3 py-2 dark:border-slate-600 dark:bg-slate-800 dark:text-white";

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Hi {user.name.split(" ")[0]}, ready to practise?</h1>

      <Card>
        <h2 className="mb-3 text-lg font-semibold">New mock interview</h2>
        <form onSubmit={onStart} className="grid gap-4 sm:grid-cols-[2fr_1fr_1fr_auto] sm:items-end">
          <label className="flex flex-col gap-1 text-sm">
            Job role
            <select name="role" className={select} defaultValue={meta.roles[0]}>
              {meta.roles.map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Level
            <select name="level" className={select} defaultValue="Junior">
              {meta.levels.map((l) => (
                <option key={l}>{l}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Questions
            <select name="num_questions" className={select} defaultValue={meta.default_questions}>
              {Array.from({ length: meta.max_questions - meta.min_questions + 1 }, (_, i) => meta.min_questions + i).map(
                (n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ),
              )}
            </select>
          </label>
          <button
            type="submit"
            disabled={creating}
            className="rounded-lg bg-indigo-600 px-5 py-2 font-medium text-white hover:bg-indigo-500 disabled:opacity-60"
          >
            {creating ? "Writing your questions…" : "Start interview"}
          </button>
        </form>
        {error && (
          <div className="mt-3">
            <Alert>{error}</Alert>
          </div>
        )}
        <p className="mt-3 text-xs text-slate-500">
          About half behavioural and half technical questions. You answer each one by voice (up to{" "}
          {Math.round(meta.max_answer_seconds / 60)} minutes).
        </p>
      </Card>

      {inProgress.length > 0 && (
        <Card>
          <h2 className="mb-2 text-lg font-semibold">Continue where you left off</h2>
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {inProgress.map((iv) => (
              <li key={iv.id} className="flex items-center justify-between py-2 text-sm">
                <span>
                  {iv.level} {iv.role} · {iv.answered_count}/{iv.question_count} answered · {fmtDate(iv.created_at)}
                </span>
                <Link className="font-medium text-indigo-600 hover:underline" href={`/interview/${iv.id}`}>
                  Continue
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Recent results</h2>
          <Link href="/progress" className="text-sm text-indigo-600 hover:underline">
            See progress
          </Link>
        </div>
        {recent === null ? (
          <Spinner />
        ) : recent.filter((r) => r.status === "completed").length === 0 ? (
          <p className="text-sm text-slate-500">No finished interviews yet. Your scores will show up here.</p>
        ) : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {recent
              .filter((r) => r.status === "completed")
              .slice(0, 5)
              .map((iv) => (
                <li key={iv.id} className="flex items-center justify-between py-2 text-sm">
                  <Link href={`/interview/${iv.id}/results`} className="hover:underline">
                    {iv.level} {iv.role} · {fmtDate(iv.completed_at)}
                  </Link>
                  <span className={`font-semibold tabular-nums ${scoreTone(iv.overall_score)}`}>
                    {fmtScore(iv.overall_score)}
                  </span>
                </li>
              ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
