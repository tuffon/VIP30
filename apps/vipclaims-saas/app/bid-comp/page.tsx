"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useId, useMemo, useState } from "react";
import { useSession } from "next-auth/react";

type JobPhase = "idle" | "uploading" | "queued" | "processing" | "ready" | "failed";

type UploadDropzoneProps = {
  title: string;
  description: string;
  file: File | null;
  onFileSelect: (file: File | null) => void;
};

type JobResult = {
  status: string;
  download_urls?: { xlsx?: string };
  meta?: { elapsed_ms?: number };
  narrative_debug?: Record<string, unknown>;
  notify_email?: string;
  error?: string;
  error_code?: string;
  error_details?: string;
};

const phaseOrder: Record<JobPhase, number> = {
  idle: 0,
  uploading: 0,
  queued: 1,
  processing: 1,
  ready: 2,
  failed: -1,
};

const timeline = [
  { id: "upload", label: "Upload PDFs", description: "Secure carrier + contractor uploads" },
  { id: "processing", label: "Parsing & AI", description: "Xactimate sections + narrative summary" },
  { id: "ready", label: "Delivery", description: "Download XLSX + notify stakeholders" },
];

function UploadDropzone({ title, description, file, onFileSelect }: UploadDropzoneProps) {
  const reactId = useId();
  const id = useMemo(
    () => `${title.toLowerCase().replace(/\s+/g, "-")}-${reactId.replace(/:/g, "")}`,
    [title, reactId],
  );
  const handleFileChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const nextFile = event.target.files?.[0] ?? null;
      onFileSelect(nextFile);
    },
    [onFileSelect],
  );

  const hasFile = Boolean(file);

  return (
    <label
      htmlFor={id}
      className={`flex h-56 w-full cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-6 text-center transition ${
        hasFile ? "border-emerald-200 bg-emerald-50" : "border-slate-200 bg-white"
      }`}
    >
      <input
        id={id}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={handleFileChange}
      />
      <span
        className={`inline-flex h-12 w-12 items-center justify-center rounded-full ${
          hasFile ? "bg-emerald-100 text-emerald-600" : "bg-slate-100 text-slate-500"
        }`}
      >
        <svg aria-hidden="true" viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M12 16V4" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M6 9l6-5 6 5" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M4 20h16" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <span className="mt-4 text-base font-semibold">{title}</span>
      <span className="mt-2 text-sm text-slate-500">{description}</span>
      <span className="mt-4 text-sm font-medium text-brand-primary">Click or drag to upload</span>
      {file ? (
        <span className="mt-3 w-full truncate text-xs text-emerald-600">Selected: {file.name}</span>
      ) : (
        <span className="mt-3 text-xs text-slate-400">PDF up to 30MB</span>
      )}
    </label>
  );
}

export default function BidCompPage() {
  const { data: session } = useSession();
  const [carrierFile, setCarrierFile] = useState<File | null>(null);
  const [contractorFile, setContractorFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<JobPhase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [result, setResult] = useState<JobResult | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [shouldEmail, setShouldEmail] = useState(false);
  const [notifyEmail, setNotifyEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const apiBase = useMemo(() => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:4000", []);

  useEffect(() => {
    if (session?.user?.email) {
      setNotifyEmail(session.user.email);
      setShouldEmail(true);
    }
  }, [session]);

  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!carrierFile || !contractorFile) {
        setError("Please select both PDFs to continue.");
        return;
      }

      const base = apiBase.replace(/\/$/, "");
      const uploadEndpoint = (filename: string) =>
        `${base}/render/upload-url?filename=${encodeURIComponent(filename)}`;

      setPhase("uploading");
      setError(null);
      setErrorCode(null);
      setResult(null);
      setJobId(null);
      setJobStatus(null);
      setDownloadUrl(null);
      setIsSubmitting(true);

      try {
        const createUrl = async (file: File) => {
          const resp = await fetch(uploadEndpoint(file.name), { method: "POST" });
          if (!resp.ok) throw new Error(`Failed to create upload URL (${resp.status})`);
          return resp.json() as Promise<{ upload_url: string; key: string }>;
        };

        const [carrierUrl, contractorUrl] = await Promise.all([
          createUrl(carrierFile),
          createUrl(contractorFile),
        ]);

        const commonHeaders: HeadersInit = { "Content-Type": "application/pdf" };
        const uploadCarrier = fetch(carrierUrl.upload_url, {
          method: "PUT",
          body: carrierFile,
          headers: commonHeaders,
        });
        const uploadContractor = fetch(contractorUrl.upload_url, {
          method: "PUT",
          body: contractorFile,
          headers: commonHeaders,
        });
        const [carrierResp, contractorResp] = await Promise.all([uploadCarrier, uploadContractor]);
        if (!carrierResp.ok || !contractorResp.ok) {
          throw new Error("Upload failed. Please verify your network connection.");
        }

        const payload: Record<string, unknown> = {
          carrier_key: carrierUrl.key,
          contractor_key: contractorUrl.key,
          carrier_filename: carrierFile.name,
          contractor_filename: contractorFile.name,
        };
        if (shouldEmail && notifyEmail) {
          payload.notify_email = notifyEmail;
        }

        const enqueueResp = await fetch(`${base}/render/bid-comp/keys`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!enqueueResp.ok) {
          throw new Error("Unable to start the bid comp job.");
        }
        const job = await enqueueResp.json();
        if (!job?.job_id) throw new Error("Server did not return a job id.");
        setJobId(job.job_id);
        setJobStatus(job.status || "queued");
        setPhase("queued");

        const statusUrl = `${base}/render/bid-comp/${job.job_id}`;
        for (let attempt = 0; attempt < 300; attempt++) {
          const resp = await fetch(statusUrl);
          const statusJson = await resp.json();
          const nextStatus = statusJson?.status ?? null;
          setJobStatus(nextStatus);
          if (statusJson?.download_urls?.xlsx) {
            setDownloadUrl(statusJson.download_urls.xlsx);
          }
          if (nextStatus === "finished") {
            setPhase("ready");
            setResult(statusJson);
            break;
          }
          if (nextStatus === "failed") {
            setPhase("failed");
            setErrorCode(statusJson?.error_code || null);
            throw new Error(statusJson?.error || "Job failed. Please try again.");
          }
          setPhase("processing");
          await new Promise((resolve) => setTimeout(resolve, 2000));
        }
      } catch (err) {
        setPhase("failed");
        setError(err instanceof Error ? err.message : "Unexpected error");
      } finally {
        setIsSubmitting(false);
      }
    },
    [apiBase, carrierFile, contractorFile, notifyEmail, shouldEmail],
  );

  return (
    <div className="space-y-10 text-slate-900">
      <header className="space-y-3">
        <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Bid Comp</p>
        <h1 className="text-3xl font-semibold text-slate-900">
          Carrier vs. contractor in one shareable report.
        </h1>
        <p className="text-slate-500">
          Upload two PDFs, let ScopeVista parse the scope, and we’ll return an XLSX + email-ready summary
          that explains the deltas.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="space-y-8">
        <section className="grid gap-6 md:grid-cols-2">
          <UploadDropzone
            title="Carrier Estimate"
            description="Attach the benchmark carrier estimate (PDF)."
            file={carrierFile}
            onFileSelect={setCarrierFile}
          />
          <UploadDropzone
            title="Contractor Bid"
            description="Attach the contractor or in-house bid (PDF)."
            file={contractorFile}
            onFileSelect={setContractorFile}
          />
        </section>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <label className="flex items-center gap-3 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={shouldEmail}
              onChange={(event) => setShouldEmail(event.target.checked)}
              className="h-4 w-4 rounded border-slate-300"
            />
            Email me when the report is ready (includes download and marketing tips)
          </label>
          {shouldEmail && (
            <div className="mt-3">
              <input
                type="email"
                value={notifyEmail}
                onChange={(event) => setNotifyEmail(event.target.value)}
                placeholder="you@firm.com"
                className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none"
                required
              />
            </div>
          )}
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-full bg-slate-900 px-8 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-60"
        >
          {isSubmitting ? "Processing…" : "Generate Bid Comp"}
        </button>
      </form>

      {error && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-5 shadow-sm">
          <div className="flex items-start gap-3">
            <span className="inline-flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-rose-100 text-rose-600">
              <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 8v4M12 16h.01" strokeLinecap="round" />
              </svg>
            </span>
            <div className="flex-1">
              <p className="text-sm font-semibold text-rose-800">
                {errorCode === "WORKER_CRASHED" && "Processing Error"}
                {errorCode === "TIMEOUT" && "Request Timed Out"}
                {errorCode === "OUT_OF_MEMORY" && "File Too Large"}
                {errorCode === "PARSE_ERROR" && "PDF Parse Error"}
                {errorCode === "FILE_NOT_FOUND" && "File Not Found"}
                {errorCode === "CONNECTION_ERROR" && "Connection Issue"}
                {errorCode === "LLM_ERROR" && "AI Generation Error"}
                {(!errorCode || errorCode === "UNKNOWN_ERROR") && "Something Went Wrong"}
              </p>
              <p className="mt-1 text-sm text-rose-700">{error}</p>
              <button
                type="button"
                onClick={() => {
                  setPhase("idle");
                  setError(null);
                  setErrorCode(null);
                  setJobId(null);
                  setJobStatus(null);
                }}
                className="mt-3 rounded-full bg-rose-100 px-4 py-1.5 text-xs font-semibold text-rose-700 transition hover:bg-rose-200"
              >
                Try Again
              </button>
            </div>
          </div>
        </div>
      )}

      {jobId && (
        <section className="space-y-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm font-semibold text-slate-900">Job {jobId.slice(0, 8)}…</span>
            <span className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600">
              {jobStatus ?? "starting"}
            </span>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {timeline.map((step, idx) => {
              const activeIndex = phaseOrder[phase] ?? 0;
              const isComplete = idx < activeIndex;
              const isCurrent = idx === activeIndex && phase !== "ready";
              return (
                <div key={step.id} className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                  <p className="text-sm font-semibold text-slate-900">
                    {step.label}{" "}
                    {isComplete && <span className="text-emerald-500">✓</span>}
                    {isCurrent && !isComplete && <span className="text-amber-500">•</span>}
                  </p>
                  <p className="text-xs text-slate-500">{step.description}</p>
                </div>
              );
            })}
          </div>
          {shouldEmail && notifyEmail && (
            <p className="text-xs text-slate-500">
              We’ll send the download link to <span className="font-semibold text-slate-900">{notifyEmail}</span> as
              soon as the XLSX is ready.
            </p>
          )}
        </section>
      )}

      {(downloadUrl || result) && (
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-center gap-4">
            <p className="text-lg font-semibold text-slate-900">Latest output</p>
            {downloadUrl && (
              <a
                href={downloadUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-full bg-slate-900 px-5 py-2 text-xs font-semibold text-white transition hover:bg-slate-800"
              >
                Download XLSX
              </a>
            )}
          </div>
          {result?.meta && (
            <p className="mt-2 text-sm text-slate-500">
              Runtime: {(result.meta.elapsed_ms ?? 0) / 1000}s · Status: {result.status}
            </p>
          )}
          {result?.narrative_debug && (
            <div className="mt-4 rounded-2xl border border-slate-100 bg-slate-50 p-4 text-xs text-slate-600">
              <p className="font-semibold text-slate-900">Narrative</p>
              <pre className="mt-2 max-h-40 overflow-auto">{JSON.stringify(result.narrative_debug, null, 2)}</pre>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
