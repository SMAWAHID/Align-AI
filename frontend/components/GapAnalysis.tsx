"use client";

import { useState } from "react";
import { ChevronDown, AlertTriangle, Lightbulb, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import type { GapAnalysisReport } from "@/types/api";

interface GapAnalysisProps {
  report: GapAnalysisReport;
}

interface AccordionItemProps {
  title: string;
  icon: React.ReactNode;
  accentColor: string;
  items?: readonly string[];
  text?: string;
  defaultOpen?: boolean;
}

function AccordionItem({
  title,
  icon,
  accentColor,
  items,
  text,
  defaultOpen = false,
}: AccordionItemProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div
      className="rounded-xl overflow-hidden border border-white/10 bg-white/[0.03] backdrop-blur-sm"
      style={{ borderLeft: `3px solid ${accentColor}` }}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-white/[0.04] transition-colors"
        aria-expanded={open}
      >
        <div className="flex items-center gap-3">
          <span style={{ color: accentColor }}>{icon}</span>
          <span className="font-semibold text-white/90 text-sm tracking-wide">
            {title}
          </span>
          {items && (
            <span
              className="px-2 py-0.5 rounded-full text-xs font-mono"
              style={{ background: `${accentColor}22`, color: accentColor }}
            >
              {items.length}
            </span>
          )}
        </div>
        <ChevronDown
          size={16}
          className={cn(
            "text-white/40 transition-transform duration-200",
            open && "rotate-180"
          )}
        />
      </button>

      <div
        className={cn(
          "overflow-hidden transition-all duration-300 ease-in-out",
          open ? "max-h-[800px] opacity-100" : "max-h-0 opacity-0"
        )}
      >
        <div className="px-5 pb-5 pt-1">
          {text && (
            <p className="text-white/70 text-sm leading-relaxed">{text}</p>
          )}
          {items && items.length > 0 && (
            <ul className="space-y-2">
              {items.map((item, i) => (
                <li key={i} className="flex items-start gap-3 text-sm">
                  <span
                    className="mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0"
                    style={{ background: accentColor }}
                  />
                  <span className="text-white/75 leading-relaxed">{item}</span>
                </li>
              ))}
            </ul>
          )}
          {items && items.length === 0 && (
            <p className="text-white/40 text-sm italic">None identified.</p>
          )}
        </div>
      </div>
    </div>
  );
}

export function GapAnalysis({ report }: GapAnalysisProps) {
  return (
    <div className="space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-widest text-white/40 mb-4">
        Gap Analysis
      </h3>

      <AccordionItem
        title="Match Summary"
        icon={<FileText size={16} />}
        accentColor="#3b82f6"
        text={report.match_summary || "No summary available."}
        defaultOpen={true}
      />

      <AccordionItem
        title="Missing Skills"
        icon={<AlertTriangle size={16} />}
        accentColor="#f59e0b"
        items={report.missing_skills}
        defaultOpen={true}
      />

      <AccordionItem
        title="Improvements"
        icon={<Lightbulb size={16} />}
        accentColor="#10b981"
        items={report.improvements}
        defaultOpen={false}
      />
    </div>
  );
}
