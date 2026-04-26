/**
 * hooks/useAnalysis.ts
 * Central state machine for the resume analysis workflow.
 *
 * Fix: jobDescription is now stored in state so the AnalysisDashboard
 * can pass the real JD to the enhance endpoint (not the match_summary).
 */
"use client";

import { useCallback, useReducer, useRef } from "react";
import { analyzeResume, AlignApiError, validateResumeFile } from "@/lib/api-client";
import type { AnalysisState, AnalysisStatus, ErrorDetail } from "@/types/api";
import type { AnalysisResponse } from "@/types/api";

// ─── State / Actions ──────────────────────────────────────────────────────────

interface ExtendedState extends AnalysisState {
  /** The job description submitted with the current analysis — needed for enhance */
  jobDescription: string;
}

type Action =
  | { type: "START_UPLOAD" }
  | { type: "PROGRESS"; payload: number }
  | { type: "SET_STATUS"; payload: AnalysisStatus }
  | { type: "SUCCESS"; payload: { result: AnalysisResponse; jobDescription: string } }
  | { type: "ERROR"; payload: ErrorDetail }
  | { type: "RESET" };

const initialState: ExtendedState = {
  status: "idle",
  result: null,
  error: null,
  uploadProgress: 0,
  jobDescription: "",
};

function reducer(state: ExtendedState, action: Action): ExtendedState {
  switch (action.type) {
    case "START_UPLOAD":
      return { ...initialState, status: "uploading" };
    case "PROGRESS":
      return { ...state, uploadProgress: action.payload };
    case "SET_STATUS":
      return { ...state, status: action.payload };
    case "SUCCESS":
      return {
        ...state,
        status: "success",
        result: action.payload.result,
        jobDescription: action.payload.jobDescription,
        error: null,
      };
    case "ERROR":
      return { ...state, status: "error", error: action.payload };
    case "RESET":
      return initialState;
    default:
      return state;
  }
}

// ─── Status messages ──────────────────────────────────────────────────────────

export const STATUS_MESSAGES: Record<AnalysisStatus, string> = {
  idle:            "Ready",
  uploading:       "Uploading resume…",
  embedding:       "Generating AI embeddings…",
  scoring:         "Computing match score…",
  reasoning:       "Analysing skill gaps…",
  building_resume: "Crafting your ATS resume…",
  saving:          "Saving results…",
  success:         "Analysis complete!",
  error:           "Analysis failed",
};

export const STATUS_STEPS: AnalysisStatus[] = [
  "uploading", "embedding", "scoring", "reasoning", "building_resume", "saving", "success",
];

// ─── Hook ─────────────────────────────────────────────────────────────────────

export interface UseAnalysisReturn {
  state: ExtendedState;
  submit: (resume: File, jobDescription: string) => Promise<void>;
  reset: () => void;
  isLoading: boolean;
}

export function useAnalysis(): UseAnalysisReturn {
  const [state, dispatch] = useReducer(reducer, initialState);
  const abortRef = useRef<(() => void) | null>(null);

  const isLoading =
    state.status !== "idle" &&
    state.status !== "success" &&
    state.status !== "error";

  const runStepSimulation = useCallback((signal: { cancelled: boolean }) => {
    const steps: Array<[AnalysisStatus, number]> = [
      ["embedding",       3000],
      ["scoring",         5500],
      ["reasoning",       8000],
      ["building_resume", 12000],
      ["saving",          17000],
    ];
    steps.forEach(([status, delay]) => {
      setTimeout(() => {
        if (!signal.cancelled) dispatch({ type: "SET_STATUS", payload: status });
      }, delay);
    });
  }, []);

  const submit = useCallback(async (resume: File, jobDescription: string): Promise<void> => {
    const fileError = validateResumeFile(
      resume,
      Number(process.env.NEXT_PUBLIC_MAX_FILE_SIZE_MB ?? 10)
    );
    if (fileError) { dispatch({ type: "ERROR", payload: fileError }); return; }

    if (jobDescription.trim().length < 50) {
      dispatch({
        type: "ERROR",
        payload: { code: "JD_TOO_SHORT", message: "Job description must be at least 50 characters.", field: "job_description" },
      });
      return;
    }

    dispatch({ type: "START_UPLOAD" });
    const signal = { cancelled: false };
    abortRef.current = () => { signal.cancelled = true; };
    runStepSimulation(signal);

    try {
      const result = await analyzeResume({
        resume,
        jobDescription: jobDescription.trim(),
        onProgress: (pct) => dispatch({ type: "PROGRESS", payload: pct }),
      });
      signal.cancelled = true;
      dispatch({ type: "SUCCESS", payload: { result, jobDescription: jobDescription.trim() } });
    } catch (err) {
      signal.cancelled = true;
      if (err instanceof AlignApiError) {
        dispatch({ type: "ERROR", payload: err.detail });
      } else {
        dispatch({ type: "ERROR", payload: { code: "UNKNOWN_ERROR", message: "An unexpected error occurred. Please try again." } });
      }
    }
  }, [runStepSimulation]);

  const reset = useCallback(() => {
    abortRef.current?.();
    abortRef.current = null;
    dispatch({ type: "RESET" });
  }, []);

  return { state, submit, reset, isLoading };
}
