"use client";

import Link from "next/link";

export default function PdfToEsxPage() {
  return (
    <div className="space-y-10">
      <header className="max-w-3xl space-y-4">
        <h1 className="text-3xl font-semibold text-gray-900">PDF to ESX Conversion</h1>
        <p className="text-base text-gray-600">
          Convert carrier estimates and contractor scopes into Xactimate-compatible ESX files. The
          workflow guides you from upload to review without leaving the dashboard.
        </p>
      </header>

      <section className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="rounded-2xl bg-white p-8 shadow-sm">
          <h2 className="text-xl font-semibold text-gray-900">How it works</h2>
          <ol className="mt-4 list-decimal space-y-3 pl-5 text-sm text-gray-700">
            <li>Upload the source PDF or ZIP package of supporting documents.</li>
            <li>We extract line items, build the scope tree, and detect missing data automatically.</li>
            <li>Review the draft output, make adjustments, and download the ESX file instantly.</li>
          </ol>
        </div>

        <aside className="rounded-2xl border border-dashed border-purple-300 bg-purple-50 p-6 text-sm text-purple-700">
          <p className="font-semibold">Coming soon</p>
          <p className="mt-2">
            The conversion workflow will open here once the upload service is connected. Check back
            soon or contact support to join the early access program.
          </p>
        </aside>
      </section>

      <div className="rounded-2xl bg-white p-8 shadow-sm">
        <h2 className="text-xl font-semibold text-gray-900">Get notified</h2>
        <p className="mt-2 text-sm text-gray-600">
          Want a heads-up when PDF to ESX goes live? Join the update list so we can notify your
          team.
        </p>
        <Link
          href="mailto:support@vipclaims.ai"
          className="mt-6 inline-flex w-auto items-center justify-center rounded-full bg-purple-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-purple-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-purple-500 focus-visible:ring-offset-2"
        >
          Contact Support
        </Link>
      </div>
    </div>
  );
}

