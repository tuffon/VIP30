"use client";

import { signIn, signOut, useSession } from "next-auth/react";

export function NavAuth() {
  const { data: session, status } = useSession();
  const isLoading = status === "loading";

  if (isLoading) {
    return <span className="text-sm text-slate-400">Loading…</span>;
  }

  if (!session?.user) {
    return (
      <button
        type="button"
        onClick={() => signIn("google")}
        className="rounded-full border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100"
      >
        Sign in with Google
      </button>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm font-medium text-slate-600">
        {session.user.name || session.user.email}
      </span>
      <button
        type="button"
        onClick={() => signOut()}
        className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-100"
      >
        Sign out
      </button>
    </div>
  );
}

