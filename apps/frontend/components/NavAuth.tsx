"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { clearPersistedSession, getPersistedSession, isSessionValid, persistSession } from "../lib/auth";
import { UserDropdown } from "./UserDropdown";

type MePayload = {
  user?: { email?: string; role?: string };
};

export function NavAuth() {
  const router = useRouter();
  const apiBase = useMemo(() => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:4000", []);
  const [isLoading, setIsLoading] = useState(false);
  const [email, setEmail] = useState<string | null>(() => {
    const persisted = getPersistedSession();
    if (!persisted) return null;
    return isSessionValid(persisted) ? persisted.email : null;
  });
  const [role, setRole] = useState<string>("member");

  useEffect(() => {
    let isMounted = true;

    async function loadUser() {
      try {
        const response = await fetch(`${apiBase.replace(/\/$/, "")}/auth/me`, { credentials: "include" });
        if (!isMounted) return;

        if (!response.ok) {
          setEmail(null);
          setRole("member");
          clearPersistedSession();
          return;
        }

        const payload = (await response.json()) as MePayload;
        const resolvedEmail = payload.user?.email || null;
        const resolvedRole = payload.user?.role || "member";
        setEmail(resolvedEmail);
        setRole(resolvedRole);
        if (resolvedEmail) {
          persistSession(resolvedEmail);
        } else {
          clearPersistedSession();
        }
      } catch {
        if (!isMounted) return;
        setEmail(null);
        setRole("member");
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    setIsLoading(true);
    loadUser();

    return () => {
      isMounted = false;
    };
  }, [apiBase]);

  async function handleLogout() {
    clearPersistedSession();
    try {
      await fetch(`${apiBase.replace(/\/$/, "")}/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } finally {
      setEmail(null);
      setRole("member");
      router.push("/");
      router.refresh();
    }
  }

  if (isLoading && !email) {
    return <span className="text-sm text-slate-400">Loading…</span>;
  }

  if (!email) {
    return (
      <Link
        href="/login"
        className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800"
      >
        Log in
      </Link>
    );
  }

  const isAdmin = role === "admin";

  return (
    <div className="flex items-center gap-3">
      <Link href="/bid-comp" className="text-xs font-semibold text-slate-500 hover:text-slate-900">
        Bid Comp
      </Link>
      <Link href="/jobs" className="text-xs font-semibold text-slate-500 hover:text-slate-900">
        Jobs
      </Link>
      <Link href="/credits" className="text-xs font-semibold text-slate-500 hover:text-slate-900">
        Credits
      </Link>
      {isAdmin ? (
        <Link href="/admin" className="text-xs font-semibold text-slate-500 hover:text-slate-900">
          Admin
        </Link>
      ) : null}
      <UserDropdown email={email} isAdmin={isAdmin} onSignOut={handleLogout} />
    </div>
  );
}
