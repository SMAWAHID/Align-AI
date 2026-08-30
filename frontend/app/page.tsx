"use client";

import { Cpu, Github, Zap } from "lucide-react";
import { useAnalysis } from "@/hooks/useAnalysis";
import { UploadForm } from "@/components/UploadForm";
import { AnalysisDashboard } from "@/components/AnalysisDashboard";
import { LoadingStepper } from "@/components/LoadingStepper";
import { ErrorDisplay } from "@/components/ErrorDisplay";
import { ServerStatusPill, ServerWakingBanner } from "@/components/ServerStatus";
import { useServerWakeup } from "@/hooks/useServerWakeup";

export default function HomePage() {
  const { state, submit, reset, isLoading } = useAnalysis();
  // Starts waking the free-tier API while the visitor reads the hero copy.
  const serverState = useServerWakeup();

  return (
    <div className="min-h-dvh flex flex-col">
      {/* ── Nav ─────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-white/[0.06] backdrop-blur-xl bg-[#08090e]/80">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
              <Cpu size={14} className="text-white" />
            </div>
            <span
              className="font-bold text-white tracking-tight"
              style={{ fontFamily: "'Syne', sans-serif", fontSize: "1.05rem" }}
            >
              AlignAI
            </span>
          </div>
          <div className="flex items-center gap-4">
            <ServerStatusPill state={serverState} />
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-white/30 hover:text-white/60 transition-colors"
              aria-label="GitHub"
            >
              <Github size={17} />
            </a>
          </div>
        </div>
      </header>

      <div className="pt-4">
        <ServerWakingBanner state={serverState} />
      </div>

      {/* ── Hero ────────────────────────────────────────────────────────── */}
      <section className="pt-16 pb-10 px-6 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-medium mb-6">
          <Zap size={12} />
          Real-time WebSocket Pipeline · Semantic + Keyword Hybrid Scoring
        </div>
        <h1
          className="text-4xl sm:text-5xl font-extrabold text-white mb-4 leading-tight"
          style={{ fontFamily: "'Syne', sans-serif" }}
        >
          Match your resume to
          <br />
          <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-cyan-400 bg-clip-text text-transparent">
            any job description
          </span>
        </h1>
        <p className="max-w-xl mx-auto text-white/50 text-base leading-relaxed">
          Upload your resume (PDF, DOCX, or TXT) and paste a job description.
          Watch the pipeline run in real-time via WebSocket — score, gap analysis,
          resource links, and an ATS-optimised resume ready to download.
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
          {[
            "WebSocket Live Progress",
            "PDF · DOCX · TXT Input",
            "Hybrid Scoring",
            "Skill Resource Links",
            "ATS Resume Builder",
            "PDF/Word/MD/TXT Output",
          ].map((f) => (
            <span
              key={f}
              className="px-3 py-1 rounded-full text-xs text-white/50 bg-white/[0.04] border border-white/[0.07]"
            >
              {f}
            </span>
          ))}
        </div>
      </section>

      {/* ── Main grid ───────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-6 pb-20">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          {/* Left — always shows form */}
          <div
            className="glass rounded-2xl p-6 sm:p-8"
            style={{ boxShadow: "0 0 60px rgba(99,102,241,0.04)" }}
          >
            <div className="mb-6">
              <h2
                className="text-lg font-bold text-white"
                style={{ fontFamily: "'Syne', sans-serif" }}
              >
                Upload & Analyse
              </h2>
              <p className="text-xs text-white/40 mt-1">
                In-memory processing · Real-time WebSocket updates
              </p>
            </div>
            <UploadForm
              onSubmit={submit}
              isLoading={isLoading}
              disabled={isLoading}
            />
          </div>

          {/* Right — result / stepper / error / placeholder */}
          <div
            className="glass rounded-2xl p-6 sm:p-8 min-h-[480px] flex flex-col"
            style={{ boxShadow: "0 0 60px rgba(139,92,246,0.04)" }}
          >
            {state.status === "idle" && <PlaceholderPanel />}

            {isLoading && (
              <LoadingStepper
                status={state.status}
                uploadProgress={state.uploadProgress}
                serverMessage={state.serverMessage}
                scorePreview={state.scorePreview}
              />
            )}

            {state.status === "error" && state.error && (
              <div className="flex-1 flex items-center justify-center">
                <div className="w-full max-w-sm">
                  <ErrorDisplay error={state.error} onRetry={reset} />
                </div>
              </div>
            )}

            {state.status === "success" && state.result && (
              <AnalysisDashboard
                result={state.result}
                jobDescription={state.jobDescription}
                onReset={reset}
              />
            )}
          </div>
        </div>

        {/* Pipeline steps */}
        <section className="mt-16">
          <h2
            className="text-center text-lg font-bold text-white/80 mb-8"
            style={{ fontFamily: "'Syne', sans-serif" }}
          >
            How it works
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
            {PIPELINE_STEPS.map((step, i) => (
              <div key={i} className="glass rounded-xl p-3 text-center space-y-2">
                <div
                  className="w-7 h-7 rounded-lg mx-auto flex items-center justify-center text-xs font-bold"
                  style={{ background: `${step.color}20`, color: step.color }}
                >
                  {i + 1}
                </div>
                <p className="text-xs font-semibold text-white/70 leading-tight">{step.title}</p>
                <p className="text-[10px] text-white/30 leading-tight">{step.desc}</p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t border-white/[0.05] py-6 text-center text-xs text-white/25">
        AlignAI · Next.js 15 + FastAPI + WebSocket · Jina + Groq (free) / Gemini (paid)
      </footer>
    </div>
  );
}

function PlaceholderPanel() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center text-center space-y-5 py-8">
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500/20 to-violet-500/20 flex items-center justify-center border border-white/10">
        <Cpu size={28} className="text-indigo-400/70" />
      </div>
      <div className="space-y-2 max-w-xs">
        <h3
          className="text-base font-bold text-white/60"
          style={{ fontFamily: "'Syne', sans-serif" }}
        >
          Results appear here
        </h3>
        <p className="text-xs text-white/30 leading-relaxed">
          Upload your resume and paste a job description, then click{" "}
          <strong className="text-white/45">Analyse Resume</strong>.
          Live step-by-step progress will appear here via WebSocket.
        </p>
      </div>
      <svg viewBox="0 0 160 160" width={160} height={160} className="opacity-10">
        <circle cx="80" cy="80" r="60" fill="none" stroke="white" strokeWidth="10" strokeDasharray="6 4" />
        <circle cx="80" cy="80" r="40" fill="none" stroke="white" strokeWidth="8" strokeDasharray="4 4" />
        <text x="80" y="85" textAnchor="middle" fill="white" fontSize="24" fontFamily="monospace">—</text>
      </svg>
    </div>
  );
}

const PIPELINE_STEPS = [
  { title: "Upload",        desc: "PDF / DOCX / TXT",         color: "#6366f1" },
  { title: "Extract",       desc: "PyMuPDF / docx / text",    color: "#8b5cf6" },
  { title: "Embed",         desc: "Jina / Gemini vectors",    color: "#06b6d4" },
  { title: "Score",         desc: "Cosine + keyword",         color: "#3b82f6" },
  { title: "Gap Analysis",  desc: "Groq / Gemini LLM",        color: "#f59e0b" },
  { title: "ATS Resume",    desc: "AI rewrite + enhance",     color: "#10b981" },
  { title: "Download",      desc: "PDF / Word / MD / TXT",    color: "#ef4444" },
];
