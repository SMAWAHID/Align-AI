"use client";

import { useState } from "react";
import {
  BarChart2, FileText, AlertCircle, RotateCcw,
  Sparkles, Clock, Hash, Loader2, CheckCircle2,
} from "lucide-react";
import { cn, formatDate } from "@/lib/utils";
import { RadialScore } from "./RadialScore";
import { GapAnalysis } from "./GapAnalysis";
import { AtsResumeViewer } from "./AtsResumeViewer";
import type { AnalysisResponse } from "@/types/api";
import { hasGapAnalysis, hasAtsResume, SCORE_THRESHOLDS } from "@/types/api";
import { enhanceResume, AlignApiError } from "@/lib/api-client";

interface AnalysisDashboardProps {
  result: AnalysisResponse;
  onReset: () => void;
}

type Tab = "score" | "gap" | "resume";

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "score",  label: "Score",        icon: <BarChart2 size={15} /> },
  { id: "gap",    label: "Gap Analysis", icon: <AlertCircle size={15} /> },
  { id: "resume", label: "ATS Resume",   icon: <FileText size={15} /> },
];

export function AnalysisDashboard({ result, onReset }: AnalysisDashboardProps) {
  const [activeTab, setActiveTab]               = useState<Tab>("score");
  const [selectedSkills, setSelectedSkills]     = useState<string[]>([]);
  const [selectedImprovements, setSelectedImprovements] = useState<string[]>([]);
  const [enhancedResume, setEnhancedResume]     = useState<string | null>(null);
  const [enhancing, setEnhancing]               = useState(false);
  const [enhanceError, setEnhanceError]         = useState<string | null>(null);
  const [enhanceDone, setEnhanceDone]           = useState(false);

  const scoreAboveThreshold = result.score_breakdown.final >= SCORE_THRESHOLDS.excellent;
  const currentResume       = enhancedResume ?? result.ats_resume ?? "";
  const hasSelections       = selectedSkills.length > 0 || selectedImprovements.length > 0;

  const handleSelectionChange = (skills: string[], improvements: string[]) => {
    setSelectedSkills(skills);
    setSelectedImprovements(improvements);
  };

  const handleEnhance = async () => {
    if (!hasSelections || !result.ats_resume) return;
    setEnhancing(true);
    setEnhanceError(null);
    setEnhanceDone(false);
    try {
      const res = await enhanceResume({
        current_resume: currentResume,
        selected_skills: selectedSkills,
        selected_improvements: selectedImprovements,
        job_description: result.gap_analysis?.match_summary ?? "",
      });
      setEnhancedResume(res.enhanced_resume);
      setEnhanceDone(true);
      // Auto-switch to resume tab
      setTimeout(() => setActiveTab("resume"), 600);
    } catch (err) {
      setEnhanceError(err instanceof AlignApiError ? err.detail.message : "Enhancement failed. Please try again.");
    } finally {
      setEnhancing(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Sparkles size={14} className="text-indigo-400" />
            <span className="text-xs font-semibold uppercase tracking-widest text-white/40">Analysis Complete</span>
          </div>
          <h2 className="text-lg font-bold text-white truncate max-w-[260px]">{result.filename}</h2>
          <div className="flex items-center gap-3 text-xs text-white/35">
            <span className="flex items-center gap-1"><Clock size={11} />{formatDate(result.created_at)}</span>
            <span className="flex items-center gap-1"><Hash size={11} />{result.id}</span>
          </div>
        </div>
        <button onClick={onReset}
          className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium text-white/50 hover:text-white hover:bg-white/10 transition-all border border-white/10">
          <RotateCcw size={13} /> New
        </button>
      </div>

      {/* ── Score banner ───────────────────────────────────────────────── */}
      {scoreAboveThreshold && (
        <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/20 px-4 py-3 flex items-center gap-3">
          <Sparkles size={16} className="text-emerald-400 flex-shrink-0" />
          <p className="text-sm text-emerald-300">
            <strong>Strong match!</strong> Your resume aligns well with this role. Review the ATS resume for final polish.
          </p>
        </div>
      )}

      {/* ── Enhance action bar (shown when skills/improvements are selected) ── */}
      {hasGapAnalysis(result) && hasSelections && (
        <div className="rounded-xl border border-indigo-500/25 bg-indigo-500/8 px-4 py-3 flex items-center justify-between gap-4">
          <div className="text-sm text-white/70 space-y-0.5">
            <p className="font-medium text-white/90">
              {selectedSkills.length > 0 && `${selectedSkills.length} skill${selectedSkills.length > 1 ? "s" : ""}`}
              {selectedSkills.length > 0 && selectedImprovements.length > 0 && " + "}
              {selectedImprovements.length > 0 && `${selectedImprovements.length} improvement${selectedImprovements.length > 1 ? "s" : ""}`}
              {" "}selected
            </p>
            <p className="text-xs text-white/40">These will be woven into your ATS resume</p>
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            {enhanceDone && (
              <span className="flex items-center gap-1 text-xs text-emerald-400">
                <CheckCircle2 size={13} /> Enhanced!
              </span>
            )}
            {enhanceError && (
              <span className="text-xs text-red-400 max-w-[180px] text-right">{enhanceError}</span>
            )}
            <button
              onClick={handleEnhance}
              disabled={enhancing}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all",
                enhancing
                  ? "bg-white/10 text-white/40 cursor-not-allowed"
                  : "bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white shadow-lg shadow-indigo-500/25"
              )}
            >
              {enhancing
                ? <><Loader2 size={14} className="animate-spin" />Enhancing…</>
                : <><Sparkles size={14} />Enhance Resume</>}
            </button>
          </div>
        </div>
      )}

      {/* ── Tabs ────────────────────────────────────────────────────────── */}
      <div className="flex gap-1 bg-white/[0.04] rounded-xl p-1">
        {TABS.map(tab => {
          const isGapDisabled = tab.id === "gap" && !hasGapAnalysis(result);
          return (
            <button key={tab.id}
              onClick={() => !isGapDisabled && setActiveTab(tab.id)}
              disabled={isGapDisabled}
              className={cn(
                "flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg",
                "text-xs font-semibold tracking-wide transition-all duration-150",
                activeTab === tab.id ? "bg-white/10 text-white shadow-sm"
                  : isGapDisabled ? "text-white/20 cursor-not-allowed"
                  : "text-white/50 hover:text-white/80"
              )}
            >
              {tab.icon}{tab.label}
              {tab.id === "gap" && !hasGapAnalysis(result) && scoreAboveThreshold && (
                <span className="text-[10px] text-white/25 ml-0.5">(N/A)</span>
              )}
              {tab.id === "resume" && enhancedResume && (
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 ml-0.5" />
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
          hasGapAnalysis(result) ? (
            <GapAnalysis
              report={result.gap_analysis}
              selectedSkills={selectedSkills}
              selectedImprovements={selectedImprovements}
              onSelectionChange={handleSelectionChange}
            />
          ) : (
            <div className="text-center py-12 space-y-2">
              <Sparkles size={32} className="text-emerald-400 mx-auto" />
              <p className="text-white/60 text-sm">Your score is above 85% — no gap analysis needed!</p>
            </div>
          )
        )}

        {activeTab === "resume" && (
          hasAtsResume(result) ? (
            <AtsResumeViewer
              markdown={currentResume}
              filename={result.filename}
              enhanceAvailable={hasGapAnalysis(result) && !enhancedResume}
              onEnhanceClick={() => setActiveTab("gap")}
            />
          ) : (
            <div className="text-center py-12 text-white/40 text-sm">ATS resume not available.</div>
          )
        )}
      </div>
    </div>
  );
}
