"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { JobHistoryList } from "../../components/JobHistoryList";

type JobsResponse = {
  page: number;
  per_page: number;
  total_count: number;
  jobs: Array<{
    id: string;
    state: "queued" | "parsing" | "analyzing" | "writing" | "completed" | "failed";
    progress_percent: number;
    current_step: string | null;
    error_message: string | null;
    result_s3_key?: string | null;
    created_at: string;
    completed_at?: string | null;
  }>;
};

export default function JobsPage() {
  const router = useRouter();
  const apiBase = useMemo(() => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:4000", []);
  const [page, setPage] = useState(1);
  const [perPage] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<JobsResponse | null>(null);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${apiBase.replace(/\/$/, "")}/jobs?page=${page}&per_page=${perPage}`,
        { credentials: "include" },
      );

      if (response.status === 401) {
        router.push(`/login?next=${encodeURIComponent("/jobs")}`);
        return;
      }

      if (!response.ok) {
        setError("Unable to load job history.");
        return;
      }

      const payload = (await response.json()) as JobsResponse;
      setData(payload);
    } catch {
      setError("Unable to load job history.");
    } finally {
      setLoading(false);
    }
  }, [apiBase, page, perPage, router]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  async function handleRetry(jobId: string) {
    setError(null);
    try {
      const response = await fetch(`${apiBase.replace(/\/$/, "")}/jobs/${jobId}/retry`, {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) {
        setError("Unable to retry job.");
        return;
      }
      await fetchJobs();
    } catch {
      setError("Unable to retry job.");
    }
  }

  async function handleDownload(jobId: string) {
    try {
      const response = await fetch(`${apiBase.replace(/\/$/, "")}/jobs/${jobId}`, { credentials: "include" });
      if (!response.ok) {
        setError("Unable to fetch download link.");
        return;
      }
      const payload = (await response.json()) as { download_url?: string | null };
      if (payload.download_url) {
        window.open(payload.download_url, "_blank", "noopener,noreferrer");
      }
    } catch {
      setError("Unable to fetch download link.");
    }
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <p className="text-sm uppercase tracking-[0.2em] text-slate-500">Usage</p>
        <h1 className="text-3xl font-semibold text-slate-900">Job History</h1>
      </header>

      {loading ? <p className="text-sm text-slate-500">Loading jobs...</p> : null}
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}

      {data ? (
        <JobHistoryList
          jobs={data.jobs}
          totalCount={data.total_count}
          page={data.page}
          perPage={data.per_page}
          onPageChange={setPage}
          onRetry={handleRetry}
          onDownload={handleDownload}
        />
      ) : null}
    </div>
  );
}
