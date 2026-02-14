"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { AuthLayout } from "../../../components/AuthLayout";

const errorMessages: Record<string, string> = {
  invalid: "Invalid code. Please check and try again.",
  expired: "Code expired. Please request a new one.",
  too_many_attempts: "Too many attempts. Please request a new code.",
};

export default function VerifyPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const apiBase = useMemo(() => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:4000", []);
  const email = (searchParams.get("email") || "").trim().toLowerCase();

  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isResending, setIsResending] = useState(false);

  async function handleVerify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setInfo(null);

    if (!email) {
      setError("Please go back and enter your email first.");
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await fetch(`${apiBase.replace(/\/$/, "")}/auth/otp/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, code: code.trim() }),
      });

      if (response.ok) {
        router.push("/bid-comp");
        return;
      }

      const payload = await response.json().catch(() => null);
      const backendCode = payload?.detail?.error as string | undefined;
      setError(errorMessages[backendCode || ""] || "Verification failed. Please try again.");
    } catch {
      setError("Verification failed. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleResend() {
    setError(null);
    setInfo(null);

    if (!email) {
      setError("Please go back and enter your email first.");
      return;
    }

    setIsResending(true);
    try {
      const response = await fetch(`${apiBase.replace(/\/$/, "")}/auth/otp/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email }),
      });

      if (response.ok) {
        setInfo("A new code has been sent.");
        return;
      }

      if (response.status === 429) {
        setError("Too many requests. Please wait before trying again.");
        return;
      }

      setError("Unable to resend code right now.");
    } catch {
      setError("Unable to resend code right now.");
    } finally {
      setIsResending(false);
    }
  }

  return (
    <AuthLayout
      title="Verify your code"
      subtitle={email ? `Enter the 6-digit code sent to ${email}.` : "Enter your 6-digit verification code."}
    >
      <form className="space-y-4" onSubmit={handleVerify}>
        <label className="block text-sm font-medium text-slate-700" htmlFor="otp-code">
          Verification code
        </label>
        <input
          id="otp-code"
          inputMode="numeric"
          pattern="[0-9]{6}"
          maxLength={6}
          minLength={6}
          required
          value={code}
          onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
          placeholder="000000"
          className="w-full rounded-xl border border-slate-300 px-4 py-3 text-center text-2xl tracking-[0.5em] text-slate-900 placeholder:text-slate-300 focus:border-slate-900 focus:outline-none"
        />

        {error ? (
          <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>
        ) : null}
        {info ? (
          <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{info}</p>
        ) : null}

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSubmitting ? "Verifying..." : "Verify code"}
        </button>
      </form>

      <div className="mt-4 flex items-center justify-between text-sm">
        <Link href="/login" className="text-slate-500 transition hover:text-slate-900">
          Use different email
        </Link>
        <button
          type="button"
          onClick={handleResend}
          disabled={isResending}
          className="font-medium text-slate-700 transition hover:text-slate-900 disabled:opacity-60"
        >
          {isResending ? "Sending..." : "Resend code"}
        </button>
      </div>
    </AuthLayout>
  );
}
