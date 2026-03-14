/**
 * types/api.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Single source of truth for AlignAI API contracts on the frontend.
 * Mirrors backend `schemas.py` 1-to-1. Any change in Pydantic models
 * MUST be reflected here.
 *
 * Conventions:
 *  - All dates are ISO-8601 strings from the API (parse with `new Date()`)
 *  - `null` fields are explicitly typed; `undefined` means "not in payload"
 *  - Readonly arrays prevent accidental mutation
 */

// ─── Sub-types ────────────────────────────────────────────────────────────────

/**
 * AI-generated gap report from Gemini Flash.
 * Only present on the response when final_score < 85.
 */
export interface GapAnalysisReport {
  readonly missing_skills: readonly string[];
  readonly improvements: readonly string[];
  readonly match_summary: string;
}

/**
 * Detailed score breakdown rendered as the radial chart + bars.
 */
export interface ScoreBreakdown {
  readonly semantic: number; // 0–100
  readonly keyword: number;  // 0–100
  readonly final: number;    // Weighted composite, 0–100
}

// ─── Responses ────────────────────────────────────────────────────────────────

/**
 * Full response from POST /api/v1/analyze.
 * `gap_analysis` and `ats_resume` may be null if score >= 85.
 */
export interface AnalysisResponse {
  readonly id: number;
  readonly filename: string;
  readonly score_breakdown: ScoreBreakdown;
  readonly gap_analysis: GapAnalysisReport | null;
  readonly ats_resume: string | null;
  readonly created_at: string; // ISO-8601
}

/**
 * Lightweight row for the history list.
 */
export interface HistoryItem {
  readonly id: number;
  readonly filename: string;
  readonly job_description_snippet: string;
  readonly match_score: number;
  readonly created_at: string;
}

/**
 * Paginated wrapper for GET /api/v1/history.
 */
export interface HistoryResponse {
  readonly items: readonly HistoryItem[];
  readonly total: number;
  readonly page: number;
  readonly page_size: number;
}

// ─── Error shapes ─────────────────────────────────────────────────────────────

export interface ErrorDetail {
  readonly code: string;
  readonly message: string;
  readonly field?: string;
}

export interface ApiErrorResponse {
  readonly detail: ErrorDetail;
}

// ─── Upload state ─────────────────────────────────────────────────────────────

export type AnalysisStatus =
  | "idle"
  | "uploading"
  | "embedding"
  | "scoring"
  | "reasoning"
  | "building_resume"
  | "saving"
  | "success"
  | "error";

/**
 * Internal state managed by `useAnalysis` hook.
 */
export interface AnalysisState {
  status: AnalysisStatus;
  result: AnalysisResponse | null;
  error: ErrorDetail | null;
  /** Upload progress (0–100) driven by XHR ProgressEvent */
  uploadProgress: number;
}

// ─── Type guards ──────────────────────────────────────────────────────────────

export function isApiError(data: unknown): data is ApiErrorResponse {
  return (
    typeof data === "object" &&
    data !== null &&
    "detail" in data &&
    typeof (data as ApiErrorResponse).detail?.code === "string"
  );
}

export function hasGapAnalysis(
  result: AnalysisResponse
): result is AnalysisResponse & { gap_analysis: GapAnalysisReport } {
  return result.gap_analysis !== null;
}

export function hasAtsResume(
  result: AnalysisResponse
): result is AnalysisResponse & { ats_resume: string } {
  return result.ats_resume !== null && result.ats_resume.length > 0;
}

// ─── Constants ────────────────────────────────────────────────────────────────

export const SCORE_THRESHOLDS = {
  excellent: 85,
  good: 70,
  fair: 50,
} as const;

export type ScoreTier = "excellent" | "good" | "fair" | "poor";

export function getScoreTier(score: number): ScoreTier {
  if (score >= SCORE_THRESHOLDS.excellent) return "excellent";
  if (score >= SCORE_THRESHOLDS.good) return "good";
  if (score >= SCORE_THRESHOLDS.fair) return "fair";
  return "poor";
}

export const SCORE_TIER_LABELS: Record<ScoreTier, string> = {
  excellent: "Strong Match",
  good: "Good Match",
  fair: "Partial Match",
  poor: "Weak Match",
};

export const SCORE_TIER_COLORS: Record<ScoreTier, string> = {
  excellent: "#10b981", // emerald-500
  good: "#3b82f6",     // blue-500
  fair: "#f59e0b",     // amber-500
  poor: "#ef4444",     // red-500
};
