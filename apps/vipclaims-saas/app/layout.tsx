"use client";

import "./globals.css";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { brand } from "../components/brand";
import { NavAuth } from "../components/NavAuth";
import { AppProviders } from "../components/providers/AppProviders";

const navLinks = [
  { href: "/#platform", label: "Platform" },
  { href: "/#features", label: "Features" },
  { href: "/#pricing", label: "Pricing" },
  { href: "/bid-comp", label: "Bid Comp" },
  { href: "/pdf-to-esx", label: "PDF→ESX" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const marketingMode = pathname === "/";

  return (
    <html lang="en">
      <body className="bg-white text-slate-900 antialiased">
        <AppProviders>
          <div className="flex min-h-screen flex-col">
            <header className="border-b border-slate-100 bg-white/90 backdrop-blur">
              <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-4">
                <Link href="/" className="flex items-center gap-3 text-lg font-semibold text-slate-900">
                  <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-slate-900 text-base font-bold text-white">
                    SV
                  </span>
                  <span>{brand.name}</span>
                </Link>
                <nav className="hidden gap-6 text-sm font-medium text-slate-500 md:flex">
                  {navLinks.map((link) => {
                    const isActive =
                      link.href === "/"
                        ? pathname === "/"
                        : pathname === link.href || pathname.startsWith(link.href);
                    return (
                      <Link
                        key={link.href}
                        href={link.href}
                        className={`transition hover:text-slate-900 ${isActive ? "text-slate-900" : ""}`}
                      >
                        {link.label}
                      </Link>
                    );
                  })}
                </nav>
                <NavAuth />
              </div>
            </header>
            <main className={`flex-1 ${marketingMode ? "bg-slate-50" : "bg-white"}`}>
              <div className={`mx-auto w-full max-w-6xl px-6 ${marketingMode ? "py-16" : "py-10"}`}>
                {children}
              </div>
            </main>
          </div>
        </AppProviders>
      </body>
    </html>
  );
}


