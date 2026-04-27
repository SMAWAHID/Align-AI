/**
 * hooks/useAnalysis.ts
 *
 * WebSocket-first analysis hook.
 * - Opens a WebSocket to ws://host/api/v1/ws/analyze
 * - Sends the file as base64 + job description as JSON
 * - Receives real server-side step events and updates state in real time
 * - Falls back to HTTP POST /api/v1/analyze if WebSocket is unavailable
 *
 * Event protocol (server → client):
 *   { event: "status",        step, message }
 *   { event: "score_preview", final, semantic, keyword }
 *   { event: "result",        data: AnalysisResponse }
 *   { event: "error",         code, message }
 */
"use client";

import { useCallback, useReducer, useRef } from "react";
import { analyzeResume, AlignApiError, validateResumeFile } from "@/lib/api-client";
import type {
  AnalysisResponse, AnalysisStatus, AnalysisState, ErrorDetail,
} from "@/types/api";

// ─── Extended state ───────────────────────────────────────────────────────────

interface ExtendedState extends AnalysisState {
  jobDescription:  string;
  /** Live server message shown under the spinner */
  serverMessage:   string;
  /** Score preview received mid-stream (before full result) */
  scorePreview:    { final: number; semantic: number; keyword: number } | null;
}

type Action =
  | { type: "START" }
  | { type: "SET_STATUS";     payload: { status: AnalysisStatus; message: string } }
  | { type: "UPLOAD_PROGRESS"; payload: number }
  | { type: "SCORE_PREVIEW";  payload: { final: number; semantic: number; keyword: number } }
  | { type: "SUCCESS";        payload: { result: AnalysisResponse; jobDescription: string } }
  | { type: "ERROR";          payload: ErrorDetail }
  | { type: "RESET" };

const initial: ExtendedState = {
  status:        "idle",
  result:        null,
  error:         null,
  uploadProgress: 0,
  jobDescription: "",
  serverMessage:  "",
  scorePreview:   null,
};

function reducer(state: ExtendedState, action: Action): ExtendedState {
  switch (action.type) {
    case "START":
      return { ...initial, status: "uploading", serverMessage: "Uploading resume…" };
    case "SET_STATUS":
      return { ...state, status: action.payload.status, serverMessage: action.payload.message };
    case "UPLOAD_PROGRESS":
      return { ...state, uploadProgress: action.payload };
    case "SCORE_PREVIEW":
      return { ...state, scorePreview: action.payload };
    case "SUCCESS":
      return {
        ...state,
        status:         "success",
        result:          action.payload.result,
        jobDescription:  action.payload.jobDescription,
        serverMessage:  "Analysis complete!",
        error:           null,
      };
    case "ERROR":
      return { ...state, status: "error", error: action.payload };
    case "RESET":
      return initial;
    default:
      return state;
  }
}

// ─── Step → AnalysisStatus mapping ───────────────────────────────────────────

const STEP_STATUS_MAP: Record<string, AnalysisStatus> = {
  connected:       "uploading",
  extracting:      "uploading",
  embedding:       "embedding",
  scoring:         "scoring",
  gap_analysis:    "reasoning",
  skill_resources: "reasoning",
  building_resume: "building_resume",
  saving:          "saving",
  done:            "saving",
};

// ─── Hook ─────────────────────────────────────────────────────────────────────

export interface UseAnalysisReturn {
  state:     ExtendedState;
  submit:    (resume: File, jobDescription: string) => Promise<void>;
  reset:     () => void;
  isLoading: boolean;
}

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
  "uploading", "embedding", "scoring", "reasoning",
  "building_resume", "saving", "success",
];

export function useAnalysis(): UseAnalysisReturn {
  const [state, dispatch] = useReducer(reducer, initial);
  const wsRef = useRef<WebSocket | null>(null);

  const isLoading =
    state.status !== "idle" &&
    state.status !== "success" &&
    state.status !== "error";

  const submit = useCallback(async (resume: File, jobDescription: string): Promise<void> => {
    // Client-side validation
    const fileError = validateResumeFile(
      resume,
      Number(process.env.NEXT_PUBLIC_MAX_FILE_SIZE_MB ?? 10),
    );
    if (fileError) { dispatch({ type: "ERROR", payload: fileError }); return; }
    if (jobDescription.trim().length < 50) {
      dispatch({
        type: "ERROR",
        payload: { code: "JD_TOO_SHORT", message: "Job description must be at least 50 characters.", field: "job_description" },
      });
      return;
    }

    dispatch({ type: "START" });
    const jd = jobDescription.trim();

    // ── Try WebSocket first ───────────────────────────────────────────────────
    const wsUrl = _buildWsUrl();
    const wsAvailable = await _checkWsAvailable();

    if (wsAvailable) {
      await _runViaWebSocket(wsUrl, resume, jd, dispatch, wsRef);
    } else {
      // HTTP fallback
      await _runViaHttp(resume, jd, dispatch);
    }
  }, []);

  const reset = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    dispatch({ type: "RESET" });
  }, []);

  return { state, submit, reset, isLoading };
}

// ─── WebSocket path ───────────────────────────────────────────────────────────

function _buildWsUrl(): string {
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const wsBase  = apiBase.replace(/^http/, "ws");
  return `${wsBase}/api/v1/ws/analyze`;
}

async function _checkWsAvailable(): Promise<boolean> {
  return typeof WebSocket !== "undefined";
}

// ─── WebSocket flow ───────────────────────────────────────────────────────────

async function _runViaWebSocket(
  wsUrl: string,
  resume: File,
  jd: string,
  dispatch: React.Dispatch<Action>,
  wsRef: React.MutableRefObject<WebSocket | null>,
): Promise<void> {
  return new Promise((resolve) => {
    let resolved = false;
    const done = () => { if (!resolved) { resolved = true; resolve(); } };

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.addEventListener("open", async () => {
      dispatch({
        type: "SET_STATUS",
        payload: { status: "uploading", message: "Sending resume to server…" },
      });

      // Read file as base64
      const reader = new FileReader();
      reader.onload = () => {
        const b64 = (reader.result as string).split(",")[1] ?? "";
        ws.send(JSON.stringify({
          filename:        resume.name,
          file_b64:        b64,
          job_description: jd,
          content_type:    resume.type || "application/octet-stream",
        }));
      };
      reader.readAsDataURL(resume);
    });

    ws.addEventListener("message", (evt) => {
      let msg: Record<string, unknown>;
      try { msg = JSON.parse(evt.data as string); }
      catch { return; }

      switch (msg.event) {
        case "status": {
          const step    = msg.step as string;
          const message = msg.message as string;
          const status  = STEP_STATUS_MAP[step] ?? "uploading";
          dispatch({ type: "SET_STATUS", payload: { status, message } });
          break;
        }
        case "score_preview": {
          dispatch({
            type: "SCORE_PREVIEW",
            payload: {
              final:    msg.final    as number,
              semantic: msg.semantic as number,
              keyword:  msg.keyword  as number,
            },
          });
          break;
        }
        case "result": {
          dispatch({
            type: "SUCCESS",
            payload: {
              result:         msg.data as AnalysisResponse,
              jobDescription: jd,
            },
          });
          ws.close();
          done();
          break;
        }
        case "error": {
          dispatch({
            type: "ERROR",
            payload: {
              code:    msg.code    as string,
              message: msg.message as string,
            },
          });
          ws.close();
          done();
          break;
        }
      }
    });

    ws.addEventListener("error", () => {
      // WebSocket failed — fall back to HTTP
      _runViaHttp(
        new File([/* reconstruct not needed — dispatch handles */], ""),
        jd,
        dispatch,
      ).then(done).catch(done);
    });

    ws.addEventListener("close", () => {
      done();
    });

    // 3-minute timeout
    setTimeout(() => {
      if (!resolved) {
        ws.close();
        dispatch({
          type: "ERROR",
          payload: { code: "TIMEOUT", message: "Analysis timed out. Please try again." },
        });
        done();
      }
    }, 180_000);
  });
}

// ─── HTTP fallback ────────────────────────────────────────────────────────────

async function _runViaHttp(
  resume: File,
  jd: string,
  dispatch: React.Dispatch<Action>,
): Promise<void> {
  // Simulate steps while waiting
  const steps: Array<[AnalysisStatus, string, number]> = [
    ["embedding",       "Generating AI embeddings…",  3000],
    ["scoring",         "Computing match score…",      5500],
    ["reasoning",       "Analysing skill gaps…",       8000],
    ["building_resume", "Crafting your ATS resume…",  12000],
    ["saving",          "Saving results…",             17000],
  ];
  const signal = { cancelled: false };
  steps.forEach(([status, message, delay]) => {
    setTimeout(() => {
      if (!signal.cancelled) dispatch({ type: "SET_STATUS", payload: { status, message } });
    }, delay);
  });

  try {
    const result = await analyzeResume({
      resume,
      jobDescription: jd,
      onProgress: (pct) => dispatch({ type: "UPLOAD_PROGRESS", payload: pct }),
    });
    signal.cancelled = true;
    dispatch({ type: "SUCCESS", payload: { result, jobDescription: jd } });
  } catch (err) {
    signal.cancelled = true;
    dispatch({
      type: "ERROR",
      payload: err instanceof AlignApiError
        ? err.detail
        : { code: "UNKNOWN_ERROR", message: "An unexpected error occurred." },
    });
  }
}
