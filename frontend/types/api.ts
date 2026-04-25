/**
 * types/api.ts — Single source of truth for all API contracts.
 * Mirrors backend schemas.py exactly.
 */

// ─── Sub-types ────────────────────────────────────────────────────────────────

export interface SkillResource {
  readonly title: string;
  readonly url: string;
  readonly type: "docs" | "course" | "video" | "tutorial" | "other";
}

export interface SkillWithResources {
  readonly skill: string;
  readonly resources: readonly SkillResource[];
}

export interface GapAnalysisReport {
  readonly missing_skills: readonly string[];
  readonly skill_resources: readonly SkillWithResources[];
  readonly improvements: readonly string[];
  readonly match_summary: string;
}

export interface ScoreBreakdown {
  readonly semantic: number;
  readonly keyword: number;
  readonly final: number;
}

export interface AnalysisResponse {
  readonly id: number;
  readonly filename: string;
  readonly score_breakdown: ScoreBreakdown;
  readonly gap_analysis: GapAnalysisReport | null;
  readonly ats_resume: string | null;
  readonly created_at: string;
}

export interface HistoryItem {
  readonly id: number;
  readonly filename: string;
  readonly job_description_snippet: string;
  readonly match_score: number;
  readonly created_at: string;
}

export interface HistoryResponse {
  readonly items: readonly HistoryItem[];
  readonly total: number;
  readonly page: number;
  readonly page_size: number;
}

// ─── Resume enhance / download ────────────────────────────────────────────────

export interface EnhanceResumeRequest {
  current_resume: string;
  selected_skills: string[];
  selected_improvements: string[];
  job_description: string;
}

export interface EnhanceResumeResponse {
  readonly enhanced_resume: string;
  readonly provider: string;
}

export type DownloadFormat = "txt" | "md" | "pdf" | "docx";

export interface DownloadRequest {
  content: string;
  format: DownloadFormat;
  filename: string;
}

// ─── Errors ───────────────────────────────────────────────────────────────────

export interface ErrorDetail {
  readonly code: string;
  readonly message: string;
  readonly field?: string;
}

export interface ApiErrorResponse {
  readonly detail: ErrorDetail;
}

// ─── Analysis state ───────────────────────────────────────────────────────────

export type AnalysisStatus =
  | "idle" | "uploading" | "embedding" | "scoring"
  | "reasoning" | "building_resume" | "saving"
  | "success" | "error";

export interface AnalysisState {
  status: AnalysisStatus;
  result: AnalysisResponse | null;
  error: ErrorDetail | null;
  uploadProgress: number;
}

// ─── Type guards ──────────────────────────────────────────────────────────────

export function isApiError(data: unknown): data is ApiErrorResponse {
  return typeof data === "object" && data !== null && "detail" in data &&
    typeof (data as ApiErrorResponse).detail?.code === "string";
}

export function hasGapAnalysis(r: AnalysisResponse): r is AnalysisResponse & { gap_analysis: GapAnalysisReport } {
  return r.gap_analysis !== null;
}

export function hasAtsResume(r: AnalysisResponse): r is AnalysisResponse & { ats_resume: string } {
  return r.ats_resume !== null && r.ats_resume.length > 0;
}

// ─── Score tiers ──────────────────────────────────────────────────────────────

export const SCORE_THRESHOLDS = { excellent: 85, good: 70, fair: 50 } as const;
export type ScoreTier = "excellent" | "good" | "fair" | "poor";

export function getScoreTier(score: number): ScoreTier {
  if (score >= SCORE_THRESHOLDS.excellent) return "excellent";
  if (score >= SCORE_THRESHOLDS.good)      return "good";
  if (score >= SCORE_THRESHOLDS.fair)      return "fair";
  return "poor";
}

export const SCORE_TIER_LABELS: Record<ScoreTier, string> = {
  excellent: "Strong Match", good: "Good Match", fair: "Partial Match", poor: "Weak Match",
};

export const SCORE_TIER_COLORS: Record<ScoreTier, string> = {
  excellent: "#10b981", good: "#3b82f6", fair: "#f59e0b", poor: "#ef4444",
};
