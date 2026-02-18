"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { CreditHistoryList } from "../../components/CreditHistoryList";

type CreditsPayload = {
  items: Array<{
    id: string;
    type: "grant" | "consumption";
    amount: number;
    source: string | null;
    job_id: string | null;
    created_at: string;
    notes: string | null;
  }>;
  total_count: number;
  page: number;
  per_page: number;
};

export default function CreditsPage() {
  const router = useRouter();
  const apiBase = useMemo(() => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:4000", []);
  const [page, setPage] = useState(1);
  const [perPage] = useState(20);
  const [balance, setBalance] = useState<number | null>(null);
  const [data, setData] = useState<CreditsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadCredits = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [historyRes, balanceRes] = await Promise.all([
        fetch(`${apiBase.replace(/\/$/, "")}/credits?page=${page}&per_page=${perPage}`, {
          credentials: "include",
        }),
        fetch(`${apiBase.replace(/\/$/, "")}/credits/balance`, {
          credentials: "include",
        }),
      ]);

      if (historyRes.status === 401 || balanceRes.status === 401) {
        router.push(`/login?next=${encodeURIComponent("/credits")}`);
        return;
      }

      if (!historyRes.ok || !balanceRes.ok) {
        setError("Unable to load credit history.");
        return;
      }

      const historyPayload = (await historyRes.json()) as CreditsPayload;
      const balancePayload = (await balanceRes.json()) as { balance?: number };
      setData(historyPayload);
      setBalance(typeof balancePayload.balance === "number" ? balancePayload.balance : null);
    } catch {
      setError("Unable to load credit history.");
    } finally {
      setLoading(false);
    }
  }, [apiBase, page, perPage, router]);

  useEffect(() => {
    loadCredits();
  }, [loadCredits]);

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <p className="text-sm uppercase tracking-[0.2em] text-slate-500">Usage</p>
        <h1 className="text-3xl font-semibold text-slate-900">Credit History</h1>
        <p className="text-sm text-slate-600">
          Current balance: <span className="font-semibold text-slate-900">{balance ?? "..."} credits</span>
        </p>
      </header>

      {loading ? <p className="text-sm text-slate-500">Loading credit history...</p> : null}
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}

      {data ? (
        <CreditHistoryList
          transactions={data.items}
          totalCount={data.total_count}
          page={data.page}
          perPage={data.per_page}
          onPageChange={setPage}
        />
      ) : null}
    </div>
  );
}
