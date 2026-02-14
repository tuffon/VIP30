"use client";

import { useEffect, useMemo, useState } from "react";

type MeResponse = {
  success?: boolean;
  credit_balance?: number;
};

export function CreditBalance() {
  const apiBase = useMemo(() => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:4000", []);
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthed, setIsAuthed] = useState(false);
  const [balance, setBalance] = useState<number | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadBalance() {
      try {
        const response = await fetch(`${apiBase.replace(/\/$/, "")}/auth/me`, {
          credentials: "include",
        });

        if (!isMounted) return;

        if (response.status === 401) {
          setIsAuthed(false);
          setBalance(null);
          return;
        }

        if (!response.ok) {
          setIsAuthed(false);
          setBalance(null);
          return;
        }

        const payload = (await response.json()) as MeResponse;
        setIsAuthed(true);
        setBalance(typeof payload.credit_balance === "number" ? payload.credit_balance : null);
      } catch {
        if (!isMounted) return;
        setIsAuthed(false);
        setBalance(null);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadBalance();

    return () => {
      isMounted = false;
    };
  }, [apiBase]);

  if (isLoading) {
    return <span className="text-xs font-medium text-slate-400">...</span>;
  }

  if (!isAuthed) {
    return null;
  }

  const value = balance ?? 0;
  const tone = value <= 0 ? "text-rose-600" : value <= 2 ? "text-amber-600" : "text-emerald-600";

  return <span className={`text-sm font-semibold ${tone}`}>{value} credits</span>;
}
