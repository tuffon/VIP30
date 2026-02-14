"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

export function NavAuth() {
  const apiBase = useMemo(() => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:4000", []);
  const [isLoading, setIsLoading] = useState(true);
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadUser() {
      try {
        const response = await fetch(`${apiBase.replace(/\/$/, "")}/auth/me`, { credentials: "include" });
        if (!isMounted) return;

        if (!response.ok) {
          setEmail(null);
          return;
        }

        const payload = (await response.json()) as { user?: { email?: string } };
        setEmail(payload.user?.email || null);
      } catch {
        if (!isMounted) return;
        setEmail(null);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadUser();

    return () => {
      isMounted = false;
    };
  }, [apiBase]);

  async function handleLogout() {
    try {
      await fetch(`${apiBase.replace(/\/$/, "")}/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } finally {
      setEmail(null);
    }
  }

  if (isLoading) {
    return <span className="text-sm text-slate-400">Loading…</span>;
  }

  if (!email) {
    return (
      <Link
        href="/login"
        className="rounded-full border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100"
      >
        Log in
      </Link>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm font-medium text-slate-600">{email}</span>
      <button
        type="button"
        onClick={handleLogout}
        className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-100"
      >
        Log out
      </button>
    </div>
  );
}

