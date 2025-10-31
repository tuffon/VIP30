"use client";

import { useHealthQuery } from "../redux/services/api";

export default function Page() {
  const { data, isLoading } = useHealthQuery();

  return (
    <main className="min-h-screen flex items-center justify-center">
      <div className="p-6 rounded-xl border">
        <h1 className="text-2xl font-bold">VIP Claims SaaS</h1>
        <p className="mt-2 text-sm text-gray-600">
          Next.js + Tailwind + Redux Toolkit + RTK Query
        </p>
        <div className="mt-4">
          {isLoading ? "Pinging API…" : `Health: ${data?.ok ?? false}`}
        </div>
      </div>
    </main>
  );
}


