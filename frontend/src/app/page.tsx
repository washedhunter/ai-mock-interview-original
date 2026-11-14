import Link from "next/link";

const STEPS = [
  {
    title: "Pick a role and level",
    body: "Software, data, ML, DevOps or product roles, from intern to senior. Gemini writes a fresh mix of behavioural and technical questions.",
  },
  {
    title: "Answer out loud",
    body: "Record each answer in your browser. Whisper transcribes it with word timings; the audio is deleted straight after.",
  },
  {
    title: "Get scored feedback",
    body: "Content is scored against a rubric (relevance, correctness, depth, structure); clarity from your pace, filler words and pauses.",
  },
];

export default function Home() {
  return (
    <div className="flex flex-col gap-12 py-6">
      <section className="flex flex-col items-start gap-5">
        <h1 className="max-w-2xl text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl dark:text-white">
          Practise interviews out loud. Get feedback you can act on.
        </h1>
        <p className="max-w-xl text-lg text-slate-600 dark:text-slate-300">
          AI-generated questions for your target role, answered by voice, scored on what you said and how
          clearly you said it. Track your progress over time.
        </p>
        <div className="flex gap-3">
          <Link href="/signup" className="rounded-lg bg-indigo-600 px-5 py-2.5 font-medium text-white hover:bg-indigo-500">
            Start practising
          </Link>
          <Link
            href="/login"
            className="rounded-lg border border-slate-300 px-5 py-2.5 font-medium text-slate-700 hover:bg-white dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-900"
          >
            Log in
          </Link>
        </div>
      </section>
      <section className="grid gap-4 sm:grid-cols-3">
        {STEPS.map((s, i) => (
          <div key={s.title} className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
            <div className="mb-2 flex h-8 w-8 items-center justify-center rounded-full bg-indigo-100 font-semibold text-indigo-700 dark:bg-indigo-900 dark:text-indigo-200">
              {i + 1}
            </div>
            <h2 className="font-semibold">{s.title}</h2>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{s.body}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
