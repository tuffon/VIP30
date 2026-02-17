"use client";

import "./globals.css";
import Link from "next/link";
import { IBM_Plex_Sans } from "next/font/google";
import { usePathname } from "next/navigation";
import { brand } from "../components/brand";
import { CreditBalance } from "../components/CreditBalance";
import { NavAuth } from "../components/NavAuth";
import { AppProviders } from "../components/providers/AppProviders";

const ibmPlexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const navLinks = [
  { href: "/#platform", label: "Platform" },
  { href: "/#features", label: "Features" },
  { href: "/#pricing", label: "Pricing" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const marketingMode = pathname === "/";

  return (
    <html lang="en">
      <body className={`${ibmPlexSans.className} bg-[#f4f6f8] text-slate-900 antialiased`}>
        <AppProviders>
          <div className="flex min-h-screen flex-col">
            <header className="border-b border-slate-200 bg-white/90 backdrop-blur">
              <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-4">
                <Link href="/" className="flex items-center gap-3 text-lg font-semibold text-slate-900">
                  <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-[#0b1623] text-base font-bold text-white">
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
                <div className="flex items-center gap-4">
                  <CreditBalance />
                  <NavAuth />
                </div>
              </div>
            </header>
            <main className={`flex-1 ${marketingMode ? "bg-[#f4f6f8]" : "bg-white"}`}>
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


