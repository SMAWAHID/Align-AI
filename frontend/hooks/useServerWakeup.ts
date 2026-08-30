"use client";

/**
 * useServerWakeup — polls the API's /health endpoint on mount.
 *
 * The API runs on a free host that suspends the container after ~15 minutes of
 * inactivity, so the first visitor after a quiet period waits ~50s for a cold
 * start. Without this the UI just appears to hang. Polling early means the wake
 * begins while the user is still reading the page, and the state drives an
 * honest "server is waking up" message instead of a silent stall.
 */
import { useEffect, useState } from "react";
import { API_ORIGIN } from "@/lib/api-client";

export type ServerState = "checking" | "waking" | "ready" | "unreachable";

/** Below this, a normal request. Above it, assume the container is asleep. */
const SLOW_AFTER_MS = 2_500;
const RETRY_DELAY_MS = 3_000;
const GIVE_UP_AFTER_MS = 120_000;

export function useServerWakeup(): ServerState {
  const [state, setState] = useState<ServerState>("checking");

  useEffect(() => {
    let cancelled = false;
    const startedAt = Date.now();

    const slowTimer = setTimeout(() => {
      if (!cancelled) setState((s) => (s === "checking" ? "waking" : s));
    }, SLOW_AFTER_MS);

    async function poll(): Promise<void> {
      while (!cancelled) {
        try {
          const res = await fetch(`${API_ORIGIN}/health`, { cache: "no-store" });
          if (res.ok) {
            if (!cancelled) setState("ready");
            return;
          }
        } catch {
          // Connection refused / reset — the container is still booting.
        }
        if (Date.now() - startedAt > GIVE_UP_AFTER_MS) {
          if (!cancelled) setState("unreachable");
          return;
        }
        if (!cancelled) setState("waking");
        await new Promise((r) => setTimeout(r, RETRY_DELAY_MS));
      }
    }

    void poll();
    return () => {
      cancelled = true;
      clearTimeout(slowTimer);
    };
  }, []);

  return state;
}
