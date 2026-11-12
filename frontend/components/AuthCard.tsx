"use client";

/**
 * Shared shell for the sign-in and sign-up forms. Both screens are the same
 * card with a different field set, so they share layout, error handling and
 * submit state rather than diverging into two near-copies.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AlertCircle, ArrowRight, Cpu, Loader2 } from "lucide-react";

import { useAuth } from "@/lib/auth";
import { AlignApiError } from "@/lib/api-client";

type Mode = "login" | "signup";

export function AuthCard({ mode }: { mode: Mode }) {
  const isSignup = mode === "signup";
  const { signIn, signUp, status } = useAuth();
  const router = useRouter();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Someone who is already signed in has no business on these screens.
  useEffect(() => {
    if (status === "authenticated") router.replace("/app");
  }, [status, router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (isSignup) await signUp(email, password, fullName);
      else await signIn(email, password);
      router.replace("/app");
    } catch (err) {
      setError(
        err instanceof AlignApiError
          ? err.detail.message
          : "Could not reach the server. It may still be waking up — try again in a moment.",
      );
      setBusy(false);
    }
  }

  return (
    <div className="min-h-dvh flex flex-col">
      <header className="border-b border-white/[0.06]">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
              <Cpu size={14} className="text-white" />
            </div>
            <span
              className="font-bold text-white tracking-tight group-hover:text-white/80 transition-colors"
              style={{ fontFamily: "'Syne', sans-serif", fontSize: "1.05rem" }}
            >
              AlignAI
            </span>
          </Link>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <h1
            className="text-2xl font-bold text-white mb-1.5"
            style={{ fontFamily: "'Syne', sans-serif" }}
          >
            {isSignup ? "Create your account" : "Welcome back"}
          </h1>
          <p className="text-sm text-white/40 mb-7">
            {isSignup
              ? "Your analyses are saved to your account and visible only to you."
              : "Sign in to run an analysis and see your history."}
          </p>

          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            {isSignup && (
              <Field
                label="Full name"
                type="text"
                value={fullName}
                onChange={setFullName}
                autoComplete="name"
                required
                minLength={2}
              />
            )}
            <Field
              label="Email"
              type="email"
              value={email}
              onChange={setEmail}
              autoComplete="email"
              required
            />
            <Field
              label="Password"
              type="password"
              value={password}
              onChange={setPassword}
              autoComplete={isSignup ? "new-password" : "current-password"}
              required
              minLength={isSignup ? 8 : undefined}
              hint={isSignup ? "At least 8 characters." : undefined}
            />

            {error && (
              <div
                role="alert"
                className="flex items-start gap-2.5 rounded-lg border border-red-500/25 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-200"
              >
                <AlertCircle size={15} className="mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="w-full h-11 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-white text-sm font-semibold flex items-center justify-center gap-2 shadow-lg shadow-indigo-500/25 transition-opacity hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
            >
              {busy ? (
                <>
                  <Loader2 size={15} className="animate-spin" />
                  {isSignup ? "Creating account…" : "Signing in…"}
                </>
              ) : (
                <>
                  {isSignup ? "Create account" : "Sign in"}
                  <ArrowRight size={15} />
                </>
              )}
            </button>
          </form>

          <p className="mt-6 text-sm text-white/35 text-center">
            {isSignup ? "Already have an account? " : "No account yet? "}
            <Link
              href={isSignup ? "/login" : "/signup"}
              className="text-indigo-300 hover:text-indigo-200 font-medium"
            >
              {isSignup ? "Sign in" : "Create one"}
            </Link>
          </p>
        </div>
      </main>
    </div>
  );
}

interface FieldProps {
  label: string;
  type: string;
  value: string;
  onChange: (v: string) => void;
  // tsconfig sets exactOptionalPropertyTypes, so `?` alone does not admit an
  // explicitly-passed undefined — these props are conditionally supplied.
  autoComplete?: string | undefined;
  required?: boolean | undefined;
  minLength?: number | undefined;
  hint?: string | undefined;
}

function Field({ label, type, value, onChange, autoComplete, required, minLength, hint }: FieldProps) {
  const id = `field-${label.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-medium text-white/50 mb-1.5">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        required={required}
        minLength={minLength}
        className="w-full h-11 rounded-lg bg-white/[0.03] border border-white/10 px-3.5 text-sm text-white placeholder-white/25 outline-none transition-colors focus:border-indigo-400/60 focus:bg-white/[0.05]"
      />
      {hint && <p className="mt-1.5 text-xs text-white/25">{hint}</p>}
    </div>
  );
}
