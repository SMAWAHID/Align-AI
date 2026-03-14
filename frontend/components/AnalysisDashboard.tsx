"use client";

import { useState } from "react";
import {
  BarChart2,
  FileText,
  AlertCircle,
  RotateCcw,
  Sparkles,
  Clock,
  Hash,
} from "lucide-react";
import { cn, formatDate } from "@/lib/utils";
import { RadialScore } from "./RadialScore";
import { GapAnalysis } from "./GapAnalysis";
import { AtsResumeViewer } from "./AtsResumeViewer";
import type { AnalysisResponse } from "@/types/api";
import { hasGapAnalysis, hasAtsResume, SCORE_THRESHOLDS } from "@/types/api";

interface AnalysisDashboardProps {
  result: AnalysisResponse;
  onReset: () => void;
}

type Tab = "score" | "gap" | "resume";

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "score", label: "Score", icon: <BarChart2 size={15} /> },
  { id: "gap", label: "Gap Analysis", icon: <AlertCircle size={15} /> },
  { id: "resume", label: "ATS Resume", icon: <FileText size={15} /> },
];

export function AnalysisDashboard({ result, onReset }: AnalysisDashboardProps) {
  const [activeTab, setActiveTab] = useState<Tab>("score");

  const scoreAboveThreshold =
    result.score_breakdown.final >= SCORE_THRESHOLDS.excellent;

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Sparkles size={14} className="text-indigo-400" />
            <span className="text-xs font-semibold uppercase tracking-widest text-white/40">
              Analysis Complete
            </span>
          </div>
          <h2 className="text-lg font-bold text-white truncate max-w-[260px]">
            {result.filename}
          </h2>
          <div className="flex items-center gap-3 text-xs text-white/35">
            <span className="flex items-center gap-1">
              <Clock size={11} />
              {formatDate(result.created_at)}
            </span>
            <span className="flex items-center gap-1">
              <Hash size={11} />
              {result.id}
            </span>
          </div>
        </div>

        <button
          onClick={onReset}
          className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium text-white/50 hover:text-white hover:bg-white/10 transition-all border border-white/10"
        >
          <RotateCcw size={13} />
          New
        </button>
      </div>

      {/* ── Success banner for high scores ──────────────────────────────── */}
      {scoreAboveThreshold && (
        <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/20 px-4 py-3 flex items-center gap-3">
          <Sparkles size={16} className="text-emerald-400 flex-shrink-0" />
          <p className="text-sm text-emerald-300">
            <strong>Strong match!</strong> Your resume aligns well with this
            role. Review the ATS resume for final polish.
          </p>
        </div>
      )}

      {/* ── Tabs ────────────────────────────────────────────────────────── */}
      <div className="flex gap-1 bg-white/[0.04] rounded-xl p-1">
        {TABS.map((tab) => {
          const disabled = tab.id === "gap" && scoreAboveThreshold && !hasGapAnalysis(result);
          return (
            <button
              key={tab.id}
              onClick={() => !disabled && setActiveTab(tab.id)}
              disabled={disabled}
              className={cn(
                "flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg",
                "text-xs font-semibold tracking-wide transition-all duration-150",
                activeTab === tab.id
                  ? "bg-white/10 text-white shadow-sm"
                  : disabled
                  ? "text-white/20 cursor-not-allowed"
                  : "text-white/50 hover:text-white/80"
              )}
            >
              {tab.icon}
              {tab.label}
              {tab.id === "gap" && !hasGapAnalysis(result) && scoreAboveThreshold && (
                <span className="text-[10px] text-white/25">(N/A)</span>
              )}
            </button>
          );
        })}
      </div>

      {/* ── Tab content ─────────────────────────────────────────────────── */}
      <div>
        {activeTab === "score" && (
          <div className="flex flex-col items-center py-4">
            <RadialScore breakdown={result.score_breakdown} animate />
          </div>
        )}

        {activeTab === "gap" && (
          <>
            {hasGapAnalysis(result) ? (
              <GapAnalysis report={result.gap_analysis} />
            ) : (
              <div className="text-center py-12 space-y-2">
                <Sparkles size={32} className="text-emerald-400 mx-auto" />
                <p className="text-white/60 text-sm">
                  Your score is above 85% — no gap analysis needed!
                </p>
              </div>
            )}
          </>
        )}

        {activeTab === "resume" && (
          <>
            {hasAtsResume(result) ? (
              <AtsResumeViewer
                markdown={result.ats_resume}
                filename={result.filename}
              />
            ) : (
              <div className="text-center py-12 text-white/40 text-sm">
                ATS resume not available.
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
