"use client";

import { useState } from "react";
import { Download, Copy, Check, Eye, Code, ChevronDown, Loader2 } from "lucide-react";
import { cn, downloadText } from "@/lib/utils";
import { downloadResume, AlignApiError } from "@/lib/api-client";
import type { DownloadFormat } from "@/types/api";

interface AtsResumeViewerProps {
  markdown: string;
  filename: string;
  /** If provided, shows an "Enhance Resume" call-to-action */
  onEnhanceClick?: () => void;
  enhanceAvailable?: boolean;
}

const FORMATS: { value: DownloadFormat; label: string; desc: string }[] = [
  { value: "pdf",  label: "PDF",      desc: "Best for sending to employers" },
  { value: "docx", label: "Word",     desc: "Editable in Microsoft Word" },
  { value: "md",   label: "Markdown", desc: "For Markdown editors" },
  { value: "txt",  label: "Plain Text", desc: "Universal compatibility" },
];

export function AtsResumeViewer({ markdown, filename, onEnhanceClick, enhanceAvailable }: AtsResumeViewerProps) {
  const [copied, setCopied]           = useState(false);
  const [view, setView]               = useState<"preview" | "raw">("preview");
  const [format, setFormat]           = useState<DownloadFormat>("pdf");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [dlError, setDlError]         = useState<string | null>(null);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = async () => {
    setDlError(null);

    // txt and md can be done client-side instantly
    if (format === "txt") {
      downloadText(_mdToTxt(markdown), `${_baseName(filename)}_ATS_Resume.txt`, "text/plain");
      return;
    }
    if (format === "md") {
      downloadText(markdown, `${_baseName(filename)}_ATS_Resume.md`, "text/markdown");
      return;
    }

    // pdf and docx need the backend converter
    setDownloading(true);
    try {
      await downloadResume({ content: markdown, format, filename: `${_baseName(filename)}_ATS_Resume` });
    } catch (err) {
      setDlError(err instanceof AlignApiError ? err.detail.message : "Download failed. Please try again.");
    } finally {
      setDownloading(false);
    }
  };

  const selectedFmt = FORMATS.find(f => f.value === format)!;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-widest text-white/40">
          ATS-Optimised Resume
        </h3>
        <div className="flex items-center bg-white/5 rounded-lg p-0.5 gap-0.5">
          {(["preview", "raw"] as const).map(v => (
            <button key={v} onClick={() => setView(v)}
              className={cn("px-3 py-1 rounded-md text-xs font-medium transition-all",
                view === v ? "bg-white/10 text-white" : "text-white/40 hover:text-white/60")}>
              {v === "preview" ? <><Eye size={11} className="inline mr-1" />Preview</> : <><Code size={11} className="inline mr-1" />Raw</>}
            </button>
          ))}
        </div>
      </div>

      {/* Enhance CTA */}
      {enhanceAvailable && onEnhanceClick && (
        <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 px-4 py-3 flex items-center justify-between gap-4">
          <p className="text-sm text-indigo-300">
            <strong className="text-white">Enhance this resume</strong> — select missing skills and improvements from the Gap Analysis tab to incorporate them.
          </p>
          <button
            onClick={onEnhanceClick}
            className="flex-shrink-0 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-colors"
          >
            Enhance ✦
          </button>
        </div>
      )}

      {/* Content */}
      <div className="relative rounded-xl border border-white/10 bg-white/[0.02] overflow-hidden">
        {/* Toolbar */}
        <div className="flex items-center justify-between gap-2 px-4 py-2.5 border-b border-white/8 bg-white/[0.02]">
          <button onClick={handleCopy}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white/60 hover:text-white hover:bg-white/10 transition-all">
            {copied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
            {copied ? "Copied!" : "Copy"}
          </button>

          <div className="flex items-center gap-2">
            {/* Format dropdown */}
            <div className="relative">
              <button
                onClick={() => setDropdownOpen(o => !o)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-white/8 hover:bg-white/12 text-white/80 transition-all border border-white/10"
              >
                <span>{selectedFmt.label}</span>
                <ChevronDown size={12} className={cn("transition-transform", dropdownOpen && "rotate-180")} />
              </button>

              {dropdownOpen && (
                <div className="absolute right-0 top-full mt-1 w-52 rounded-xl border border-white/10 bg-[#0f1117] shadow-xl z-50 overflow-hidden">
                  {FORMATS.map(f => (
                    <button
                      key={f.value}
                      onClick={() => { setFormat(f.value); setDropdownOpen(false); }}
                      className={cn(
                        "w-full flex items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-white/5",
                        format === f.value && "bg-indigo-500/10"
                      )}
                    >
                      <div>
                        <p className={cn("text-xs font-semibold", format === f.value ? "text-indigo-400" : "text-white/80")}>{f.label}</p>
                        <p className="text-[11px] text-white/35 mt-0.5">{f.desc}</p>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Download button */}
            <button
              onClick={handleDownload}
              disabled={downloading}
              className={cn(
                "flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold transition-all",
                downloading
                  ? "bg-white/10 text-white/40 cursor-not-allowed"
                  : "bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20"
              )}
            >
              {downloading
                ? <><Loader2 size={13} className="animate-spin" /> Generating…</>
                : <><Download size={13} /> Download {selectedFmt.label}</>}
            </button>
          </div>
        </div>

        {dlError && (
          <div className="px-4 py-2 bg-red-500/10 border-b border-red-500/20 text-xs text-red-400">{dlError}</div>
        )}

        {/* Document */}
        <div className="max-h-[500px] overflow-y-auto p-6 custom-scrollbar">
          {view === "preview" ? (
            <div className="prose-sm max-w-none text-sm"
              dangerouslySetInnerHTML={{ __html: _renderMarkdown(markdown) }} />
          ) : (
            <pre className="text-xs text-white/60 font-mono leading-relaxed whitespace-pre-wrap break-words">{markdown}</pre>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function _baseName(filename: string) {
  return filename.replace(/\.pdf$/i, "");
}

function _mdToTxt(md: string): string {
  return md
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/\*(.+?)\*/g, "$1")
    .replace(/^[-*+]\s+/gm, "• ")
    .replace(/\[(.+?)\]\(.+?\)/g, "$1")
    .replace(/^---+$/gm, "─".repeat(50))
    .trim();
}

function _renderMarkdown(md: string): string {
  return md
    .replace(/^# (.+)$/gm, '<h1 class="text-xl font-bold text-white mt-0 mb-1">$1</h1>')
    .replace(/^## (.+)$/gm, '<h2 class="text-base font-semibold text-indigo-300 mt-5 mb-2 border-b border-white/10 pb-1">$1</h2>')
    .replace(/^### (.+)$/gm, '<h3 class="text-sm font-semibold text-white/80 mt-4 mb-1">$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-white/90">$1</strong>')
    .replace(/^- (.+)$/gm, '<li class="ml-4 text-white/70 list-disc marker:text-indigo-400 text-sm leading-relaxed">$1</li>')
    .replace(/^---$/gm, '<hr class="border-white/10 my-4" />')
    .replace(/\n{2,}/g, '</p><p class="text-white/60 text-sm leading-relaxed mt-2">')
    .replace(/^(?!<[hlip])(.+)$/gm, '<p class="text-white/60 text-sm leading-relaxed">$1</p>');
}
