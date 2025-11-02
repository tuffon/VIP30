"use client";

import { ChangeEvent, FormEvent, useCallback, useMemo, useState } from "react";

type RequestInfo = {
  url: string;
  method: string;
  fields: Array<{ name: string; value: string }>;
  files: Array<{ field: string; name: string; size: number }>;
  response?: {
    ok: boolean;
    status: number;
    statusText: string;
    error?: string;
  };
};

type JsonPreview = {
  filename: string;
  payload: Record<string, unknown>;
};

type RecapPreview = {
  filename: string;
  recap: Record<string, unknown> | null;
};

type UploadDropzoneProps = {
  title: string;
  description: string;
  file: File | null;
  onFileSelect: (file: File | null) => void;
};

function UploadDropzone({ title, description, file, onFileSelect }: UploadDropzoneProps) {
  const id = useMemo(() => `${title.toLowerCase().replace(/\s+/g, "-")}-${Math.random().toString(36).slice(2)}`, [title]);

  const handleFileChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const nextFile = event.target.files?.[0] ?? null;
      onFileSelect(nextFile);
    },
    [onFileSelect]
  );

  const hasFile = Boolean(file);
  const borderClass = hasFile ? "border-green-400 bg-green-50" : "border-gray-300 bg-white";

  return (
    <label
      htmlFor={id}
      className={`flex h-60 w-full cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-6 text-center transition hover:border-blue-500 hover:bg-blue-50 ${borderClass}`}
    >
      <input
        id={id}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={handleFileChange}
      />
      <span className={`inline-flex h-12 w-12 items-center justify-center rounded-full ${hasFile ? "bg-green-200 text-green-700" : "bg-blue-100 text-blue-600"}`}>
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          className="h-6 w-6"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <path d="M12 16V4" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M6 9l6-5 6 5" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M4 20h16" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <span className="mt-4 text-base font-semibold text-gray-900">{title}</span>
      <span className="mt-2 text-sm text-gray-600">{description}</span>
      <span className="mt-4 text-sm font-medium text-blue-600">Drag and drop or click to upload</span>
      {file ? (
        <span className="mt-3 w-full truncate text-xs text-green-600">Selected: {file.name}</span>
      ) : (
        <span className="mt-3 text-xs text-gray-400">No file selected</span>
      )}
    </label>
  );
}

export default function BidCompPage() {
  const [carrierFile, setCarrierFile] = useState<File | null>(null);
  const [contractorFile, setContractorFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [requestInfo, setRequestInfo] = useState<RequestInfo | null>(null);
  const [pingStatus, setPingStatus] = useState<string | null>(null);
  const [echoStatus, setEchoStatus] = useState<string | null>(null);

  const apiBase = useMemo(() => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:4000", []);

  const handlePing = useCallback(async () => {
    setPingStatus("Testing…");
    try {
      const response = await fetch(`${apiBase.replace(/\/$/, "")}/render/debug/ping`);
      const data = await response.json();
      setPingStatus(`Status ${response.status}: ${JSON.stringify(data)}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unexpected error";
      setPingStatus(`Failed: ${message}`);
    }
  }, [apiBase]);

  const handleEcho = useCallback(async () => {
    setEchoStatus("Testing…");
    try {
      const response = await fetch(`${apiBase.replace(/\/$/, "")}/render/debug/echo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: "hello from bid-comp", timestamp: Date.now() }),
      });
      const data = await response.json();
      setEchoStatus(`Status ${response.status}: ${JSON.stringify(data)}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unexpected error";
      setEchoStatus(`Failed: ${message}`);
    }
  }, [apiBase]);

  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!carrierFile || !contractorFile) {
        setError("Please select both PDF files before running the comparison.");
        return;
      }

      setIsSubmitting(true);
      setError(null);
      setResult(null);
      setRequestInfo(null);

      const formData = new FormData();
      formData.append("carrier_estimate", carrierFile);
      formData.append("contractor_estimate", contractorFile);
      formData.append("model", "gpt-4o-mini");
      formData.append("temperature", "0.2");
      formData.append("row_label_header", "Category");

      const endpoint = `${apiBase.replace(/\/$/, "")}/render/bid-comp`;
      setRequestInfo({
        url: endpoint,
        method: "POST",
        fields: [
          { name: "model", value: "gpt-4o-mini" },
          { name: "temperature", value: "0.2" },
          { name: "row_label_header", value: "Category" },
        ],
        files: [
          { field: "carrier_estimate", name: carrierFile.name, size: carrierFile.size },
          { field: "contractor_estimate", name: contractorFile.name, size: contractorFile.size },
        ],
      });

      try {
        const response = await fetch(endpoint, {
          method: "POST",
          body: formData,
        });

        const responseSummary = {
          ok: response.ok,
          status: response.status,
          statusText: response.statusText || (response.ok ? "OK" : "Error"),
        };

        if (!response.ok) {
          const text = await response.text();
          setRequestInfo((prev) =>
            prev
              ? {
                  ...prev,
                  response: {
                    ...responseSummary,
                    error: text || `Request failed with status ${response.status}`,
                  },
                }
              : prev
          );
          throw new Error(text || `Request failed with status ${response.status}`);
        }

        const data = await response.json();
        setResult(data);
        setRequestInfo((prev) =>
          prev
            ? {
                ...prev,
                response: {
                  ...responseSummary,
                },
              }
            : prev
        );
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unexpected error";
        setError(message);
        setRequestInfo((prev) =>
          prev
            ? {
                ...prev,
                response: {
                  ok: false,
                  status: prev.response?.status ?? 0,
                  statusText: prev.response?.statusText ?? "Request Failed",
                  error: message,
                },
              }
            : prev
        );
      } finally {
        setIsSubmitting(false);
      }
    },
    [apiBase, carrierFile, contractorFile]
  );

  const openAiText = result?.openai_result?.response_text as string | undefined;
  const requestStatus = requestInfo?.response;
  const openAiRequest = result?.openai_request_preview;
  const hasOpenAiResponse = Boolean(result?.openai_result);
  const jsonPreviews: JsonPreview[] = useMemo(() => {
    if (!result) return [];
    const previews: JsonPreview[] = [];
    if (result.carrier_estimate) {
      previews.push({
        filename: result.carrier_estimate.filename,
        payload: result.carrier_estimate.payload,
      });
    }
    if (result.contractor_estimate) {
      previews.push({
        filename: result.contractor_estimate.filename,
        payload: result.contractor_estimate.payload,
      });
    }
    return previews;
  }, [result]);

  const recapPreviews: RecapPreview[] = useMemo(() => {
    if (!result) return [];
    const extractRecap = (payload: Record<string, unknown>): Record<string, unknown> | null => {
      const recapsAndSummaries = payload?.recaps_and_summaries as Record<string, unknown> | undefined;
      const directRecap = payload?.recap_by_category as Record<string, unknown> | undefined;
      if (recapsAndSummaries && typeof recapsAndSummaries === "object") {
        const nested = recapsAndSummaries.recap_by_category as Record<string, unknown> | undefined;
        if (nested && typeof nested === "object") {
          return nested;
        }
      }
      if (directRecap && typeof directRecap === "object") {
        return directRecap;
      }
      return null;
    };

    const previews: RecapPreview[] = [];
    if (result.carrier_estimate?.payload) {
      previews.push({
        filename: result.carrier_estimate.filename,
        recap: extractRecap(result.carrier_estimate.payload),
      });
    }
    if (result.contractor_estimate?.payload) {
      previews.push({
        filename: result.contractor_estimate.filename,
        recap: extractRecap(result.contractor_estimate.payload),
      });
    }
    return previews;
  }, [result]);

  return (
    <div className="space-y-10">
      <header className="max-w-3xl space-y-4">
        <h1 className="text-3xl font-semibold text-gray-900">Bid Comparison</h1>
        <p className="text-base text-gray-600">
          Upload the scope documents to generate a side-by-side cost comparison. The analysis runs
          through the parser and OpenAI to create a recap-by-category summary.
        </p>
      </header>

      <form className="space-y-8" onSubmit={handleSubmit}>
        <section className="grid gap-6 md:grid-cols-2">
          <UploadDropzone
            title="Carrier Estimate"
            description="Attach the carrier or benchmark estimate (PDF only)."
            file={carrierFile}
            onFileSelect={setCarrierFile}
          />
          <UploadDropzone
            title="Contractor Bid"
            description="Upload the contractor or internal bid (PDF only)."
            file={contractorFile}
            onFileSelect={setContractorFile}
          />
        </section>

        <div className="flex flex-wrap items-center gap-4">
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-full bg-blue-600 px-8 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? "Running..." : "Instant Bid Comp"}
          </button>
          <span className="text-xs text-gray-400">API base: {apiBase}</span>
          {isSubmitting && <span className="text-xs text-blue-600">Uploading & processing…</span>}
          {requestStatus && (
            <span
              className={`rounded-full px-3 py-1 text-xs font-semibold ${requestStatus.ok ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}
            >
              {requestStatus.ok ? "Success" : "Failed"}
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs">
          <button
            type="button"
            onClick={handlePing}
            className="rounded bg-gray-200 px-3 py-2 font-semibold text-gray-700 transition hover:bg-gray-300"
          >
            Test API Ping
          </button>
          <button
            type="button"
            onClick={handleEcho}
            className="rounded bg-gray-200 px-3 py-2 font-semibold text-gray-700 transition hover:bg-gray-300"
          >
            Test API Echo
          </button>
          {pingStatus && <span className="text-gray-600">Ping: {pingStatus}</span>}
          {echoStatus && <span className="text-gray-600">Echo: {echoStatus}</span>}
        </div>
      </form>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {requestInfo && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">API Request Details</h2>
          <div className="rounded-lg border border-gray-200 bg-white p-4 text-xs text-gray-800">
            <div className="space-y-2">
              <div>
                <span className="font-medium">Method:</span> {requestInfo.method}
              </div>
              <div>
                <span className="font-medium">URL:</span> {requestInfo.url}
              </div>
              <div>
                <span className="font-medium">Fields:</span>
                <ul className="mt-1 list-disc space-y-1 pl-5">
                  {requestInfo.fields.map((field) => (
                    <li key={field.name}>
                      {field.name} = {field.value}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <span className="font-medium">Files:</span>
                <ul className="mt-1 list-disc space-y-1 pl-5">
                  {requestInfo.files.map((fileMeta) => (
                    <li key={fileMeta.field}>
                      {fileMeta.field}: {fileMeta.name} ({(fileMeta.size / 1024).toFixed(1)} KB)
                    </li>
                  ))}
                </ul>
              </div>
              {requestInfo.response && (
                <div>
                  <span className="font-medium">Response:</span> {requestInfo.response.status} {requestInfo.response.statusText}
                  {requestInfo.response.error && (
                    <span className="text-red-600"> — {requestInfo.response.error}</span>
                  )}
                </div>
              )}
              {!requestInfo.response && (
                <div>
                  <span className="font-medium">Response:</span> <span className="text-blue-500">Pending…</span>
                </div>
              )}
            </div>
          </div>
        </section>
      )}

      {result && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">Latest Result</h2>
          <div className="rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-700">
            <p className="font-medium">Estimate Labels</p>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              <li>
                <span className="font-semibold">Left:</span> {result.left_label}
              </li>
              <li>
                <span className="font-semibold">Right:</span> {result.right_label}
              </li>
              <li>
                <span className="font-semibold">Row Header:</span> {result.row_label_header}
              </li>
            </ul>
          </div>

          {jsonPreviews.length > 0 && (
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <p className="text-sm font-medium text-gray-900">Parsed Estimate JSON</p>
              <div className="mt-3 space-y-4">
                {jsonPreviews.map((preview) => (
                  <details key={preview.filename} className="overflow-hidden rounded border border-gray-200" open>
                    <summary className="cursor-pointer bg-gray-50 px-4 py-2 text-sm font-semibold text-gray-700">
                      {preview.filename}
                    </summary>
                    <pre className="max-h-72 overflow-auto bg-gray-900 p-4 text-xs text-white">
                      {JSON.stringify(preview.payload, null, 2)}
                    </pre>
                  </details>
                ))}
              </div>
            </div>
          )}

          {recapPreviews.length > 0 && (
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <p className="text-sm font-medium text-gray-900">recap_by_category Context</p>
              <div className="mt-3 space-y-4">
                {recapPreviews.map((preview) => (
                  <details key={`${preview.filename}-recap`} className="overflow-hidden rounded border border-gray-200" open>
                    <summary className="cursor-pointer bg-gray-50 px-4 py-2 text-sm font-semibold text-gray-700">
                      {preview.filename}
                    </summary>
                    <pre className="max-h-72 overflow-auto bg-gray-900 p-4 text-xs text-white">
                      {preview.recap ? JSON.stringify(preview.recap, null, 2) : "{\n  \"recap_by_category\": null\n}"}
                    </pre>
                  </details>
                ))}
              </div>
            </div>
          )}

          {openAiText && (
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <p className="text-sm font-medium text-gray-900">OpenAI CSV Output</p>
              <pre className="mt-3 max-h-64 overflow-auto rounded bg-gray-900 p-4 text-xs text-white">
                {openAiText}
              </pre>
            </div>
          )}

          {!hasOpenAiResponse && openAiRequest && (
            <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800">
              <p className="font-semibold">OpenAI request not executed</p>
              <p className="mt-1">Add your <code className="rounded bg-yellow-100 px-1 py-0.5">OPENAI_API_KEY</code> to run the completion. Preview below:</p>
            </div>
          )}

          {openAiRequest && (
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <p className="text-sm font-medium text-gray-900">OpenAI Request Preview</p>
              <pre className="mt-3 max-h-64 overflow-auto rounded bg-gray-900 p-4 text-xs text-white">
                {JSON.stringify(openAiRequest, null, 2)}
              </pre>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

