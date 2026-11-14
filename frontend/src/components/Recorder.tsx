"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api";

type Phase = "idle" | "requesting" | "recording" | "recorded" | "uploading";

type Problem = { kind: ProblemKind; message: string } | null;
type ProblemKind = "unsupported" | "denied" | "nomic" | "busy" | "short" | "upload" | "server";

const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
const MIN_SECONDS = 2;

function pickMimeType(): string {
  if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return "";
  return MIME_CANDIDATES.find((t) => MediaRecorder.isTypeSupported(t)) ?? "";
}

function extensionFor(type: string): string {
  if (type.includes("mp4")) return "m4a";
  if (type.includes("ogg")) return "ogg";
  return "webm";
}

export function micProblem(err: unknown): Problem {
  const name = err instanceof DOMException ? err.name : "";
  if (name === "NotAllowedError" || name === "SecurityError")
    return {
      kind: "denied",
      message:
        "Microphone access was blocked. Allow the microphone for this site (the icon at the left of the address bar), then try again.",
    };
  if (name === "NotFoundError" || name === "OverconstrainedError")
    return { kind: "nomic", message: "No microphone was found. Plug one in or pick one in your system settings." };
  if (name === "NotReadableError" || name === "AbortError")
    return {
      kind: "busy",
      message: "The microphone is in use by another app or couldn't start. Close other apps using it and try again.",
    };
  return { kind: "unsupported", message: "Couldn't start recording in this browser." };
}

function fmt(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

type Props = {
  maxSeconds: number;
  /** Upload the recording. Throw ApiError to show its message (the recording is kept for retry). */
  onSubmit: (audio: Blob, filename: string) => Promise<void>;
  submitLabel?: string;
};

export default function Recorder({ maxSeconds, onSubmit, submitLabel = "Submit answer" }: Props) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [problem, setProblem] = useState<Problem>(null);
  const [elapsed, setElapsed] = useState(0);
  const [level, setLevel] = useState(0);
  const [audio, setAudio] = useState<{ blob: Blob; url: string; seconds: number } | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedRef = useRef(0);
  const timerRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);

  const releaseMic = useCallback(() => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    timerRef.current = rafRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    ctxRef.current?.close().catch(() => undefined);
    ctxRef.current = null;
    setLevel(0);
  }, []);

  // Release the microphone if this component unmounts or its route is hidden mid-recording.
  useEffect(() => {
    return () => {
      const rec = recorderRef.current;
      if (rec && rec.state !== "inactive") {
        rec.onstop = null;
        rec.stop();
      }
      releaseMic();
    };
  }, [releaseMic]);

  useEffect(() => {
    return () => {
      if (audio) URL.revokeObjectURL(audio.url);
    };
  }, [audio]);

  const stop = useCallback(() => {
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") rec.stop();
  }, []);

  const start = useCallback(async () => {
    setProblem(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setProblem({
        kind: "unsupported",
        message: "This browser can't record audio. Use a recent Chrome, Edge, Firefox or Safari over HTTPS.",
      });
      return;
    }
    setPhase("requesting");
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
      });
    } catch (err) {
      setPhase("idle");
      setProblem(micProblem(err));
      return;
    }
    streamRef.current = stream;

    const mimeType = pickMimeType();
    let rec: MediaRecorder;
    try {
      rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    } catch (err) {
      releaseMic();
      setPhase("idle");
      setProblem(micProblem(err));
      return;
    }
    recorderRef.current = rec;
    chunksRef.current = [];
    rec.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    rec.onstop = () => {
      const seconds = (performance.now() - startedRef.current) / 1000;
      releaseMic();
      const type = rec.mimeType || mimeType || "audio/webm";
      const blob = new Blob(chunksRef.current, { type });
      if (seconds < MIN_SECONDS || blob.size === 0) {
        setPhase("idle");
        setProblem({ kind: "short", message: "That recording was too short. Hold the button a little longer." });
        return;
      }
      setAudio({ blob, url: URL.createObjectURL(blob), seconds });
      setPhase("recorded");
    };

    // Input level meter, so the user can see the mic is picking them up.
    try {
      const ctx = new AudioContext();
      ctxRef.current = ctx;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      ctx.createMediaStreamSource(stream).connect(analyser);
      const buf = new Uint8Array(analyser.fftSize);
      const tick = () => {
        analyser.getByteTimeDomainData(buf);
        let peak = 0;
        for (const v of buf) peak = Math.max(peak, Math.abs(v - 128));
        setLevel(Math.min(1, peak / 64));
        rafRef.current = requestAnimationFrame(tick);
      };
      tick();
    } catch {
      // the meter is optional
    }

    startedRef.current = performance.now();
    setElapsed(0);
    rec.start(1000);
    setPhase("recording");
    timerRef.current = window.setInterval(() => {
      const s = (performance.now() - startedRef.current) / 1000;
      setElapsed(s);
      if (s >= maxSeconds && rec.state !== "inactive") rec.stop();
    }, 250);
  }, [maxSeconds, releaseMic]);

  const discard = useCallback(() => {
    setAudio(null);
    setProblem(null);
    setPhase("idle");
  }, []);

  const submit = useCallback(async () => {
    if (!audio) return;
    setProblem(null);
    setPhase("uploading");
    try {
      await onSubmit(audio.blob, `answer.${extensionFor(audio.blob.type)}`);
      setAudio(null);
      setPhase("idle");
    } catch (err) {
      setPhase("recorded"); // keep the recording so the user can retry without re-recording
      if (err instanceof ApiError && err.status > 0 && err.status < 500 && err.status !== 429) {
        setProblem({ kind: "server", message: err.message });
      } else {
        const wait = err instanceof ApiError && err.retryAfter ? ` (try again in ${err.retryAfter} s)` : "";
        const msg = err instanceof ApiError ? err.message : "Upload failed.";
        setProblem({ kind: "upload", message: `${msg}${wait} Your recording is kept, so you can retry.` });
      }
    }
  }, [audio, onSubmit]);

  const remaining = maxSeconds - elapsed;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900" data-testid="recorder" data-phase={phase}>
      {problem && (
        <div
          role="alert"
          data-testid="recorder-error"
          data-kind={problem.kind}
          className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200"
        >
          {problem.message}
        </div>
      )}

      {(phase === "idle" || phase === "requesting") && (
        <div className="flex flex-col items-center gap-3 py-2">
          <button
            type="button"
            onClick={start}
            disabled={phase === "requesting"}
            className="flex items-center gap-2 rounded-full bg-indigo-600 px-6 py-3 font-medium text-white shadow-sm hover:bg-indigo-500 disabled:opacity-60"
          >
            <span className="inline-block h-3 w-3 rounded-full bg-red-400" aria-hidden />
            {phase === "requesting" ? "Waiting for microphone…" : "Start recording"}
          </button>
          <p className="text-xs text-slate-500">Up to {fmt(maxSeconds)}. Speak as you would in a real interview.</p>
        </div>
      )}

      {phase === "recording" && (
        <div className="flex flex-col items-center gap-3 py-2">
          <div className="flex items-center gap-3">
            <span className="relative flex h-3 w-3" aria-hidden>
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
              <span className="relative inline-flex h-3 w-3 rounded-full bg-red-500" />
            </span>
            <span className="font-mono text-lg tabular-nums" data-testid="elapsed">
              {fmt(elapsed)}
            </span>
            <span className="text-xs text-slate-500">({fmt(remaining)} left)</span>
          </div>
          <div className="h-2 w-48 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700" aria-label="Microphone level">
            <div className="h-full bg-emerald-500 transition-[width] duration-75" style={{ width: `${Math.round(level * 100)}%` }} />
          </div>
          <button
            type="button"
            onClick={stop}
            className="rounded-full bg-slate-900 px-6 py-3 font-medium text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900"
          >
            Stop recording
          </button>
        </div>
      )}

      {(phase === "recorded" || phase === "uploading") && audio && (
        <div className="flex flex-col gap-3">
          <audio controls src={audio.url} className="w-full" />
          <p className="text-xs text-slate-500">Recorded {fmt(audio.seconds)}. Listen back if you like, then submit.</p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={submit}
              disabled={phase === "uploading"}
              className="rounded-lg bg-indigo-600 px-4 py-2 font-medium text-white hover:bg-indigo-500 disabled:opacity-60"
            >
              {phase === "uploading" ? "Transcribing and scoring…" : problem?.kind === "upload" ? "Retry upload" : submitLabel}
            </button>
            <button
              type="button"
              onClick={discard}
              disabled={phase === "uploading"}
              className="rounded-lg border border-slate-300 px-4 py-2 text-slate-700 hover:bg-slate-50 disabled:opacity-60 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              Re-record
            </button>
          </div>
          {phase === "uploading" && (
            <p className="text-sm text-slate-500" aria-live="polite">
              Transcribing your answer with Whisper, then scoring it. This usually takes 5–30 seconds.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
