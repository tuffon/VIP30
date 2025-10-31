"use client";

import Link from "next/link";
import { useHealthQuery } from "../redux/services/api";

export default function HomePage() {
  const { data, isLoading } = useHealthQuery();
  const apiHealthy = data?.ok ?? false;

  return (
    <div className="space-y-10">
      <section className="rounded-2xl bg-white p-10 shadow-sm">
        <h1 className="text-3xl font-semibold text-gray-900">Welcome to VIP Claims</h1>
        <p className="mt-4 max-w-2xl text-base text-gray-600">
          Launch new estimates, manage document conversions, and monitor claim activity from one
          streamlined workspace.
        </p>
        <div className="mt-8 grid gap-6 sm:grid-cols-3">
          <div className="rounded-xl border border-gray-100 bg-gray-50 p-6">
            <p className="text-sm font-medium text-gray-500">Recent Activity</p>
            <p className="mt-2 text-2xl font-semibold text-gray-900">5 drafts</p>
            <p className="mt-1 text-sm text-gray-500">Updated in the last 24 hours</p>
          </div>
          <div className="rounded-xl border border-gray-100 bg-gray-50 p-6">
            <p className="text-sm font-medium text-gray-500">Open Bid Comps</p>
            <p className="mt-2 text-2xl font-semibold text-gray-900">2 pending</p>
            <p className="mt-1 text-sm text-gray-500">Awaiting review</p>
          </div>
          <div className="rounded-xl border border-gray-100 bg-gray-50 p-6">
            <p className="text-sm font-medium text-gray-500">PDF to ESX</p>
            <p className="mt-2 text-2xl font-semibold text-gray-900">3 conversions</p>
            <p className="mt-1 text-sm text-gray-500">Completed this week</p>
          </div>
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-2">
        <div className="rounded-2xl bg-white p-8 shadow-sm">
          <h2 className="text-xl font-semibold text-gray-900">System health</h2>
          <p className="mt-2 text-sm text-gray-600">
            We continuously monitor the core services behind VIP Claims so you can work without
            interruption.
          </p>
          <div className="mt-6 flex items-center gap-3">
            <span
              className={`inline-flex h-3 w-3 rounded-full ${
                apiHealthy ? "bg-emerald-500" : "bg-rose-500"
              }`}
            />
            <span className="text-sm font-medium text-gray-700">
              {isLoading ? "Checking API status…" : apiHealthy ? "API is online" : "API is offline"}
            </span>
          </div>
        </div>

        <div className="rounded-2xl bg-white p-8 shadow-sm">
          <h2 className="text-xl font-semibold text-gray-900">Quick actions</h2>
          <p className="mt-2 text-sm text-gray-600">
            Jump directly into your core workflows.
          </p>
          <div className="mt-6 grid gap-3">
            <Link
              href="/bid-comp"
              className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm font-medium text-blue-700 transition hover:bg-blue-100"
            >
              Launch Bid Comp
            </Link>
            <Link
              href="/pdf-to-esx"
              className="rounded-lg border border-purple-100 bg-purple-50 px-4 py-3 text-sm font-medium text-purple-700 transition hover:bg-purple-100"
            >
              Convert PDF to ESX
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}


