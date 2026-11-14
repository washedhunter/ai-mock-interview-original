"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import AnswerFeedback from "@/components/AnswerFeedback";
import Recorder from "@/components/Recorder";
import { Alert, Card, Spinner, Tag } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth, useOn401, useRequireUser } from "@/lib/auth";
import type { Interview, Question } from "@/lib/types";

export default function InterviewSession() {
  const { id } = useParams<{ id: string }>();
  const user = useRequireUser();
  const { meta, apiDown } = useAuth();
  const on401 = useOn401();
  const router = useRouter();
  const [iv, setIv] = useState<Interview | null>(null);
  const [current, setCurrent] = useState(0);
  const [reanswering, setReanswering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [finishing, setFinishing] = useState(false);
  const [recorderBusy, setRecorderBusy] = useState(false);

  useEffect(() => {
    if (!user) return;
    let alive = true;
    api<Interview>(`/interviews/${id}`)
      .then((data) => {
        if (!alive) return;
        if (data.status === "completed") {
          router.replace(`/interview/${id}/results`);
          return;
        }
        setIv(data);
        const firstOpen = data.questions.findIndex((q) => !q.answer);
        setCurrent(firstOpen === -1 ? data.questions.length - 1 : firstOpen);
      })
      .catch((e) => {
        on401(e);
        if (alive) setError(e instanceof ApiError && e.status === 404 ? "Interview not found." : String(e.message ?? e));
      });
    return () => {
      alive = false;
    };
  }, [id, user, router, on401]);

  const submitAnswer = useCallback(
    async (q: Question, blob: Blob, filename: string) => {
      const form = new FormData();
      form.append("audio", blob, filename);
      try {
        const updated = await api<Question>(`/interviews/${id}/questions/${q.id}/answer`, {
          method: "POST",
          body: form,
        });
        setIv((prev) =>
          prev ? { ...prev, questions: prev.questions.map((x) => (x.id === updated.id ? updated : x)) } : prev,
        );
        setReanswering(false);
      } catch (e) {
        on401(e);
        throw e;
      }
    },
    [id, on401],
  );

  async function finish() {
    if (!iv) return;
    const open = iv.questions.filter((q) => !q.answer).length;
    if (open > 0 && !window.confirm(`${open} question(s) are unanswered and will be skipped. Finish anyway?`)) return;
    setFinishing(true);
    setError(null);
    try {
      await api<Interview>(`/interviews/${id}/complete`, { method: "POST" });
      router.push(`/interview/${id}/results`);
    } catch (e) {
      on401(e);
      setError(e instanceof ApiError ? e.message : "Could not finish the interview");
      setFinishing(false);
    }
  }

  if (error && !iv) return <Alert>{error}</Alert>;
  if (apiDown) return <Alert>{apiDown}</Alert>;
  if (!iv || !meta) return <Spinner label="Loading interview…" />;

  const q = iv.questions[current];
  const answered = iv.questions.filter((x) => x.answer).length;
  const isLast = current === iv.questions.length - 1;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">
            {iv.level} {iv.role}
          </h1>
          <p className="text-sm text-slate-500">
            {answered} of {iv.questions.length} answered
          </p>
        </div>
        <ol className="flex gap-1" aria-label="Questions">
          {iv.questions.map((x, i) => (
            <li key={x.id}>
              <button
                type="button"
                onClick={() => {
                  setCurrent(i);
                  setReanswering(false);
                }}
                disabled={recorderBusy}
                aria-current={i === current ? "step" : undefined}
                aria-label={`Question ${i + 1}${x.answer ? " (answered)" : ""}`}
                className={`h-8 w-8 rounded-full text-sm font-medium ${
                  i === current
                    ? "bg-indigo-600 text-white"
                    : x.answer
                      ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200"
                      : "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                }`}
              >
                {x.answer && i !== current ? "✓" : i + 1}
              </button>
            </li>
          ))}
        </ol>
      </div>

      <Card>
        <div className="mb-2 flex items-center gap-2">
          <span className="text-sm font-medium text-slate-500">
            Question {current + 1} of {iv.questions.length}
          </span>
          <Tag>{q.kind}</Tag>
          <Tag>{q.skill}</Tag>
        </div>
        <p className="text-xl font-medium leading-relaxed text-slate-900 dark:text-white" data-testid="question-text">
          {q.text}
        </p>
      </Card>

      {q.answer && !reanswering ? (
        <Card>
          <AnswerFeedback question={q} />
          <div className="mt-5 flex flex-wrap gap-2">
            {!isLast && (
              <button
                type="button"
                onClick={() => setCurrent(current + 1)}
                className="rounded-lg bg-indigo-600 px-4 py-2 font-medium text-white hover:bg-indigo-500"
              >
                Next question
              </button>
            )}
            <button
              type="button"
              onClick={() => setReanswering(true)}
              className="rounded-lg border border-slate-300 px-4 py-2 text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              Answer again
            </button>
          </div>
        </Card>
      ) : (
        <>
          <Recorder
            key={`${q.id}-${reanswering}`}
            maxSeconds={meta.max_answer_seconds}
            onSubmit={(blob, filename) => submitAnswer(q, blob, filename)}
            onBusyChange={setRecorderBusy}
          />
          {reanswering && (
            <button type="button" onClick={() => setReanswering(false)} className="self-start text-sm text-slate-500 hover:underline">
              Cancel and keep my earlier answer
            </button>
          )}
        </>
      )}

      {error && <Alert>{error}</Alert>}

      <div className="flex justify-end border-t border-slate-200 pt-4 dark:border-slate-800">
        <button
          type="button"
          onClick={finish}
          disabled={answered === 0 || finishing || recorderBusy}
          title={recorderBusy ? "Wait until the current answer is recorded and scored" : undefined}
          className={`rounded-lg px-5 py-2 font-medium disabled:opacity-50 ${
            answered === iv.questions.length
              ? "bg-emerald-600 text-white hover:bg-emerald-500"
              : "border border-slate-300 text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
          }`}
        >
          {finishing ? "Writing your debrief…" : "Finish interview"}
        </button>
      </div>
    </div>
  );
}
