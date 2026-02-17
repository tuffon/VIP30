"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useSession } from "next-auth/react";
import { brand } from "../components/brand";
import { LandingSignupForm } from "../components/LandingSignupForm";

const features = [
  {
    title: "Side-by-side deltas",
    description: "See exactly where carrier and contractor estimates diverge, line by line.",
  },
  {
    title: "Mismatch flags",
    description: "Automatically highlight significant variances that need attention.",
  },
  {
    title: "Narrative citations",
    description: "Professional narratives explain each delta with industry-appropriate language.",
  },
];

export default function HomePage() {
  const { data: session } = useSession();
  const apiBase = useMemo(() => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:4000", []);

  return (
    <div className="space-y-28 text-slate-900">
      <section id="hero" className="space-y-12 py-8 md:py-14">
        <div className="grid items-start gap-10 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="space-y-7">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">{brand.tagline}</p>
            <h1 className="text-4xl font-semibold leading-tight text-slate-900 md:text-6xl">
              Turn two Xactimate estimate PDFs into a carrier vs contractor comparison in minutes
            </h1>
            <p className="max-w-2xl text-lg leading-relaxed text-slate-600">
              Built for insurance adjusters who need clear variance reporting fast. Upload one carrier estimate and
              one contractor estimate, then download a ready-to-share report with deltas and narrative explanations.
              ScopeVista currently supports Xactimate estimate PDFs only.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link
                href="/bid-comp"
                className="rounded-full bg-[#0b1623] px-8 py-3 text-sm font-semibold text-white transition hover:bg-[#13263b]"
              >
                Generate Bid Comp
              </Link>
              <Link
                href="mailto:hello@scopevista.app"
                className="rounded-full border border-slate-300 bg-white px-8 py-3 text-sm font-semibold text-slate-800 transition hover:bg-slate-100"
              >
                Book demo
              </Link>
            </div>
          </div>
          <div className="panel p-0">
            <div className="border-b border-slate-200 px-6 py-4">
              <p className="text-sm font-semibold text-slate-900">Carrier vs Contractor Delta Summary</p>
              <p className="mt-1 text-xs uppercase tracking-[0.12em] text-slate-500">Xactimate comparison preview</p>
            </div>
            <div className="space-y-4 p-6">
              <div className="grid grid-cols-[1.2fr_1fr_1fr_1fr] gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <span>Category</span>
                <span>Carrier</span>
                <span>Contractor</span>
                <span>Delta</span>
              </div>
              {[
                ["Mitigation (PWI)", "$2,340", "$8,450", "+$6,110"],
                ["Electrical (ELE)", "$4,800", "$1,200", "-$3,600"],
                ["Paint (PNT)", "$2,775", "$735", "-$2,040"],
              ].map((row) => (
                <div
                  key={row[0]}
                  className="grid grid-cols-[1.2fr_1fr_1fr_1fr] gap-2 rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm"
                >
                  <span className="font-medium text-slate-900">{row[0]}</span>
                  <span className="text-slate-700">{row[1]}</span>
                  <span className="text-slate-700">{row[2]}</span>
                  <span className="font-semibold text-[#0f3a5f]">{row[3]}</span>
                </div>
              ))}
              <p className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-relaxed text-slate-700">
                Narrative citation: Carrier includes full MEP scope. Contractor does not contemplate mechanical or
                electrical allowance in two units. Variance driven by scope, not rate.
              </p>
            </div>
          </div>
        </div>
        <LandingSignupForm apiBase={apiBase} defaultEmail={session?.user?.email ?? ""} />
      </section>

      <section id="platform" className="space-y-7">
        <h2 className="text-3xl font-semibold leading-tight text-slate-900 md:text-4xl">
          Enterprise-ready comparison output for claims teams.
        </h2>
        <p className="max-w-3xl text-base leading-relaxed text-slate-600">
          Every report is structured for claim file review, supervisor sign-off, and stakeholder communication. You get
          consistent category framing, clear scope deltas, and concise narrative context.
        </p>
        <div className="grid gap-6 md:grid-cols-3">
          {features.map((feature) => (
            <div key={feature.title} className="rounded-2xl border border-slate-200 bg-white p-6">
              <p className="text-base font-semibold text-slate-900">{feature.title}</p>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">{feature.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="features" className="space-y-8">
        <div className="panel space-y-5">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Workflow</p>
          <h3 className="text-2xl font-semibold text-slate-900 md:text-3xl">
            Purpose-built for Xactimate estimate comparison
          </h3>
          <ol className="space-y-4 text-slate-700">
            <li>
              <span className="font-semibold text-slate-900">1. Upload two Xactimate PDFs.</span> Start with a carrier
              estimate and a contractor estimate for the same loss.
            </li>
            <li>
              <span className="font-semibold text-slate-900">2. AI analyzes the differences.</span> The system performs
              line-by-line comparison, computes deltas, and flags mismatched scope.
            </li>
            <li>
              <span className="font-semibold text-slate-900">3. Download your bid comp.</span> Export an XLSX report
              with structured deltas and narratives ready to share.
            </li>
          </ol>
        </div>
      </section>

      <section id="pricing" className="space-y-5">
        <h3 className="text-3xl font-semibold text-slate-900">Built for active claim operations.</h3>
        <div className="rounded-3xl border border-slate-200 bg-white p-7">
          <p className="text-lg font-semibold text-slate-900">Start with 5 free credits to evaluate fit.</p>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600">
            Process real files, review deltas, and validate narrative quality with your team before scaling usage.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link
              href="/bid-comp"
              className="rounded-full bg-[#0b1623] px-8 py-3 text-sm font-semibold text-white transition hover:bg-[#13263b]"
            >
              Generate Bid Comp
            </Link>
            <Link
              href="mailto:hello@scopevista.app"
              className="rounded-full border border-slate-300 bg-white px-8 py-3 text-sm font-semibold text-slate-800 transition hover:bg-slate-100"
            >
              Book demo
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
