"use client";

import { AlertTriangle, RefreshCcw } from "lucide-react";
import type { ErrorDetail } from "@/types/api";

const ERROR_SUGGESTIONS: Record<string, string> = {
  INVALID_FILE_TYPE: "Make sure you're uploading a .pdf file.",
  FILE_TOO_LARGE: "Try compressing the PDF or using a smaller file.",
  ENCRYPTED_PDF: "Remove the password protection from the PDF before uploading.",
  EMPTY_CONTENT: "The PDF may be scanned/image-only. Try a text-based PDF.",
  EMBEDDING_ERROR: "The AI service is temporarily busy. Please try again in a moment.",
  REASONING_ERROR: "Gap analysis failed. Your score and ATS resume may still be available.",
  NETWORK_ERROR: "Check your internet connection and try again.",
  TIMEOUT: "The server took too long. Try again — large PDFs may take up to 2 minutes.",
  RATE_LIMIT: "You've sent too many requests. Please wait a minute before trying again.",
  JD_TOO_SHORT: "Paste the full job description for best results.",
};

interface ErrorDisplayProps {
  error: ErrorDetail;
  onRetry?: () => void;
}

export function ErrorDisplay({ error, onRetry }: ErrorDisplayProps) {
  const suggestion = ERROR_SUGGESTIONS[error.code];

  return (
    <div className="rounded-2xl border border-red-500/20 bg-red-500/5 p-6 space-y-4">
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 rounded-xl bg-red-500/15 flex items-center justify-center flex-shrink-0">
          <AlertTriangle size={18} className="text-red-400" />
        </div>
        <div className="space-y-1 min-w-0">
          <p className="text-sm font-semibold text-white/90">{error.message}</p>
          {error.field && (
            <p className="text-xs text-red-400/70 font-mono">
              Field: {error.field}
            </p>
          )}
          {suggestion && (
            <p className="text-xs text-white/50 mt-2">{suggestion}</p>
          )}
        </div>
      </div>

      {onRetry && (
        <button
          onClick={onRetry}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border border-white/10 text-sm text-white/60 hover:text-white hover:bg-white/5 transition-all"
        >
          <RefreshCcw size={14} />
          Try again
        </button>
      )}
    </div>
  );
}
