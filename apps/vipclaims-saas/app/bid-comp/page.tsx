"use client";

import { useId } from "react";

function UploadDropzone({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  const id = useId();

  return (
    <label
      htmlFor={id}
      className="flex h-60 w-full cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-gray-300 bg-white p-6 text-center transition hover:border-blue-500 hover:bg-blue-50"
    >
      <input id={id} type="file" multiple className="hidden" />
      <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-blue-100 text-blue-600">
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
    </label>
  );
}

export default function BidCompPage() {
  return (
    <div className="space-y-10">
      <header className="max-w-3xl space-y-4">
        <h1 className="text-3xl font-semibold text-gray-900">Bid Comparison</h1>
        <p className="text-base text-gray-600">
          Upload the scope documents to generate a side-by-side cost comparison in seconds. We will
          notify you when the analysis is ready.
        </p>
      </header>

      <section className="grid gap-6 md:grid-cols-2">
        <UploadDropzone
          title="Carrier Estimate"
          description="Attach the carrier or benchmark estimate (PDF, ESX, XLSX)."
        />
        <UploadDropzone
          title="Contractor Bid"
          description="Upload the contractor or internal bid files to compare."
        />
      </section>

      <div>
        <button className="rounded-full bg-blue-600 px-8 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2">
          Instant Bid Comp
        </button>
      </div>
    </div>
  );
}

