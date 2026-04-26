"use client";

import { useCallback, useRef, useState } from "react";
import { Upload, FileText, X, Briefcase, FileType } from "lucide-react";
import { cn } from "@/lib/utils";
import { validateResumeFile } from "@/lib/api-client";
import type { ErrorDetail } from "@/types/api";

interface UploadFormProps {
  onSubmit: (file: File, jd: string) => void;
  isLoading: boolean;
  disabled?: boolean;
}

const ACCEPTED_TYPES = {
  "application/pdf": ".pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
  "text/plain": ".txt",
};

const ACCEPT_ATTR = ".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain";

const FILE_TYPE_ICONS: Record<string, React.ReactNode> = {
  pdf:  <FileText size={22} className="text-red-400" />,
  docx: <FileText size={22} className="text-blue-400" />,
  txt:  <FileType size={22} className="text-emerald-400" />,
};

function getFileExt(file: File): string {
  return file.name.split(".").pop()?.toLowerCase() ?? "";
}

function getFileIconColor(file: File): string {
  const ext = getFileExt(file);
  if (ext === "pdf")  return "bg-red-500/20";
  if (ext === "docx") return "bg-blue-500/20";
  return "bg-emerald-500/20";
}

export function UploadForm({ onSubmit, isLoading, disabled }: UploadFormProps) {
  const [file, setFile]           = useState<File | null>(null);
  const [jd, setJd]               = useState("");
  const [dragOver, setDragOver]   = useState(false);
  const [fileError, setFileError] = useState<ErrorDetail | null>(null);
  const inputRef                  = useRef<HTMLInputElement>(null);

  const handleFile = useCallback((f: File) => {
    // Accept PDF, DOCX, TXT — validate size only (type check happens server side too)
    const ext = f.name.split(".").pop()?.toLowerCase();
    if (!["pdf", "docx", "txt"].includes(ext ?? "")) {
      setFileError({ code: "INVALID_TYPE", message: "Only PDF, DOCX, and TXT files are supported.", field: "resume" });
      return;
    }
    const maxMb = Number(process.env.NEXT_PUBLIC_MAX_FILE_SIZE_MB ?? 10);
    if (f.size > maxMb * 1024 * 1024) {
      setFileError({ code: "FILE_TOO_LARGE", message: `File must be smaller than ${maxMb} MB.`, field: "resume" });
      return;
    }
    if (f.size < 512) {
      setFileError({ code: "FILE_TOO_SMALL", message: "File appears to be empty.", field: "resume" });
      return;
    }
    setFileError(null);
    setFile(f);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFile(dropped);
  }, [handleFile]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (file && jd.trim().length >= 50) onSubmit(file, jd);
  };

  const canSubmit = !!file && jd.trim().length >= 50 && !isLoading && !disabled;
  const ext       = file ? getFileExt(file) : "";

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* ── Drop Zone ─────────────────────────────────────────────────── */}
      <div>
        <label className="block text-xs font-semibold uppercase tracking-widest text-white/40 mb-3">
          Resume
        </label>

        {/* Format badges */}
        <div className="flex gap-1.5 mb-3">
          {["PDF", "DOCX", "TXT"].map((fmt) => (
            <span
              key={fmt}
              className={cn(
                "px-2 py-0.5 rounded-md text-[10px] font-semibold tracking-wide border transition-all",
                file && getFileExt(file).toUpperCase() === fmt
                  ? "bg-indigo-500/20 border-indigo-500/40 text-indigo-300"
                  : "bg-white/[0.04] border-white/10 text-white/35"
              )}
            >
              {fmt}
            </span>
          ))}
        </div>

        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={cn(
            "relative cursor-pointer rounded-2xl border-2 border-dashed p-8",
            "flex flex-col items-center justify-center gap-3 text-center",
            "transition-all duration-200",
            dragOver
              ? "border-indigo-400 bg-indigo-500/10"
              : file
              ? "border-emerald-500/50 bg-emerald-500/5"
              : "border-white/15 bg-white/[0.02] hover:border-white/30 hover:bg-white/[0.04]"
          )}
          role="button"
          tabIndex={0}
          aria-label="Upload resume file"
          onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT_ATTR}
            className="sr-only"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
          />

          {file ? (
            <>
              <div className={cn("w-12 h-12 rounded-2xl flex items-center justify-center", getFileIconColor(file))}>
                {FILE_TYPE_ICONS[ext] ?? <FileText size={22} className="text-white/60" />}
              </div>
              <div>
                <p className="text-sm font-semibold text-white/90">{file.name}</p>
                <p className="text-xs text-white/40 mt-0.5">{(file.size / 1024).toFixed(0)} KB · {ext.toUpperCase()}</p>
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                  setFileError(null);
                  if (inputRef.current) inputRef.current.value = "";
                }}
                className="absolute top-3 right-3 w-7 h-7 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors"
                aria-label="Remove file"
              >
                <X size={13} className="text-white/60" />
              </button>
            </>
          ) : (
            <>
              <div className="w-12 h-12 rounded-2xl bg-white/5 flex items-center justify-center">
                <Upload size={22} className="text-white/40" />
              </div>
              <div>
                <p className="text-sm font-medium text-white/70">
                  Drop your resume here, or{" "}
                  <span className="text-indigo-400 underline underline-offset-2">browse</span>
                </p>
                <p className="text-xs text-white/35 mt-1">PDF, DOCX, or TXT · Max 10 MB</p>
              </div>
            </>
          )}
        </div>

        {fileError && (
          <p className="mt-2 text-xs text-red-400 flex items-center gap-1.5">
            <X size={12} /> {fileError.message}
          </p>
        )}
      </div>

      {/* ── Job Description ────────────────────────────────────────────── */}
      <div>
        <label htmlFor="jd-input" className="block text-xs font-semibold uppercase tracking-widest text-white/40 mb-3">
          Job Description
        </label>
        <div className="relative">
          <Briefcase size={15} className="absolute top-3.5 left-4 text-white/30 pointer-events-none" />
          <textarea
            id="jd-input"
            value={jd}
            onChange={(e) => setJd(e.target.value)}
            placeholder="Paste the full job description here…"
            rows={8}
            maxLength={20000}
            className={cn(
              "w-full pl-10 pr-4 py-3 rounded-xl resize-none",
              "bg-white/[0.04] border border-white/10",
              "text-sm text-white/80 placeholder:text-white/25",
              "focus:outline-none focus:ring-1 focus:ring-indigo-500/60 focus:border-indigo-500/40",
              "transition-colors duration-150 leading-relaxed"
            )}
          />
          <span className="absolute bottom-3 right-4 text-xs text-white/25 font-mono">
            {jd.length}/20000
          </span>
        </div>
        {jd.length > 0 && jd.trim().length < 50 && (
          <p className="mt-1.5 text-xs text-amber-400">
            At least 50 characters required ({50 - jd.trim().length} more)
          </p>
        )}
      </div>

      {/* ── Submit ─────────────────────────────────────────────────────── */}
      <button
        type="submit"
        disabled={!canSubmit}
        className={cn(
          "w-full py-3.5 rounded-xl font-semibold text-sm tracking-wide transition-all duration-200",
          canSubmit
            ? [
                "bg-gradient-to-r from-indigo-600 to-violet-600",
                "hover:from-indigo-500 hover:to-violet-500",
                "shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40 text-white cursor-pointer",
              ]
            : "bg-white/10 text-white/30 cursor-not-allowed"
        )}
      >
        {isLoading ? "Analysing…" : "Analyse Resume"}
      </button>
    </form>
  );
}
