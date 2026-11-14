import type { Question } from "@/lib/types";

import { Bar, Score, Tag } from "./ui";

export default function AnswerFeedback({ question }: { question: Question }) {
  const a = question.answer;
  if (!a) return null;
  const fb = a.feedback;
  return (
    <div className="flex flex-col gap-4" data-testid="answer-feedback">
      <div className="grid grid-cols-3 gap-2">
        <Score label="Overall" value={a.overall_score} />
        <Score label="Content" value={a.content_score} />
        <Score label="Clarity" value={a.clarity_score} />
      </div>
      {fb.summary && <p className="font-medium text-slate-800 dark:text-slate-100">{fb.summary}</p>}

      <div className="grid gap-4 md:grid-cols-2">
        <div className="flex flex-col gap-2">
          <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Content rubric</h4>
          <Bar label="Relevance" value={a.relevance} />
          <Bar label="Correctness" value={a.correctness} />
          <Bar label="Depth" value={a.depth} />
          <Bar label="Structure" value={a.structure} />
        </div>
        <div className="flex flex-col gap-1 text-sm">
          <h4 className="font-semibold text-slate-700 dark:text-slate-200">Delivery (from your audio)</h4>
          <ul className="list-disc space-y-1 pl-5 text-slate-600 dark:text-slate-300">
            {fb.clarity_notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
          <p className="mt-1 text-xs text-slate-500">
            Clarity {Math.round(a.clarity_score)} = 60% delivery metrics ({Math.round(a.clarity_computed)}) + 40% AI
            judgement of how easy it was to follow ({a.clarity_llm}/10).
          </p>
        </div>
      </div>

      {fb.clarity_feedback && <p className="text-sm text-slate-600 dark:text-slate-300">{fb.clarity_feedback}</p>}

      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <h4 className="text-sm font-semibold text-emerald-700 dark:text-emerald-400">What worked</h4>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700 dark:text-slate-200">
            {fb.strengths.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="text-sm font-semibold text-amber-700 dark:text-amber-400">To improve</h4>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700 dark:text-slate-200">
            {fb.improvements.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
      </div>

      <details className="rounded-lg bg-slate-50 p-3 text-sm dark:bg-slate-800/60">
        <summary className="cursor-pointer font-medium">Your transcript ({a.word_count} words)</summary>
        <p className="mt-2 whitespace-pre-wrap text-slate-700 dark:text-slate-200" data-testid="transcript">
          {a.transcript}
        </p>
        <p className="mt-2 text-xs text-slate-500">
          Transcribed by {a.transcriber}. The recording was {a.audio_kept ? "kept" : "deleted after transcription"}.
        </p>
      </details>

      {question.guidance && (
        <details className="rounded-lg bg-slate-50 p-3 text-sm dark:bg-slate-800/60">
          <summary className="cursor-pointer font-medium">What a strong answer covers</summary>
          <p className="mt-2 text-slate-700 dark:text-slate-200">{question.guidance}</p>
        </details>
      )}

      <details className="rounded-lg bg-indigo-50 p-3 text-sm dark:bg-indigo-950/50">
        <summary className="cursor-pointer font-medium text-indigo-900 dark:text-indigo-200">
          A stronger example answer
        </summary>
        <p className="mt-2 whitespace-pre-wrap text-slate-700 dark:text-slate-200">{a.example_answer}</p>
      </details>
      <div className="flex gap-2">
        <Tag>{question.kind}</Tag>
        <Tag>{question.skill}</Tag>
      </div>
    </div>
  );
}
