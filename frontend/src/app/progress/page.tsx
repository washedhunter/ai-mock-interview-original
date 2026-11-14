"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Alert, Card, fmtScore, scoreTone, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useOn401, useRequireUser } from "@/lib/auth";
import type { Progress } from "@/lib/types";

const SERIES = {
  scores: [
    { key: "overall", name: "Overall", color: "#4f46e5" },
    { key: "content", name: "Content", color: "#059669" },
    { key: "clarity", name: "Clarity", color: "#d97706" },
  ],
  rubric: [
    { key: "relevance", name: "Relevance", color: "#4f46e5" },
    { key: "correctness", name: "Correctness", color: "#059669" },
    { key: "depth", name: "Depth", color: "#db2777" },
    { key: "structure", name: "Structure", color: "#0891b2" },
  ],
  kinds: [
    { key: "behavioural", name: "Behavioural", color: "#7c3aed" },
    { key: "technical", name: "Technical", color: "#0d9488" },
  ],
} as const;

function TrendChart({
  data,
  series,
  domain = [0, 100],
  testId,
}: {
  data: Record<string, unknown>[];
  series: readonly { key: string; name: string; color: string }[];
  domain?: [number, number];
  testId?: string;
}) {
  return (
    <div className="h-64 w-full" data-testid={testId}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis domain={domain} tick={{ fontSize: 12 }} />
          <Tooltip />
          <Legend />
          {series.map((s) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.name}
              stroke={s.color}
              strokeWidth={2}
              dot={{ r: 3 }}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function ProgressPage() {
  const user = useRequireUser();
  const on401 = useOn401();
  const [role, setRole] = useState<string>("");
  const [data, setData] = useState<Progress | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    const q = role ? `?role=${encodeURIComponent(role)}` : "";
    api<Progress>(`/progress${q}`)
      .then(setData)
      .catch((e) => {
        on401(e);
        setError("Could not load your progress.");
      });
  }, [user, role, on401]);

  if (error) return <Alert>{error}</Alert>;
  if (!user || !data) return <Spinner />;

  const points = data.points.map((p, i) => ({
    ...p,
    label: `#${i + 1} ${new Date(p.completed_at).toLocaleDateString(undefined, { day: "numeric", month: "short" })}`,
  }));

  return (
    <div className="flex flex-col gap-5" data-testid="progress">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Your progress</h1>
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          aria-label="Filter by role"
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-800"
        >
          <option value="">All roles</option>
          {data.roles_practised.map((r) => (
            <option key={r}>{r}</option>
          ))}
        </select>
      </div>

      {points.length === 0 ? (
        <Card>
          <p className="text-sm text-slate-500">
            Finish an interview to start tracking your progress.{" "}
            <Link href="/dashboard" className="text-indigo-600 hover:underline">
              Start one
            </Link>
            .
          </p>
        </Card>
      ) : (
        <>
          {data.by_role.length > 0 && !role && (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {data.by_role.map((r) => (
                <Card key={r.role}>
                  <p className="text-sm font-medium">{r.role}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {r.interviews} interview{r.interviews === 1 ? "" : "s"} · best{" "}
                    <span className={scoreTone(r.best_overall)}>{fmtScore(r.best_overall)}</span> · latest{" "}
                    <span className={scoreTone(r.latest_overall)}>{fmtScore(r.latest_overall)}</span>
                  </p>
                </Card>
              ))}
            </div>
          )}

          <Card>
            <h2 className="mb-2 font-semibold">Scores over time</h2>
            <TrendChart data={points} series={SERIES.scores} testId="chart-scores" />
          </Card>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <h2 className="mb-2 font-semibold">Content rubric</h2>
              <TrendChart data={points} series={SERIES.rubric} />
            </Card>
            <Card>
              <h2 className="mb-2 font-semibold">Behavioural vs technical</h2>
              <TrendChart data={points} series={SERIES.kinds} />
            </Card>
          </div>

          <Card className="overflow-x-auto">
            <h2 className="mb-2 font-semibold">By skill</h2>
            <table className="w-full text-sm" data-testid="skills-table">
              <thead className="text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-1">Skill</th>
                  <th className="py-1 text-right">First</th>
                  <th className="py-1 text-right">Latest</th>
                  <th className="py-1 text-right">Average</th>
                  <th className="py-1 text-right">Change</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {data.skills.map((s) => (
                  <tr key={s.skill}>
                    <td className="py-1.5">{s.skill}</td>
                    <td className="py-1.5 text-right tabular-nums">{fmtScore(s.first)}</td>
                    <td className={`py-1.5 text-right font-semibold tabular-nums ${scoreTone(s.latest)}`}>{fmtScore(s.latest)}</td>
                    <td className="py-1.5 text-right tabular-nums">{fmtScore(s.average)}</td>
                    <td
                      className={`py-1.5 text-right tabular-nums ${
                        s.change == null ? "text-slate-400" : s.change >= 0 ? "text-emerald-600" : "text-red-600"
                      }`}
                    >
                      {s.change == null ? "–" : `${s.change > 0 ? "+" : ""}${Math.round(s.change)}`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-xs text-slate-500">All on a 0–100 scale. Change = latest minus first interview.</p>
          </Card>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <h2 className="mb-2 font-semibold">Delivery</h2>
              <TrendChart
                data={points}
                domain={[0, 220]}
                series={[{ key: "wpm", name: "Words per minute", color: "#4f46e5" }]}
              />
              <TrendChart
                data={points}
                domain={[0, 15]}
                series={[{ key: "fillers_per_100", name: "Filler words per 100", color: "#d97706" }]}
              />
            </Card>
            <Card>
              <h2 className="mb-2 font-semibold">Question topics you&apos;ve practised</h2>
              <ul className="divide-y divide-slate-100 text-sm dark:divide-slate-800">
                {data.question_skills.map((q) => (
                  <li key={q.skill} className="flex justify-between py-1.5">
                    <span>
                      {q.skill} <span className="text-xs text-slate-500">({q.answers})</span>
                    </span>
                    <span className={`font-semibold tabular-nums ${scoreTone(q.average_overall)}`}>
                      {fmtScore(q.average_overall)}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
