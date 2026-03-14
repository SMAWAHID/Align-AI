"use client";

import { useState } from "react";
import { Download, Copy, Check, FileDown, Eye } from "lucide-react";
import { cn } from "@/lib/utils";
import { downloadText } from "@/lib/utils";

interface AtsResumeViewerProps {
  markdown: string;
  filename: string;
}

export function AtsResumeViewer({ markdown, filename }: AtsResumeViewerProps) {
  const [copied, setCopied] = useState(false);
  const [view, setView] = useState<"preview" | "raw">("preview");

  const handleCopy = async () => {
    await navigator.clipboard.writeText(markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadMd = () => {
    const baseName = filename.replace(/\.pdf$/i, "");
    downloadText(markdown, `${baseName}_ATS_Resume.md`, "text/markdown");
  };

  const handleDownloadTxt = () => {
    const baseName = filename.replace(/\.pdf$/i, "");
    downloadText(markdown, `${baseName}_ATS_Resume.txt`, "text/plain");
  };

  /** Simple Markdown → HTML renderer (headings, bold, bullets, hr) */
  const renderMarkdown = (md: string): string => {
    return md
      .replace(/^# (.+)$/gm, '<h1 class="text-xl font-bold text-white mt-0 mb-1">$1</h1>')
      .replace(/^## (.+)$/gm, '<h2 class="text-base font-semibold text-indigo-300 mt-5 mb-2 border-b border-white/10 pb-1">$2</h2>'.replace('$2','$1'))
      .replace(/^### (.+)$/gm, '<h3 class="text-sm font-semibold text-white/80 mt-4 mb-1">$1</h3>')
      .replace(/\*\*(.+?)\*\*/g, '<strong class="text-white/90">$1</strong>')
      .replace(/^- (.+)$/gm, '<li class="ml-4 text-white/70 list-disc marker:text-indigo-400">$1</li>')
      .replace(/^---$/gm, '<hr class="border-white/10 my-4" />')
      .replace(/\n{2,}/g, '</p><p class="text-white/60 text-sm leading-relaxed mt-2">')
      .replace(/^(?!<[hlip])(.+)$/gm, '<p class="text-white/60 text-sm leading-relaxed">$1</p>');
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-widest text-white/40">
          ATS-Optimised Resume
        </h3>

        {/* View toggle */}
        <div className="flex items-center bg-white/5 rounded-lg p-0.5 gap-0.5">
          {(["preview", "raw"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={cn(
                "px-3 py-1 rounded-md text-xs font-medium transition-all",
                view === v
                  ? "bg-white/10 text-white"
                  : "text-white/40 hover:text-white/60"
              )}
            >
              {v === "preview" ? <Eye size={12} className="inline mr-1" /> : null}
              {v.charAt(0).toUpperCase() + v.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="relative rounded-xl border border-white/10 bg-white/[0.02] overflow-hidden">
        {/* Action bar */}
        <div className="flex items-center justify-end gap-2 px-4 py-2.5 border-b border-white/8 bg-white/[0.02]">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white/60 hover:text-white hover:bg-white/10 transition-all"
          >
            {copied ? (
              <Check size={13} className="text-emerald-400" />
            ) : (
              <Copy size={13} />
            )}
            {copied ? "Copied!" : "Copy"}
          </button>
          <button
            onClick={handleDownloadMd}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white/60 hover:text-white hover:bg-white/10 transition-all"
          >
            <Download size={13} />
            .md
          </button>
          <button
            onClick={handleDownloadTxt}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-600/80 hover:bg-indigo-500/80 text-white transition-all"
          >
            <FileDown size={13} />
            .txt
          </button>
        </div>

        {/* Document */}
        <div className="max-h-[500px] overflow-y-auto p-6 custom-scrollbar">
          {view === "preview" ? (
            <div
              className="prose-sm max-w-none text-sm"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(markdown) }}
            />
          ) : (
            <pre className="text-xs text-white/60 font-mono leading-relaxed whitespace-pre-wrap break-words">
              {markdown}
            </pre>
          )}
        </div>
      </div>

      <p className="text-xs text-white/30 text-center">
        Copy the Markdown and paste into{" "}
        <a
          href="https://resume.io"
          target="_blank"
          rel="noopener noreferrer"
          className="text-indigo-400 hover:underline"
        >
          resume.io
        </a>{" "}
        or any Markdown-to-PDF tool for a polished final document.
      </p>
    </div>
  );
}
