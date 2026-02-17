"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { onCreditBalanceChanged } from "../lib/credits";

type MeResponse = {
  balance?: number;
};

export function CreditBalance() {
  const apiBase = useMemo(() => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:4000", []);
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthed, setIsAuthed] = useState(false);
  const [balance, setBalance] = useState<number | null>(null);

  const loadBalance = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!options?.silent) {
        setIsLoading(true);
      }
      try {
        const response = await fetch(`${apiBase.replace(/\/$/, "")}/credits/balance`, {
          credentials: "include",
        });

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
        setBalance(typeof payload.balance === "number" ? payload.balance : null);
      } catch {
        setIsAuthed(false);
        setBalance(null);
      } finally {
        setIsLoading(false);
      }
    },
    [apiBase],
  );

  useEffect(() => {
    void loadBalance();
  }, [loadBalance]);

  useEffect(() => {
    const refresh = () => {
      void loadBalance({ silent: true });
    };
    const intervalId = setInterval(refresh, 10000);
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    const unsubscribe = onCreditBalanceChanged((detail) => {
      if (typeof detail.balance === "number") {
        setIsAuthed(true);
        setBalance(detail.balance);
        setIsLoading(false);
      }
      refresh();
    });

    return () => {
      clearInterval(intervalId);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
      unsubscribe();
    };
  }, [loadBalance]);

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
