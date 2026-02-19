"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type AdminUserItem = {
  id: string;
  email: string;
  role: string;
  workspace_id: string;
  workspace_name?: string;
  created_at: string;
  balance: number;
};

type AdminUsersResponse = {
  items: AdminUserItem[];
  total_count: number;
  page: number;
  per_page: number;
};

type AuthMePayload = {
  user?: {
    role?: string;
  };
};

export default function AdminPage() {
  const apiBase = useMemo(() => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:4000", []);
  const [authorized, setAuthorized] = useState(false);
  const [loading, setLoading] = useState(true);
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busyByUser, setBusyByUser] = useState<Record<string, boolean>>({});
  const [grantAmountByUser, setGrantAmountByUser] = useState<Record<string, string>>({});

  const loadUsers = useCallback(async () => {
    setError(null);
    const query = search.trim() ? `?search=${encodeURIComponent(search.trim())}` : "";
    const response = await fetch(`${apiBase.replace(/\/$/, "")}/admin/users${query}`, {
      credentials: "include",
    });
    if (!response.ok) {
      if (response.status === 403) {
        setAuthorized(false);
      }
      throw new Error(`Failed to load users (${response.status})`);
    }
    const payload = (await response.json()) as AdminUsersResponse;
    setUsers(payload.items || []);
  }, [apiBase, search]);

  useEffect(() => {
    let mounted = true;

    async function init() {
      setLoading(true);
      setError(null);
      try {
        const me = await fetch(`${apiBase.replace(/\/$/, "")}/auth/me`, { credentials: "include" });
        if (!me.ok) {
          setAuthorized(false);
          return;
        }
        const mePayload = (await me.json()) as AuthMePayload;
        const isAdmin = mePayload.user?.role === "admin";
        setAuthorized(isAdmin);
        if (!isAdmin) return;

        await loadUsers();
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "Failed to initialize admin portal");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    void init();
    return () => {
      mounted = false;
    };
  }, [apiBase, loadUsers]);

  async function onSearchSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  }

  async function grantCredits(userId: string) {
    const amountRaw = grantAmountByUser[userId] ?? "";
    const amount = Number.parseInt(amountRaw, 10);
    if (!amount || amount <= 0) {
      setError("Grant amount must be greater than 0");
      return;
    }

    setBusyByUser((prev) => ({ ...prev, [userId]: true }));
    setError(null);
    try {
      const response = await fetch(`${apiBase.replace(/\/$/, "")}/admin/users/${userId}/credits/grant`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ amount, notes: "Admin portal grant" }),
      });
      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || `Grant failed (${response.status})`);
      }
      setGrantAmountByUser((prev) => ({ ...prev, [userId]: "" }));
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to grant credits");
    } finally {
      setBusyByUser((prev) => ({ ...prev, [userId]: false }));
    }
  }

  if (loading) {
    return <main className="mx-auto max-w-6xl px-6 py-10">Loading admin portal...</main>;
  }

  if (!authorized) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <h1 className="text-2xl font-semibold text-slate-900">Admin Portal</h1>
        <p className="mt-3 text-slate-600">You do not have admin access.</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900">Admin Portal</h1>
        <p className="mt-2 text-sm text-slate-600">Manage users and grant testing credits.</p>
      </div>

      <form onSubmit={onSearchSubmit} className="mb-6 flex gap-3">
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by email"
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <button type="submit" className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white">
          Search
        </button>
      </form>

      {error ? <p className="mb-4 rounded-md bg-rose-50 p-3 text-sm text-rose-700">{error}</p> : null}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left">
            <tr>
              <th className="px-4 py-3 font-semibold text-slate-700">Email</th>
              <th className="px-4 py-3 font-semibold text-slate-700">Role</th>
              <th className="px-4 py-3 font-semibold text-slate-700">Workspace</th>
              <th className="px-4 py-3 font-semibold text-slate-700">Balance</th>
              <th className="px-4 py-3 font-semibold text-slate-700">Grant Credits</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {users.map((user) => {
              const busy = busyByUser[user.id] === true;
              return (
                <tr key={user.id}>
                  <td className="px-4 py-3 text-slate-900">{user.email}</td>
                  <td className="px-4 py-3 text-slate-700">{user.role}</td>
                  <td className="px-4 py-3 text-slate-700">{user.workspace_name || user.workspace_id}</td>
                  <td className="px-4 py-3 font-semibold text-slate-900">{user.balance}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <input
                        value={grantAmountByUser[user.id] ?? ""}
                        onChange={(event) =>
                          setGrantAmountByUser((prev) => ({ ...prev, [user.id]: event.target.value }))
                        }
                        placeholder="Amount"
                        className="w-24 rounded-md border border-slate-300 px-2 py-1"
                      />
                      <button
                        type="button"
                        onClick={() => void grantCredits(user.id)}
                        disabled={busy}
                        className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-60"
                      >
                        {busy ? "Granting..." : "Grant"}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {users.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                  No users found.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </main>
  );
}
