"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type JobState = "queued" | "parsing" | "analyzing" | "writing" | "completed" | "failed";

type JobStatusPayload = {
  id: string;
  state: JobState;
  progress_percent: number;
  current_step: string | null;
  error_message: string | null;
  result_s3_key?: string | null;
  download_url?: string | null;
};

const stateTone: Record<JobState, string> = {
  queued: "bg-slate-100 text-slate-700",
  parsing: "bg-amber-100 text-amber-800",
  analyzing: "bg-amber-100 text-amber-800",
  writing: "bg-amber-100 text-amber-800",
  completed: "bg-emerald-100 text-emerald-800",
  failed: "bg-rose-100 text-rose-800",
};

const POLL_INTERVAL_MS = 2000;
const HEALTHY_POLL_WINDOW_MS = 8000;
const ETA_MINUTES = 5;

const milestoneThresholds = [
  { id: "downloaded", label: "Files downloaded", threshold: 15 },
  { id: "carrier", label: "Primary estimate parsed", threshold: 35 },
  { id: "comparison", label: "Comparison estimate parsed", threshold: 55 },
  { id: "analysis", label: "Delta analysis completed", threshold: 65 },
  { id: "report", label: "Report generated", threshold: 88 },
  { id: "uploaded", label: "Results uploaded", threshold: 96 },
];

export function JobProgress({
  jobId,
  onComplete,
  onError,
  onRetry,
}: {
  jobId: string;
  onComplete?: (result: JobStatusPayload) => void;
  onError?: (errorMessage: string, result: JobStatusPayload) => void;
  onRetry?: () => void;
}) {
  const apiBase = useMemo(() => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:4000", []);
  const [status, setStatus] = useState<JobStatusPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [lastPollAt, setLastPollAt] = useState<number | null>(null);
  const [lastProgressAt, setLastProgressAt] = useState<number | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [now, setNow] = useState<number | null>(null);
  const callbackSent = useRef(false);
  const previousProgress = useRef<number | null>(null);

  useEffect(() => {
    callbackSent.current = false;
    previousProgress.current = null;
    setStatus(null);
    setRequestError(null);
    setLoading(true);
    const started = Date.now();
    setStartedAt(started);
    setNow(started);
    setLastPollAt(null);
    setLastProgressAt(null);

    const base = apiBase.replace(/\/$/, "");
    let active = true;
    let intervalId: ReturnType<typeof setInterval> | null = null;

    const poll = async () => {
      try {
        const response = await fetch(`${base}/jobs/${jobId}`, { credentials: "include" });
        if (!active) return;

        if (!response.ok) {
          setRequestError(`Unable to load job status (${response.status}).`);
          return;
        }

        const payload = (await response.json()) as JobStatusPayload;
        const now = Date.now();
        setLastPollAt(now);
        if (previousProgress.current !== payload.progress_percent) {
          previousProgress.current = payload.progress_percent;
          setLastProgressAt(now);
        }
        setStatus(payload);
        setRequestError(null);

        if ((payload.state === "completed" || payload.state === "failed") && !callbackSent.current) {
          callbackSent.current = true;
          if (payload.state === "completed") {
            onComplete?.(payload);
          } else {
            onError?.(payload.error_message || "Job failed.", payload);
          }
          if (intervalId) {
            clearInterval(intervalId);
            intervalId = null;
          }
        }
      } catch {
        if (!active) return;
        setRequestError("Unable to load job status right now.");
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    poll();
    intervalId = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      active = false;
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [apiBase, jobId, onComplete, onError]);

  useEffect(() => {
    const tick = () => setNow(Date.now());
    tick();
    const intervalId = setInterval(tick, 1000);
    return () => clearInterval(intervalId);
  }, []);

  const progress = status?.progress_percent ?? 0;
  const tone = stateTone[status?.state || "queued"];
  const isTerminal = status?.state === "completed" || status?.state === "failed";
  const currentNow = now ?? startedAt ?? 0;
  const elapsedSec = startedAt ? Math.max(0, Math.floor((currentNow - startedAt) / 1000)) : 0;
  const sinceLastPollSec = lastPollAt ? Math.floor((currentNow - lastPollAt) / 1000) : null;
  const sinceLastProgressSec = lastProgressAt ? Math.floor((currentNow - lastProgressAt) / 1000) : null;
  const pollingHealthy = typeof sinceLastPollSec === "number" ? sinceLastPollSec * 1000 <= HEALTHY_POLL_WINDOW_MS : false;
  const milestoneProgress = status?.state === "completed" ? 100 : progress;

  return (
    <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm font-semibold text-slate-900">Job {jobId.slice(0, 8)}...</p>
        <div className="flex items-center gap-2">
          {!isTerminal ? <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-400 border-t-transparent" /> : null}
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone}`}>
            {status?.state || (loading ? "loading" : "queued")}
          </span>
        </div>
      </div>

      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-slate-900 transition-all"
          style={{ width: `${Math.max(0, Math.min(100, progress))}%` }}
        />
      </div>

      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>{status?.current_step || "Waiting for worker..."}</span>
        <span>{progress}%</span>
      </div>

      {!isTerminal ? (
        <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
          <div className="flex items-center justify-between gap-3">
            <span className="font-medium">
              {pollingHealthy
                ? "Polling healthy. Worker is still processing your documents."
                : "Checking job status. Waiting for fresh poll response..."}
            </span>
            <span>{elapsedSec}s elapsed</span>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <span>{`Expected runtime: ~${ETA_MINUTES} min for large PDFs`}</span>
            {typeof sinceLastPollSec === "number" ? <span>{`Last poll: ${sinceLastPollSec}s ago`}</span> : null}
            {typeof sinceLastProgressSec === "number" ? <span>{`Last progress change: ${sinceLastProgressSec}s ago`}</span> : null}
          </div>
        </div>
      ) : null}

      <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Milestones</p>
        <div className="grid gap-2 sm:grid-cols-2">
          {milestoneThresholds.map((milestone) => {
            const complete = milestoneProgress >= milestone.threshold;
            return (
              <div
                key={milestone.id}
                className={`rounded-lg border px-3 py-2 text-xs ${
                  complete ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-slate-200 bg-slate-50 text-slate-600"
                }`}
              >
                <span className="mr-2">{complete ? "✓" : "○"}</span>
                {milestone.label}
              </div>
            );
          })}
        </div>
      </div>

      {status?.state === "failed" ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          <p>{status.error_message || "The job failed."}</p>
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="mt-2 rounded-full bg-rose-100 px-3 py-1 text-xs font-semibold text-rose-700 hover:bg-rose-200"
            >
              Retry job
            </button>
          ) : null}
        </div>
      ) : null}

      {requestError ? <p className="text-xs text-rose-600">{requestError}</p> : null}
    </section>
  );
}
