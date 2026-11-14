# Design decisions

Plain-English notes on why the project is built the way it is, and what else was considered.

## Architecture: Next.js frontend, FastAPI backend, PostgreSQL

- **Why two services.** The speech-to-text model (Whisper) and the AI calls are Python-first, so the
  backend is Python (FastAPI). The UI needs a modern React app with good TypeScript support, so the
  frontend is Next.js. Each scales and deploys on its own.
- **Why the browser never talks to the backend directly.** Every `/api/*` request goes to a
  Next.js route handler (`frontend/src/app/api/[...path]/route.ts`) that forwards it to FastAPI.
  The browser sees one origin, so the session cookie is a plain first-party, httpOnly cookie and
  there's no CORS to configure. The backend URL is read at request time, so the same image runs
  locally, in CI and in production. *Alternative:* Next.js `rewrites` – rejected because they are
  fixed at build time in a standalone build.
- **Why PostgreSQL + SQLAlchemy + Alembic.** Relational data (users → interviews → questions →
  answers) with real foreign keys and cascades. Alembic keeps schema changes versioned; a test
  checks that the migrations produce exactly the schema the models describe.

## Interview flow

1. Gemini writes the question set as structured JSON (half behavioural, half technical, one skill
   each, plus "what a good answer covers").
2. The user records each answer in the browser (MediaRecorder: webm/opus in Chrome/Firefox,
   mp4 in Safari) and uploads it.
3. The backend saves the upload to a temp file, transcribes it with Whisper (word timestamps),
   **deletes the audio**, computes delivery metrics, and asks Gemini to score the content.
4. Feedback appears immediately for that question; "Finish" adds an overall debrief.

*Why score each answer immediately instead of at the end:* the user learns as they go, a failure
only costs one answer, and each request stays short (3.5–12 s measured).

*Why synchronous requests instead of a job queue:* one request per answer that finishes in seconds
doesn't need Celery/Redis. A queue would be the next step if answers got much longer or the host
much slower (see Limitations in the README).

## Scoring

- **Content (Gemini, 0–100).** A fixed rubric of four dimensions scored 0–10 with written anchors
  (relevance, correctness, depth, structure); content = mean × 10. For behavioural questions
  "correctness" means a credible, specific example (STAR), which the prompt states. The model must
  also return specific strengths, improvements and a stronger example answer.
- **Clarity (0–100) = 60 % measured + 40 % Gemini.** The measured part comes from Whisper's word
  timestamps: pace (words per minute; no penalty inside 110–170), filler words per 100 words, and
  long pauses (≥ 2 s) per minute. The penalties are simple linear rules (see
  `backend/src/interview_api/clarity.py`) so every point can be explained. Gemini adds a 0–10
  "easy to follow when heard" judgement. *Why blend:* the metrics capture delivery the transcript
  can't show; the LLM captures coherence the metrics can't.
- **Overall = 70 % content + 30 % clarity.** What you say matters more than how smoothly you say it.
  All weights are settings.
- **Prompt-injection guard.** The transcript is user-controlled text. It goes inside delimiters, the
  system prompt says it is data, not instructions, and the delimiter can't be closed from inside.
- **Whisper and filler words.** Whisper tends to drop "um" and "uh". A disfluent `initial_prompt`
  nudges it to keep them. In the real-voice run every scripted filler survived, but that audio was
  synthetic speech with clearly spoken fillers; real hesitations may still be lost.
- **"like" is only a filler when punctuated as an interjection** ("it was, like, slow"). The first
  rule also counted ", like a holiday" (an example); a real run caught it and a test pins it.

## Speech-to-text: faster-whisper, locally and in the deployment

- **faster-whisper (CTranslate2, int8, CPU)** is ~4× faster than the reference implementation and
  needs no GPU. `base.en` transcribed 21.5 s of speech in 2.2 s on the dev machine; `small.en` took
  4.5 s with the same transcript. Default `base.en`; configurable.
- The model is **downloaded at image build time**, and the container runs with `HF_HUB_OFFLINE=1`,
  so start-up never depends on Hugging Face.
- **PyAV is pinned below 19.** faster-whisper 1.2.1 calls `av.open(..., metadata_errors=...)`,
  which PyAV 19 removed; every transcription failed until the pin.
- **The deployment runs the same image and model** (`base.en`, baked in): Vercel's container
  functions have 2 GB / 1 vCPU, enough for `base.en` int8. Live answers of ~50 s got feedback in
  9–11 s (README).
- **Optional: Whisper large-v3-turbo on Groq's API** (`TRANSCRIBER=groq`, word timestamps) behind the
  same `Transcriber` interface, for hosts too small to run Whisper in-process. It was built when the
  first hosting choice (Northflank, ~0.2 vCPU / 512 MB) looked too small; it is tested with mocked
  HTTP but not used by the live deployment.

## Gemini

- Model: `gemini-3.5-flash-lite` (config). On 2026-11-14 it answered a probe in 0.8 s, while
  `gemini-3.6-flash` took 58 s and `gemini-3.8-flash` didn't answer within 60 s on the free tier.
- Structured output (`response_json_schema` from Pydantic models), then **re-validation** with
  Pydantic: Gemini ignores some schema constraints, so scores are clamped to 0–10 and lists trimmed.
- Retries with backoff on 429/5xx/timeouts and on unusable JSON, capped at 20 s per wait because a
  user is waiting. A daily-quota error is not retried and becomes a clear 503 message.
- Previous questions for the same role are passed as an "avoid" list, so repeat practice gets new
  questions (seen in the real run).
- **Privacy:** on Gemini's free tier Google may use inputs to improve its products. The README says
  so; transcripts (not audio) are what Gemini sees.

## Accounts and security

- **Passwords:** argon2id (argon2-cffi defaults). Unknown emails still run a dummy verify, so login
  timing doesn't reveal which emails exist; the error message is identical.
- **Sessions:** a random 32-byte token in an httpOnly, SameSite=Lax cookie (Secure in production).
  Only its SHA-256 is stored, so a database leak doesn't leak live sessions. Logout deletes the row.
  *Alternative:* JWTs – rejected because they can't be revoked without extra state anyway.
- **CSRF:** SameSite=Lax stops cross-site POSTs from carrying the cookie; JSON endpoints also need a
  JSON content type, which a plain HTML form can't send.
- **Isolation:** every query filters by the logged-in user; another user's interview id returns 404
  (same as a missing one). Tested for every endpoint.
- **Rate limits:** a small in-memory sliding window per user (interview creation, answer uploads,
  completion), per client IP for login/sign-up (plus at most 5 new accounts per IP per hour), per
  email for *failed* logins only (a correct password isn't blocked by someone else's typos until
  50 failures/hour), and a **global** hourly cap on AI calls so one client can't burn the free
  Gemini/Groq quota. Stale keys are purged so memory stays bounded. *Trade-off:* per process. Locally
  that is exact; on Vercel each backend instance has its own counters (usually one instance at this
  traffic, but a burst can start more, and a new deployment resets them). A shared store (Postgres
  or Redis) is the fix if it matters.
- **Client IP behind proxies:** the Next.js proxy takes the right-most `X-Forwarded-For` entry (the
  one the platform's edge sets) and passes it to the backend in its own `x-interview-client-ip`
  header; browsers can't set that header because the proxy only copies an allowlist. The backend
  prefers it and otherwise falls back to the right-most `X-Forwarded-For` entry. *Found in
  production:* on Vercel the internal call from the frontend to the private backend arrives with
  `X-Forwarded-For` rewritten to the frontend function's own (AWS) address, so at first every
  visitor shared one per-IP bucket (5 sign-ups an hour for the whole site). Rate-limit rejections
  are logged (email keys masked); after the fix the logged key equals the caller's public IP and
  spoofed headers are ignored (checked with 6 sign-ups and 21 logins carrying fake IPs). *Limit:* with nothing in front of Next.js (local `docker compose`), Next.js keeps a
  browser-supplied header and route handlers can't see the socket address, so per-IP limits are
  spoofable there (checked: 6 sign-ups with fake headers all succeeded locally). The per-user and
  global AI caps don't depend on the IP.
- **Secure cookie:** `COOKIE_SECURE=auto` sets the Secure flag whenever the request arrived over
  HTTPS (`X-Forwarded-Proto`), so production is safe by default and `http://localhost` still works.
- **Open redirects:** the post-login `next` parameter must be a plain path (`/[A-Za-z0-9/_-]*`);
  `/\evil.com`-style tricks fall back to the dashboard.
- **Upload bounds:** bodies over the limit are refused from `Content-Length` (in the Next proxy and
  in a backend middleware) before being read, and the recording's length is read from the container
  (demuxing, no decoding) so an over-long answer is refused **before** any transcription CPU or
  quota is spent.
- **Slow AI calls don't hold database connections.** Each request reads what it needs, ends its
  transaction, calls Whisper/Gemini, then re-reads the interview under a row lock to write. The lock
  also settles two races: an answer arriving after "Finish" (refused with 409) and "Finish" while
  an answer is being saved (409, the client finishes again). The UI disables Finish during an
  upload, too. Gemini retries stop after 60 s in total, well inside the proxy's timeout.
- **Swagger** (`/api/docs`) can be switched off with `ENABLE_API_DOCS=false` (done in production,
  where the backend isn't publicly routable anyway).
- **Audio retention:** deleted in a `finally` block right after transcription, including when
  transcription fails (tested). `KEEP_AUDIO=true` opts in to keeping it.

## Frontend

- Next.js 16 App Router with Cache Components (the scaffold default). Two consequences handled:
  pages that read the URL (`useParams`, `usePathname`, `useSearchParams`) sit inside `Suspense`,
  and hidden routes stay mounted, so the recorder releases the microphone in effect clean-up.
- The recorder is a small state machine: idle → requesting → recording → recorded → uploading.
  Errors are typed (unsupported browser, permission denied, no mic, mic busy, too short, upload
  failed, server rejected). An upload failure **keeps the recording** so the user can retry
  without re-recording (covered by an end-to-end test).
- Charts with Recharts; Tailwind for styling; no component library to keep the bundle small.

## Testing

- **Backend (pytest, 92 tests):** auth, sessions, isolation, rate limits, audio deletion, upload
  validation, clarity maths, scoring, the Gemini adapter (fake client: retries, quota, bad JSON,
  injection delimiter), both transcribers (fake model / mocked HTTP), migrations. Runs against real
  PostgreSQL. Nothing external is called: an autouse fixture makes creating a Gemini client fail.
- **Frontend:** typecheck, ESLint, production build.
- **End-to-end (Playwright):** the compose stack with mocked AI and Chromium's fake microphone:
  sign up → interview → record each answer → feedback → finish → history → progress, plus
  "mic permission denied" and "upload fails, then retry".
- **Real-voice run (manual, recorded in the README):** the same browser path with real Gemini and
  real Whisper, driven by spoken WAV files (`frontend/e2e-voice/`).

## Hosting

- The spec asked for Azure (Container Apps + Azure Database for PostgreSQL). Azure for Students
  verification failed and a card-backed account wasn't an option. Northflank's free Sandbox was
  the next choice, but it wasn't accepting sign-ups.
- **Deployed on Vercel (Hobby, free, no card)** with **Vercel Services**: one project, two services.
  - `frontend`: the Next.js app, built natively by Vercel; the only public route.
  - `backend`: the **same `backend/Dockerfile`** as `docker compose`, run on Vercel's container
    runtime (Whisper `base.en` baked in, migrations on start). It has no public route; the frontend
    reaches it through a service binding that injects `BACKEND_URL`, so the proxy design needed no
    change.
  - **PostgreSQL: Neon** (free plan), provisioned through Vercel's Neon integration, which sets
    `DATABASE_URL` (pooled). The settings validator turns `postgresql://` into the psycopg driver
    URL.
- **Consequences, handled:** request bodies are capped at 4.5 MB (the recorder now records Opus at
  32 kbit/s, ~1 MB for 4 minutes; `MAX_AUDIO_BYTES=4000000`); containers scale to zero after ~5
  idle minutes (cold start measured in the README); several containers can start at once, so
  Alembic takes a transaction-scoped advisory lock; per-IP limits needed the client-IP header above.
- *Considered:* Render free (services sleep, Postgres expires after 30 days, 512 MB too small for
  Whisper), Hugging Face Docker Spaces (now need a paid plan), Koyeb (reportedly needs a card),
  Google Cloud Run (needs a card).
