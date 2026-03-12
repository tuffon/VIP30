"use client";

function formatStableDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}

type CreditTransaction = {
  id: string;
  type: "grant" | "consumption";
  amount: number;
  source: string | null;
  job_id: string | null;
  created_at: string;
  notes: string | null;
};

export function CreditHistoryList({
  transactions,
  totalCount,
  page,
  perPage,
  onPageChange,
}: {
  transactions: CreditTransaction[];
  totalCount: number;
  page: number;
  perPage: number;
  onPageChange: (page: number) => void;
}) {
  if (transactions.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
        <p className="text-lg font-semibold text-slate-900">No transactions yet</p>
        <p className="mt-2 text-sm text-slate-500">Your credit activity will appear here.</p>
      </div>
    );
  }

  const totalPages = Math.max(1, Math.ceil(totalCount / perPage));
  const start = (page - 1) * perPage + 1;
  const end = Math.min(totalCount, page * perPage);

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <ul className="divide-y divide-slate-100">
          {transactions.map((tx) => {
            const isGrant = tx.type === "grant";
            const badgeClass = isGrant ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700";
            const signedAmount = isGrant ? `+${tx.amount}` : `-${tx.amount}`;

            return (
              <li key={tx.id} className="flex flex-col gap-2 p-4 md:flex-row md:items-center md:justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${badgeClass}`}>
                      {isGrant ? "Grant" : "Used"}
                    </span>
                    <p className="text-sm font-semibold text-slate-900">{signedAmount} credits</p>
                  </div>
                  <p className="text-xs text-slate-500">
                    {isGrant
                      ? tx.notes || tx.source || "Credit grant"
                      : tx.job_id
                        ? `Job #${tx.job_id.slice(0, 8)} completion`
                        : "Credit consumption"}
                  </p>
                </div>
                <p className="text-xs text-slate-500">{formatStableDateTime(tx.created_at)} UTC</p>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="flex items-center justify-between text-sm text-slate-500">
        <p>
          Showing {start}-{end} of {totalCount}
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            className="rounded-full border border-slate-200 px-3 py-1 disabled:opacity-40"
          >
            Previous
          </button>
          <span>
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            className="rounded-full border border-slate-200 px-3 py-1 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
