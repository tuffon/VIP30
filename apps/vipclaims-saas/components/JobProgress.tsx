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
  const callbackSent = useRef(false);

  useEffect(() => {
    callbackSent.current = false;
    setStatus(null);
    setRequestError(null);
    setLoading(true);

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
    intervalId = setInterval(poll, 2000);

    return () => {
      active = false;
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [apiBase, jobId, onComplete, onError]);

  const progress = status?.progress_percent ?? 0;
  const tone = stateTone[status?.state || "queued"];

  return (
    <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-slate-900">Job {jobId.slice(0, 8)}...</p>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone}`}>
          {status?.state || (loading ? "loading" : "queued")}
        </span>
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
