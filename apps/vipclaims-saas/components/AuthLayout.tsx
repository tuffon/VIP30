import Link from "next/link";
import { ReactNode } from "react";

import { brand } from "./brand";

export function AuthLayout({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <section className="mx-auto flex w-full max-w-sm flex-col gap-6">
      <Link
        href="/"
        className="inline-flex items-center gap-2 self-start text-xs font-semibold uppercase tracking-[0.2em] text-slate-500 transition hover:text-slate-900"
      >
        <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-slate-900 text-[10px] font-bold text-white">
          SV
        </span>
        {brand.name}
      </Link>
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        <p className="mt-2 text-sm text-slate-500">{subtitle}</p>
        <div className="mt-6">{children}</div>
      </div>
    </section>
  );
}
