"use client";

import { CheckCircle2, Circle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  STATUS_MESSAGES,
  STATUS_STEPS,
  type UseAnalysisReturn,
} from "@/hooks/useAnalysis";
import type { AnalysisStatus } from "@/types/api";

interface LoadingStepperProps {
  status: AnalysisStatus;
  uploadProgress: number;
}

export function LoadingStepper({ status, uploadProgress }: LoadingStepperProps) {
  const currentIndex = STATUS_STEPS.indexOf(status);

  return (
    <div className="flex flex-col items-center justify-center py-12 space-y-8">
      {/* Central spinner */}
      <div className="relative">
        <div className="w-20 h-20 rounded-full bg-indigo-500/10 flex items-center justify-center">
          <Loader2 size={32} className="text-indigo-400 animate-spin" />
        </div>
        <div className="absolute inset-0 rounded-full border-2 border-indigo-500/20 animate-ping" />
      </div>

      {/* Current status message */}
      <div className="text-center space-y-1">
        <p className="text-white font-semibold text-base">
          {STATUS_MESSAGES[status]}
        </p>
        {status === "uploading" && (
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
      </div>

      {/* Step list */}
      <div className="space-y-3 w-full max-w-xs">
        {STATUS_STEPS.filter((s) => s !== "success").map((step, i) => {
          const done = i < currentIndex;
          const active = i === currentIndex;

          return (
            <div key={step} className="flex items-center gap-3">
              <div className="flex-shrink-0">
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
                  "text-sm",
                  done && "text-white/50 line-through",
                  active && "text-white font-medium",
                  !done && !active && "text-white/25"
                )}
              >
                {STATUS_MESSAGES[step]}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
