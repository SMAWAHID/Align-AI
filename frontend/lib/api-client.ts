/**
 * lib/api-client.ts — Typed API client with progress tracking.
 */
import type {
  AnalysisResponse, ApiErrorResponse, ErrorDetail,
  HistoryResponse, EnhanceResumeRequest, EnhanceResumeResponse,
  DownloadRequest, DownloadFormat,
} from "@/types/api";
import { isApiError } from "@/types/api";

// In production the API lives on a different origin (the Render service), so
// requests go straight there rather than through the Next.js rewrite — a proxied
// request would hit the platform's edge timeout while a sleeping free dyno wakes.
// With NEXT_PUBLIC_API_URL unset (local dev) this stays relative and the rewrite
// in next.config.ts forwards to localhost:8000 exactly as before.
export const API_ORIGIN = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

const BASE_URL = `${API_ORIGIN}/api/v1`;

// ─── Session ─────────────────────────────────────────────────────────────────
// The JWT lives in localStorage so a refresh keeps you signed in. Reads are
// guarded because the accessor throws outright in some privacy modes.

const TOKEN_KEY = "alignai_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable — the session simply will not survive a reload */
  }
}

/** Authorization header for the current session, or {} when signed out. */
function auth(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export class AlignApiError extends Error {
  constructor(public readonly detail: ErrorDetail, public readonly status: number) {
    super(detail.message);
    this.name = "AlignApiError";
  }
}

async function parseError(res: Response): Promise<AlignApiError> {
  let body: unknown;
  try { body = await res.json(); } catch { body = null; }
  if (isApiError(body)) return new AlignApiError(body.detail, res.status);
  return new AlignApiError({ code: "HTTP_ERROR", message: res.statusText || `HTTP ${res.status}` }, res.status);
}

// ─── Analyze ─────────────────────────────────────────────────────────────────

export interface AnalyzePayload {
  resume: File;
  jobDescription: string;
  onProgress?: (pct: number) => void;
}

export function analyzeResume({ resume, jobDescription, onProgress }: AnalyzePayload): Promise<AnalysisResponse> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("resume", resume, resume.name);
    form.append("job_description", jobDescription);

    const xhr = new XMLHttpRequest();
    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
    });
    xhr.addEventListener("load", () => {
      let body: unknown;
      try { body = JSON.parse(xhr.responseText); } catch { body = null; }
      if (xhr.status >= 200 && xhr.status < 300) { resolve(body as AnalysisResponse); return; }
      if (isApiError(body)) { reject(new AlignApiError((body as ApiErrorResponse).detail, xhr.status)); return; }
      reject(new AlignApiError({ code: "HTTP_ERROR", message: `Request failed with status ${xhr.status}` }, xhr.status));
    });
    xhr.addEventListener("error", () =>
      reject(new AlignApiError({ code: "NETWORK_ERROR", message: "Network error. Please check your connection." }, 0)));
    xhr.addEventListener("timeout", () =>
      reject(new AlignApiError({ code: "TIMEOUT", message: "Request timed out. Please try again." }, 408)));
    xhr.open("POST", `${BASE_URL}/analyze`);
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.timeout = 120_000;
    xhr.send(form);
  });
}

// ─── Enhance ─────────────────────────────────────────────────────────────────

export async function enhanceResume(payload: EnhanceResumeRequest): Promise<EnhanceResumeResponse> {
  const res = await fetch(`${BASE_URL}/resume/enhance`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...auth() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await parseError(res);
  return res.json() as Promise<EnhanceResumeResponse>;
}

// ─── Download ─────────────────────────────────────────────────────────────────

export async function downloadResume(payload: DownloadRequest): Promise<void> {
  const res = await fetch(`${BASE_URL}/resume/download`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...auth() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await parseError(res);

  const blob        = await res.blob();
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match       = disposition.match(/filename="?([^"]+)"?/);
  const filename    = match?.[1] ?? `resume.${payload.format}`;

  const url = URL.createObjectURL(blob);
  const a   = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// ─── History ──────────────────────────────────────────────────────────────────

export async function fetchHistory(page = 1, pageSize = 10): Promise<HistoryResponse> {
  const res = await fetch(`${BASE_URL}/history?page=${page}&page_size=${pageSize}`, { cache: "no-store", headers: auth() });
  if (!res.ok) throw await parseError(res);
  return res.json() as Promise<HistoryResponse>;
}

export async function fetchHistoryItem(id: number): Promise<AnalysisResponse> {
  const res = await fetch(`${BASE_URL}/history/${id}`, { cache: "no-store", headers: auth() });
  if (!res.ok) throw await parseError(res);
  return res.json() as Promise<AnalysisResponse>;
}

export async function deleteHistoryItem(id: number): Promise<void> {
  const res = await fetch(`${BASE_URL}/history/${id}`, { method: "DELETE", headers: auth() });
  if (!res.ok && res.status !== 204) throw await parseError(res);
}

// ─── File validation (client-side) ───────────────────────────────────────────

export function validateResumeFile(file: File, maxMb = 10): ErrorDetail | null {
  const ext = file.name.split(".").pop()?.toLowerCase();
  if (!["pdf", "docx", "txt"].includes(ext ?? "")) {
    return { code: "INVALID_TYPE", message: "Only PDF, DOCX, and TXT files are supported.", field: "resume" };
  }
  if (file.size > maxMb * 1024 * 1024) {
    return { code: "FILE_TOO_LARGE", message: `File must be smaller than ${maxMb} MB.`, field: "resume" };
  }
  if (file.size < 512) {
    return { code: "FILE_TOO_SMALL", message: "File appears to be empty or corrupt.", field: "resume" };
  }
  return null;
}

// ─── Auth ────────────────────────────────────────────────────────────────────

export interface AuthUser {
  id: number;
  email: string;
  full_name: string;
  created_at: string;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

async function postAuth(path: string, body: unknown): Promise<TokenResponse> {
  const res = await fetch(`${BASE_URL}/auth/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await parseError(res);
  return res.json() as Promise<TokenResponse>;
}

export function signup(email: string, password: string, fullName: string) {
  return postAuth("signup", { email, password, full_name: fullName });
}

export function login(email: string, password: string) {
  return postAuth("login", { email, password });
}

export async function fetchMe(): Promise<AuthUser> {
  const res = await fetch(`${BASE_URL}/auth/me`, { cache: "no-store", headers: auth() });
  if (!res.ok) throw await parseError(res);
  return res.json() as Promise<AuthUser>;
}
