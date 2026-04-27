"use client";

import { CheckCircle2, Circle, Loader2, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { STATUS_MESSAGES, STATUS_STEPS } from "@/hooks/useAnalysis";
import type { AnalysisStatus } from "@/types/api";

interface LoadingStepperProps {
  status:        AnalysisStatus;
  uploadProgress: number;
  /** Real server message from WebSocket — shown instead of generic label */
  serverMessage?: string;
  /** Score preview received mid-stream */
  scorePreview?: { final: number; semantic: number; keyword: number } | null;
}

export function LoadingStepper({
  status,
  uploadProgress,
  serverMessage,
  scorePreview,
}: LoadingStepperProps) {
  const currentIndex = STATUS_STEPS.indexOf(status);
  const displayMsg   = serverMessage || STATUS_MESSAGES[status];

  return (
    <div className="flex flex-col items-center justify-center py-10 space-y-8">
      {/* Central spinner */}
      <div className="relative">
        <div className="w-20 h-20 rounded-full bg-indigo-500/10 flex items-center justify-center">
          <Loader2 size={32} className="text-indigo-400 animate-spin" />
        </div>
        <div className="absolute inset-0 rounded-full border-2 border-indigo-500/20 animate-ping" />
      </div>

      {/* Live server message */}
      <div className="text-center space-y-1 min-h-[48px]">
        <p className="text-white font-semibold text-base transition-all duration-300">
          {displayMsg}
        </p>

        {/* Upload progress bar */}
        {status === "uploading" && uploadProgress > 0 && (
          <div className="mt-3 w-48 mx-auto">
            <div className="flex justify-between text-xs text-white/40 mb-1.5">
              <span>Uploading</span>
              <span className="font-mono">{uploadProgress}%</span>
            </div>
            <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
              <div
                className="h-full bg-indigo-500 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}

        {/* Score preview card — shown as soon as server sends it */}
        {scorePreview && (
          <div className="mt-4 flex items-center gap-2 justify-center">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/[0.06] border border-white/10">
              <Zap size={12} className="text-amber-400" />
              <span className="text-xs text-white/60">Score preview:</span>
              <span
                className="text-sm font-bold font-mono"
                style={{ color: scorePreview.final >= 85 ? "#10b981" : scorePreview.final >= 70 ? "#3b82f6" : scorePreview.final >= 50 ? "#f59e0b" : "#ef4444" }}
              >
                {Math.round(scorePreview.final)}%
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Step list */}
      <div className="space-y-2.5 w-full max-w-xs">
        {STATUS_STEPS.filter((s) => s !== "success").map((step, i) => {
          const done   = i < currentIndex;
          const active = i === currentIndex;

          return (
            <div key={step} className="flex items-center gap-3">
              <div className="flex-shrink-0 w-[18px]">
                {done ? (
                  <CheckCircle2 size={18} className="text-emerald-400" />
                ) : active ? (
                  <Loader2 size={18} className="text-indigo-400 animate-spin" />
                ) : (
                  <Circle size={18} className="text-white/20" />
                )}
              </div>
              <span
                className={cn(
                  "text-sm transition-all duration-200",
                  done   && "text-white/40 line-through",
                  active && "text-white font-medium",
                  !done && !active && "text-white/25",
                )}
              >
                {STATUS_MESSAGES[step]}
              </span>
            </div>
          );
        })}
      </div>

      {/* WS indicator */}
      <div className="flex items-center gap-1.5 text-[10px] text-white/25">
        <div className="w-1.5 h-1.5 rounded-full bg-emerald-400/60 animate-pulse" />
        Live server updates via WebSocket
      </div>
    </div>
  );
}
