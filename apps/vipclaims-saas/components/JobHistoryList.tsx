"use client";

import Link from "next/link";

type JobHistoryItem = {
  id: string;
  state: "queued" | "parsing" | "analyzing" | "writing" | "completed" | "failed";
  progress_percent: number;
  current_step: string | null;
  error_message: string | null;
  result_s3_key?: string | null;
  created_at: string;
  completed_at?: string | null;
};

const stateBadge: Record<JobHistoryItem["state"], string> = {
  queued: "bg-slate-100 text-slate-700",
  parsing: "bg-amber-100 text-amber-800",
  analyzing: "bg-amber-100 text-amber-800",
  writing: "bg-amber-100 text-amber-800",
  completed: "bg-emerald-100 text-emerald-800",
  failed: "bg-rose-100 text-rose-800",
};

export function JobHistoryList({
  jobs,
  totalCount,
  page,
  perPage,
  onPageChange,
  onRetry,
  onDownload,
}: {
  jobs: JobHistoryItem[];
  totalCount: number;
  page: number;
  perPage: number;
  onPageChange: (nextPage: number) => void;
  onRetry: (jobId: string) => void;
  onDownload: (jobId: string) => void;
}) {
  if (jobs.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
        <p className="text-lg font-semibold text-slate-900">No jobs yet</p>
        <p className="mt-2 text-sm text-slate-500">Run your first comparison to build history.</p>
        <Link
          href="/bid-comp"
          className="mt-5 inline-flex rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
        >
          Start your first comparison
        </Link>
      </div>
    );
  }

  const totalPages = Math.max(1, Math.ceil(totalCount / perPage));
  const start = (page - 1) * perPage + 1;
  const end = Math.min(totalCount, page * perPage);

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <ul className="divide-y divide-slate-100">
          {jobs.map((job) => (
            <li key={job.id} className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-slate-900">Job {job.id.slice(0, 8)}...</p>
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${stateBadge[job.state]}`}>
                    {job.state}
                  </span>
                </div>
                <p className="text-xs text-slate-500">
                  Created {new Date(job.created_at).toLocaleString()} · Credit cost: 1
                </p>
                {job.current_step ? <p className="text-xs text-slate-500">{job.current_step}</p> : null}
                {job.state === "failed" && job.error_message ? (
                  <p className="text-xs text-rose-600">{job.error_message}</p>
                ) : null}
              </div>

              <div className="flex items-center gap-2">
                {job.state === "completed" ? (
                  <button
                    type="button"
                    onClick={() => onDownload(job.id)}
                    className="rounded-full border border-emerald-200 px-3 py-1 text-xs font-semibold text-emerald-700 hover:bg-emerald-50"
                  >
                    Download
                  </button>
                ) : null}
                {job.state === "failed" ? (
                  <button
                    type="button"
                    onClick={() => onRetry(job.id)}
                    className="rounded-full border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                  >
                    Retry
                  </button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      </div>

      <div className="flex items-center justify-between text-sm text-slate-500">
        <p>
          Showing {start}-{end} of {totalCount}
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            className="rounded-full border border-slate-200 px-3 py-1 disabled:opacity-40"
          >
            Previous
          </button>
          <span>
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            className="rounded-full border border-slate-200 px-3 py-1 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
