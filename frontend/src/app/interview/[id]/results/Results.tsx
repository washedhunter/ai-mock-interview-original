"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import AnswerFeedback from "@/components/AnswerFeedback";
import { Alert, Card, fmtDate, fmtScore, Score, scoreTone, Spinner, Tag } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useOn401, useRequireUser } from "@/lib/auth";
import type { Interview } from "@/lib/types";

export default function Results() {
  const { id } = useParams<{ id: string }>();
  const user = useRequireUser();
  const on401 = useOn401();
  const router = useRouter();
  const [iv, setIv] = useState<Interview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    api<Interview>(`/interviews/${id}`)
      .then((data) => {
        if (data.status !== "completed") router.replace(`/interview/${id}`);
        else setIv(data);
      })
      .catch((e) => {
        on401(e);
        setError(e instanceof ApiError && e.status === 404 ? "Interview not found." : "Could not load the results.");
      });
  }, [id, user, router, on401]);

  if (error) return <Alert>{error}</Alert>;
  if (!iv) return <Spinner label="Loading results…" />;
  const s = iv.summary;

  return (
    <div className="flex flex-col gap-5" data-testid="results">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">
            {iv.level} {iv.role}: results
          </h1>
          <p className="text-sm text-slate-500">
            {fmtDate(iv.completed_at)} · {iv.answered_count} of {iv.question_count} answered
          </p>
        </div>
        <div className="flex gap-3 text-sm">
          <Link href="/history" className="text-indigo-600 hover:underline">
            All interviews
          </Link>
          <Link href="/progress" className="text-indigo-600 hover:underline">
            Progress
          </Link>
        </div>
      </div>

      <Card>
        <div className="grid grid-cols-3 gap-3">
          <Score label="Overall" value={iv.overall_score} big />
          <Score label="Content" value={iv.content_score} big />
          <Score label="Clarity" value={iv.clarity_score} big />
        </div>
        {s && (
          <div className="mt-5 flex flex-col gap-4">
            <p className="text-slate-800 dark:text-slate-100" data-testid="summary">
              {s.summary}
            </p>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <h2 className="text-sm font-semibold text-emerald-700 dark:text-emerald-400">Strengths</h2>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
                  {s.strengths.map((x) => (
                    <li key={x}>{x}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h2 className="text-sm font-semibold text-amber-700 dark:text-amber-400">Practise next</h2>
                <ol className="mt-1 list-decimal space-y-1 pl-5 text-sm">
                  {s.priorities.map((x) => (
                    <li key={x}>{x}</li>
                  ))}
                </ol>
              </div>
            </div>
            {s.skipped_questions > 0 && (
              <p className="text-xs text-slate-500">{s.skipped_questions} question(s) were skipped and aren&apos;t scored.</p>
            )}
          </div>
        )}
      </Card>

      {iv.questions.map((q) => (
        <details key={q.id} className="group rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
          <summary className="flex cursor-pointer items-center gap-3 p-4">
            <span className="text-sm font-medium text-slate-500">Q{q.position}</span>
            <span className="flex-1 font-medium">{q.text}</span>
            <Tag>{q.kind}</Tag>
            <span className={`w-10 text-right font-semibold tabular-nums ${scoreTone(q.answer?.overall_score)}`}>
              {q.answer ? fmtScore(q.answer.overall_score) : "skipped"}
            </span>
          </summary>
          <div className="border-t border-slate-100 p-4 dark:border-slate-800">
            {q.answer ? (
              <AnswerFeedback question={q} />
            ) : (
              <p className="text-sm text-slate-500">Not answered. {q.guidance && <>A strong answer covers: {q.guidance}</>}</p>
            )}
          </div>
        </details>
      ))}
    </div>
  );
}
