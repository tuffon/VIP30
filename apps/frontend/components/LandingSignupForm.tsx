"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type Props = {
  apiBase: string;
  defaultEmail?: string;
};

type Status = "idle" | "loading" | "success" | "error";

export function LandingSignupForm({ apiBase, defaultEmail }: Props) {
  const [email, setEmail] = useState(defaultEmail ?? "");
  const [name, setName] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState<string | null>(null);

  const endpoint = useMemo(() => `${apiBase.replace(/\/$/, "")}/marketing/signup`, [apiBase]);

  useEffect(() => {
    if (defaultEmail) {
      setEmail(defaultEmail);
    }
  }, [defaultEmail]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email) {
      setMessage("Please enter an email address.");
      return;
    }
    setStatus("loading");
    setMessage(null);
    try {
      const resp = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          name: name || undefined,
          source: "scopevista-landing",
        }),
      });
      if (!resp.ok) {
        throw new Error(`Signup failed (${resp.status})`);
      }
      setStatus("success");
      setMessage("Thanks! We'll keep you posted.");
    } catch (err) {
      setStatus("error");
      setMessage(err instanceof Error ? err.message : "Unable to save email right now.");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-10 flex flex-col gap-3 md:flex-row">
      <div className="flex-1">
        <label htmlFor="early-access-email" className="sr-only">
          Email address
        </label>
        <input
          id="early-access-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@firm.com"
          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-base text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none"
          required
        />
      </div>
      <div className="md:w-48">
        <label htmlFor="early-access-name" className="sr-only">
          Name
        </label>
        <input
          id="early-access-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Your name"
          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-base text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none"
        />
      </div>
      <button
        type="submit"
        disabled={status === "loading"}
        className="rounded-2xl bg-slate-900 px-6 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-60"
      >
        {status === "loading" ? "Joining…" : "Join the list"}
      </button>
      {message && (
        <p className={`text-sm ${status === "success" ? "text-emerald-600" : "text-rose-500"}`}>{message}</p>
      )}
    </form>
  );
}

