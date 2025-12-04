"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useSession } from "next-auth/react";
import { brand } from "../components/brand";
import { LandingSignupForm } from "../components/LandingSignupForm";

const stats = [
  { label: "Avg. time saved per file", value: "3.1 hrs" },
  { label: "Contracts reconciled in 30 days", value: ">$12M" },
  { label: "LLM narratives generated", value: "1,400+" },
];

const features = [
  {
    title: "Frictionless uploads",
    description: "Secure carrier + contractor uploads with instant cloud parsing.",
  },
  {
    title: "Narratives you can send",
    description: "Bid-ready summaries, clarity on deltas, and owner-friendly insights.",
  },
  {
    title: "Category intelligence",
    description: "Verisk-aligned categories with delta spotlighting and download links.",
  },
];

export default function HomePage() {
  const { data: session } = useSession();
  const apiBase = useMemo(() => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:4000", []);

  return (
    <div className="space-y-24 text-slate-900">
      <section id="hero" className="space-y-10">
        <div className="panel space-y-6">
          <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Introducing {brand.name}</p>
          <h1 className="text-4xl font-semibold leading-tight md:text-5xl text-slate-900">
            Compare bids, explain deltas, and email the report in minutes.
          </h1>
          <p className="text-lg text-slate-600 md:max-w-2xl">
            ScopeVista brings uploads, parsing, AI narrative, and delivery under one roof. Launch a bid comp,
            share the XLSX, and keep your stakeholders in sync without spreadsheets.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/bid-comp"
              className="rounded-full bg-slate-900 px-8 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
            >
              Launch Bid Comp
            </Link>
            <a
              href="#platform"
              className="rounded-full border border-slate-200 px-8 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            >
              See how it works
            </a>
          </div>
          <div className="grid gap-6 pt-6 sm:grid-cols-3">
            {stats.map((stat) => (
              <div key={stat.label} className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                <p className="text-2xl font-semibold text-slate-900">{stat.value}</p>
                <p className="text-sm text-slate-500">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
        <LandingSignupForm apiBase={apiBase} defaultEmail={session?.user?.email ?? ""} />
      </section>

      <section id="platform" className="space-y-6">
        <h2 className="text-3xl font-semibold">A platform adjusters actually want to open.</h2>
        <div className="grid gap-6 md:grid-cols-3">
          {features.map((feature) => (
            <div key={feature.title} className="rounded-3xl border border-slate-100 bg-white p-6 shadow-sm">
              <p className="text-base font-semibold text-slate-900">{feature.title}</p>
              <p className="mt-2 text-sm text-slate-500">{feature.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="features" className="space-y-8">
        <div className="panel space-y-4">
          <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Workflow</p>
          <h3 className="text-2xl font-semibold text-slate-900">How ScopeVista gets you from PDF to narrative</h3>
          <ol className="space-y-4 text-slate-600">
            <li>
              <span className="font-semibold text-slate-900">1. Upload & authenticate.</span> Drop carrier and
              contractor PDFs, sign in with Google, and keep moving.
            </li>
            <li>
              <span className="font-semibold text-slate-900">2. Automated parsing + AI summary.</span> We structure
              the Verisk categories, call the LLM once, and snapshot the context for QA.
            </li>
            <li>
              <span className="font-semibold text-slate-900">3. Delivery + marketing touch.</span> As soon as the XLSX
              drops, you get a download button, in-app toast, and branded email.
            </li>
          </ol>
        </div>
      </section>

      <section id="pricing" className="space-y-4">
        <h3 className="text-3xl font-semibold">Simple pricing, no seat minimums.</h3>
        <div className="rounded-3xl border border-slate-100 bg-white p-6 shadow-sm">
          <p className="text-lg font-semibold text-slate-900">$79 per active user / month</p>
          <p className="mt-2 text-sm text-slate-500">
            Unlimited bid comps, AI narratives, download links, and marketing emails. Pay only for users who submit at
            least one job that month.
          </p>
          <Link
            href="mailto:hello@scopevista.app"
            className="mt-4 inline-flex rounded-full border border-slate-200 px-6 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            Talk to sales
          </Link>
        </div>
      </section>
    </div>
  );
}
