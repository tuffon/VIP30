import Link from "next/link";

import { brand } from "./brand";

export function Footer() {
  return (
    <footer className="bg-slate-900 text-slate-300">
      <div className="mx-auto grid w-full max-w-6xl gap-10 px-8 py-16 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-3">
          <p className="text-lg font-semibold text-white">{brand.name}</p>
          <p className="text-sm leading-relaxed text-slate-400">
            Xactimate comparison reporting for carrier and contractor estimate reviews.
          </p>
        </div>

        <div className="space-y-3">
          <p className="text-sm font-semibold uppercase tracking-wide text-slate-400">Legal</p>
          <div className="space-y-2 text-sm">
            <Link href="/privacy" className="transition hover:text-white">
              Privacy Policy
            </Link>
            <Link href="/terms" className="block transition hover:text-white">
              Terms of Service
            </Link>
          </div>
        </div>

        <div className="space-y-3">
          <p className="text-sm font-semibold uppercase tracking-wide text-slate-400">Security</p>
          <Link href="/security" className="text-sm transition hover:text-white">
            Security Overview
          </Link>
        </div>

        <div className="space-y-3">
          <p className="text-sm font-semibold uppercase tracking-wide text-slate-400">Contact</p>
          <div className="space-y-2 text-sm">
            <a href="mailto:hello@scopevista.app" className="block transition hover:text-white">
              hello@scopevista.app
            </a>
            <p className="text-slate-400">Austin, TX, United States</p>
          </div>
        </div>
      </div>
    </footer>
  );
}
