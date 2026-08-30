"use client";

import { AlertTriangle, Loader2 } from "lucide-react";
import type { ServerState } from "@/hooks/useServerWakeup";

/** Live API status in the nav bar — replaces a hardcoded "always green" dot. */
export function ServerStatusPill({ state }: { state: ServerState }) {
  const dot =
    state === "ready"
      ? "bg-emerald-400 animate-pulse"
      : state === "unreachable"
        ? "bg-red-400"
        : "bg-amber-400 animate-pulse";

  const label =
    state === "ready"
      ? "Jina + Groq / Gemini"
      : state === "unreachable"
        ? "API unreachable"
        : "Waking API…";

  return (
    <div className="hidden sm:flex items-center gap-1.5 text-xs text-white/40">
      <div className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      {label}
    </div>
  );
}

/** Explains the cold start rather than letting the page look frozen. */
export function ServerWakingBanner({ state }: { state: ServerState }) {
  if (state === "ready" || state === "checking") return null;

  if (state === "unreachable") {
    return (
      <div className="mx-auto max-w-6xl px-6">
        <div className="flex items-start gap-3 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          <p>
            The analysis API isn&apos;t responding. It runs on a free tier that sleeps when
            idle — try reloading in a minute.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-6">
      <div className="flex items-start gap-3 rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
        <Loader2 size={16} className="mt-0.5 shrink-0 animate-spin" />
        <p>
          <strong className="font-semibold">Waking the server up.</strong>{" "}
          The API sleeps after 15 minutes of inactivity on the free tier, so the first
          request can take up to a minute. You can fill in the form meanwhile.
        </p>
      </div>
    </div>
  );
}
