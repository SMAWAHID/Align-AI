/**
 * lib/api-client.ts — Typed API client with progress tracking.
 */
import type {
  AnalysisResponse, ApiErrorResponse, ErrorDetail,
  HistoryResponse, EnhanceResumeRequest, EnhanceResumeResponse,
  DownloadRequest, DownloadFormat,
} from "@/types/api";
import { isApiError } from "@/types/api";

const BASE_URL = "/api/v1";

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
    xhr.addEventListener("error", () => reject(new AlignApiError({ code: "NETWORK_ERROR", message: "Network error. Please check your connection." }, 0)));
    xhr.addEventListener("timeout", () => reject(new AlignApiError({ code: "TIMEOUT", message: "Request timed out. Please try again." }, 408)));
    xhr.open("POST", `${BASE_URL}/analyze`);
    xhr.timeout = 120_000;
    xhr.send(form);
  });
}

// ─── Enhance ─────────────────────────────────────────────────────────────────

export async function enhanceResume(payload: EnhanceResumeRequest): Promise<EnhanceResumeResponse> {
  const res = await fetch(`${BASE_URL}/resume/enhance`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await parseError(res);
  return res.json() as Promise<EnhanceResumeResponse>;
}

// ─── Download ─────────────────────────────────────────────────────────────────

export async function downloadResume(payload: DownloadRequest): Promise<void> {
  const res = await fetch(`${BASE_URL}/resume/download`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await parseError(res);

  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match?.[1] ?? `resume.${payload.format}`;

  const url = URL.createObjectURL(blob);
  const a   = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// ─── History ──────────────────────────────────────────────────────────────────

export async function fetchHistory(page = 1, pageSize = 10): Promise<HistoryResponse> {
  const res = await fetch(`${BASE_URL}/history?page=${page}&page_size=${pageSize}`, { cache: "no-store" });
  if (!res.ok) throw await parseError(res);
  return res.json() as Promise<HistoryResponse>;
}

export async function fetchHistoryItem(id: number): Promise<AnalysisResponse> {
  const res = await fetch(`${BASE_URL}/history/${id}`, { cache: "no-store" });
  if (!res.ok) throw await parseError(res);
  return res.json() as Promise<AnalysisResponse>;
}

export async function deleteHistoryItem(id: number): Promise<void> {
  const res = await fetch(`${BASE_URL}/history/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw await parseError(res);
}

// ─── Validation ───────────────────────────────────────────────────────────────

export function validateResumeFile(file: File, maxMb = 10): ErrorDetail | null {
  if (file.type !== "application/pdf") return { code: "INVALID_TYPE", message: "Please upload a PDF file.", field: "resume" };
  if (file.size > maxMb * 1024 * 1024) return { code: "FILE_TOO_LARGE", message: `File must be smaller than ${maxMb} MB.`, field: "resume" };
  if (file.size < 1024) return { code: "FILE_TOO_SMALL", message: "File appears to be empty or corrupt.", field: "resume" };
  return null;
}
