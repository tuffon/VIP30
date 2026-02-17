"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useId, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { JobProgress } from "../../components/JobProgress";

type JobPhase = "idle" | "uploading" | "queued" | "processing" | "ready" | "failed";

type UploadDropzoneProps = {
  title: string;
  description: string;
  file: File | null;
  onFileSelect: (file: File | null) => void;
};

type BalancePayload = {
  balance?: number;
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
  { id: "ready", label: "Delivery", description: "Download XLSX and review history" },
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
      <input id={id} type="file" accept="application/pdf" className="hidden" onChange={handleFileChange} />
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
  const router = useRouter();
  const [carrierFile, setCarrierFile] = useState<File | null>(null);
  const [contractorFile, setContractorFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<JobPhase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [creditBalance, setCreditBalance] = useState<number | null>(null);
  const [isCreditsLoading, setIsCreditsLoading] = useState(true);
  const apiBase = useMemo(() => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:4000", []);

  useEffect(() => {
    let active = true;

    async function loadCredits() {
      setIsCreditsLoading(true);
      try {
        const response = await fetch(`${apiBase.replace(/\/$/, "")}/credits/balance`, {
          credentials: "include",
        });

        if (!active) return;
        if (response.status === 401) {
          router.push(`/login?next=${encodeURIComponent("/bid-comp")}`);
          return;
        }
        if (!response.ok) {
          setCreditBalance(null);
          return;
        }

        const payload = (await response.json()) as BalancePayload;
        setCreditBalance(typeof payload.balance === "number" ? payload.balance : null);
      } catch {
        if (!active) return;
        setCreditBalance(null);
      } finally {
        if (active) {
          setIsCreditsLoading(false);
        }
      }
    }

    loadCredits();

    return () => {
      active = false;
    };
  }, [apiBase, router]);

  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!carrierFile || !contractorFile) {
        setError("Please select both PDFs to continue.");
        return;
      }

      if ((creditBalance ?? 0) <= 0) {
        setError("Insufficient credits. Please add credits to continue.");
        return;
      }

      const base = apiBase.replace(/\/$/, "");
      const uploadEndpoint = (filename: string) => `${base}/render/upload-url?filename=${encodeURIComponent(filename)}`;

      setPhase("uploading");
      setError(null);
      setJobId(null);
      setDownloadUrl(null);
      setIsSubmitting(true);

      try {
        const createUrl = async (file: File) => {
          const resp = await fetch(uploadEndpoint(file.name), { method: "POST" });
          if (!resp.ok) throw new Error(`Failed to create upload URL (${resp.status})`);
          return resp.json() as Promise<{ upload_url: string; key: string }>;
        };

        const [carrierUrl, contractorUrl] = await Promise.all([createUrl(carrierFile), createUrl(contractorFile)]);

        const commonHeaders: HeadersInit = { "Content-Type": "application/pdf" };
        const [carrierResp, contractorResp] = await Promise.all([
          fetch(carrierUrl.upload_url, { method: "PUT", body: carrierFile, headers: commonHeaders }),
          fetch(contractorUrl.upload_url, { method: "PUT", body: contractorFile, headers: commonHeaders }),
        ]);

        if (!carrierResp.ok || !contractorResp.ok) {
          throw new Error("Upload failed. Please verify your network connection.");
        }

        const enqueueResp = await fetch(`${base}/jobs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            carrier_key: carrierUrl.key,
            contractor_key: contractorUrl.key,
            carrier_filename: carrierFile.name,
            contractor_filename: contractorFile.name,
          }),
        });

        if (enqueueResp.status === 401) {
          router.push(`/login?next=${encodeURIComponent("/bid-comp")}`);
          return;
        }

        if (enqueueResp.status === 402) {
          setPhase("failed");
          setError("Insufficient credits. Please add credits to continue.");
          return;
        }

        if (!enqueueResp.ok) {
          throw new Error("Unable to start the bid comp job.");
        }

        const job = (await enqueueResp.json()) as { job_id?: string };
        if (!job.job_id) {
          throw new Error("Server did not return a job id.");
        }

        setJobId(job.job_id);
        setPhase("queued");
      } catch (err) {
        setPhase("failed");
        setError(err instanceof Error ? err.message : "Unexpected error");
      } finally {
        setIsSubmitting(false);
      }
    },
    [apiBase, carrierFile, contractorFile, creditBalance, router],
  );

  const submitDisabled = isSubmitting || isCreditsLoading || !carrierFile || !contractorFile || (creditBalance ?? 0) <= 0;
  const currentBalance = creditBalance ?? 0;
  const isZeroCredits = !isCreditsLoading && currentBalance <= 0;
  const isLowCredits = !isCreditsLoading && currentBalance > 0 && currentBalance <= 2;
  const creditCardTone = isZeroCredits
    ? "border-rose-200 bg-rose-50 text-rose-700"
    : isLowCredits
      ? "border-amber-200 bg-amber-50 text-amber-700"
      : "border-emerald-200 bg-emerald-50 text-emerald-700";

  return (
    <div className="space-y-10 text-slate-900">
      <header className="space-y-3">
        <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Bid Comp</p>
        <h1 className="text-3xl font-semibold text-slate-900">Carrier vs. contractor in one shareable report.</h1>
        <p className="text-slate-500">
          Upload two PDFs, parse the scope, and get an XLSX comparison with job tracking and history.
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

        <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className={`flex flex-wrap items-center justify-between gap-4 rounded-xl border p-4 ${creditCardTone}`}>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide">Credits</p>
              <p className="text-2xl font-bold">{isCreditsLoading ? "..." : currentBalance}</p>
            </div>
            {isLowCredits ? (
              <span className="rounded-full border border-amber-300 bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800">
                Low balance
              </span>
            ) : null}
            {isZeroCredits ? (
              <span className="rounded-full border border-rose-300 bg-rose-100 px-3 py-1 text-xs font-semibold text-rose-800">
                No credits
              </span>
            ) : null}
          </div>
          <p className={`text-sm ${isZeroCredits ? "text-rose-700" : "text-slate-600"}`}>
            {isZeroCredits
              ? "You need credits to generate comparisons. Contact us to add more."
              : "Each comparison uses 1 credit."}
          </p>
          <button
            type="submit"
            disabled={submitDisabled}
            className="rounded-full bg-slate-900 px-8 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? "Processing..." : "Generate Bid Comp"}
          </button>
        </div>
      </form>

      {error ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-5 shadow-sm">
          <p className="text-sm font-semibold text-rose-800">Something went wrong</p>
          <p className="mt-1 text-sm text-rose-700">{error}</p>
        </div>
      ) : null}

      {jobId ? (
        <JobProgress
          jobId={jobId}
          onComplete={(result) => {
            setPhase("ready");
            setDownloadUrl(result.download_url || null);
            setError(null);
          }}
          onError={(message) => {
            setPhase("failed");
            setError(message);
          }}
          onRetry={async () => {
            try {
              const response = await fetch(`${apiBase.replace(/\/$/, "")}/jobs/${jobId}/retry`, {
                method: "POST",
                credentials: "include",
              });
              if (!response.ok) {
                setError("Retry failed. Please try again.");
                return;
              }
              const payload = (await response.json()) as { job_id: string };
              setJobId(payload.job_id);
              setPhase("queued");
              setError(null);
            } catch {
              setError("Retry failed. Please try again.");
            }
          }}
        />
      ) : null}

      {downloadUrl ? (
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-center gap-4">
            <p className="text-lg font-semibold text-slate-900">Latest output</p>
            <a
              href={downloadUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-full bg-slate-900 px-5 py-2 text-xs font-semibold text-white transition hover:bg-slate-800"
            >
              Download XLSX
            </a>
          </div>
        </section>
      ) : null}

      {jobId ? (
        <section className="space-y-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="grid gap-4 md:grid-cols-3">
            {timeline.map((step, idx) => {
              const activeIndex = phaseOrder[phase] ?? 0;
              const isComplete = idx < activeIndex;
              const isCurrent = idx === activeIndex && phase !== "ready";
              return (
                <div key={step.id} className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                  <p className="text-sm font-semibold text-slate-900">
                    {step.label} {isComplete ? <span className="text-emerald-500">✓</span> : null}
                    {isCurrent && !isComplete ? <span className="text-amber-500">•</span> : null}
                  </p>
                  <p className="text-xs text-slate-500">{step.description}</p>
                </div>
              );
            })}
          </div>
        </section>
      ) : null}
    </div>
  );
}
