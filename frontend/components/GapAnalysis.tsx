"use client";

import { useState } from "react";
import {
  ChevronDown, AlertTriangle, Lightbulb, FileText,
  ExternalLink, BookOpen, Youtube, GraduationCap, Code2, CheckSquare, Square,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { GapAnalysisReport, SkillResource } from "@/types/api";

interface GapAnalysisProps {
  report: GapAnalysisReport;
  /** Called when user changes skill/improvement selection */
  onSelectionChange?: (skills: string[], improvements: string[]) => void;
  selectedSkills?: string[];
  selectedImprovements?: string[];
}

// ─── Resource type icons ──────────────────────────────────────────────────────

const RESOURCE_ICONS: Record<string, React.ReactNode> = {
  docs:     <Code2 size={12} />,
  course:   <GraduationCap size={12} />,
  video:    <Youtube size={12} />,
  tutorial: <BookOpen size={12} />,
  other:    <ExternalLink size={12} />,
};

const RESOURCE_COLORS: Record<string, string> = {
  docs: "#6366f1", course: "#10b981", video: "#ef4444", tutorial: "#f59e0b", other: "#94a3b8",
};

function ResourceLink({ resource }: { resource: SkillResource }) {
  const color = RESOURCE_COLORS[resource.type] ?? RESOURCE_COLORS.other;
  const icon  = RESOURCE_ICONS[resource.type] ?? RESOURCE_ICONS.other;
  return (
    <a
      href={resource.url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all hover:scale-105"
      style={{ background: `${color}18`, color, border: `1px solid ${color}30` }}
    >
      {icon}
      {resource.title}
      <ExternalLink size={10} className="ml-0.5 opacity-60" />
    </a>
  );
}

// ─── Accordion item ───────────────────────────────────────────────────────────

function AccordionItem({
  title, icon, accentColor, children, defaultOpen = false, badge,
}: {
  title: string; icon: React.ReactNode; accentColor: string;
  children: React.ReactNode; defaultOpen?: boolean; badge?: number;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-xl overflow-hidden border border-white/10 bg-white/[0.03]" style={{ borderLeft: `3px solid ${accentColor}` }}>
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-white/[0.04] transition-colors"
        aria-expanded={open}
      >
        <div className="flex items-center gap-3">
          <span style={{ color: accentColor }}>{icon}</span>
          <span className="font-semibold text-white/90 text-sm tracking-wide">{title}</span>
          {badge !== undefined && (
            <span className="px-2 py-0.5 rounded-full text-xs font-mono" style={{ background: `${accentColor}22`, color: accentColor }}>
              {badge}
            </span>
          )}
        </div>
        <ChevronDown size={16} className={cn("text-white/40 transition-transform duration-200", open && "rotate-180")} />
      </button>
      <div className={cn("overflow-hidden transition-all duration-300", open ? "max-h-[1200px] opacity-100" : "max-h-0 opacity-0")}>
        <div className="px-5 pb-5 pt-1">{children}</div>
      </div>
    </div>
  );
}

// ─── Selectable item (skill or improvement) ───────────────────────────────────

function SelectableItem({
  text, selected, onToggle, color,
}: { text: string; selected: boolean; onToggle: () => void; color: string }) {
  return (
    <div
      onClick={onToggle}
      className={cn(
        "flex items-start gap-3 p-3 rounded-xl cursor-pointer transition-all duration-150",
        selected ? "bg-white/[0.07] border border-white/15" : "hover:bg-white/[0.04] border border-transparent"
      )}
    >
      <div className="flex-shrink-0 mt-0.5" style={{ color: selected ? color : "rgba(255,255,255,0.3)" }}>
        {selected ? <CheckSquare size={16} /> : <Square size={16} />}
      </div>
      <span className={cn("text-sm leading-relaxed", selected ? "text-white/90" : "text-white/65")}>{text}</span>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function GapAnalysis({
  report,
  onSelectionChange,
  selectedSkills = [],
  selectedImprovements = [],
}: GapAnalysisProps) {

  const toggleSkill = (skill: string) => {
    const next = selectedSkills.includes(skill)
      ? selectedSkills.filter(s => s !== skill)
      : [...selectedSkills, skill];
    onSelectionChange?.(next, selectedImprovements);
  };

  const toggleImprovement = (imp: string) => {
    const next = selectedImprovements.includes(imp)
      ? selectedImprovements.filter(i => i !== imp)
      : [...selectedImprovements, imp];
    onSelectionChange?.(selectedSkills, next);
  };

  const selectAllSkills = () => onSelectionChange?.(
    selectedSkills.length === report.missing_skills.length ? [] : [...report.missing_skills],
    selectedImprovements
  );

  const selectAllImprovements = () => onSelectionChange?.(
    selectedSkills,
    selectedImprovements.length === report.improvements.length ? [] : [...report.improvements]
  );

  const hasResources = report.skill_resources && report.skill_resources.length > 0;
  const resourcesMap = new Map(report.skill_resources?.map(s => [s.skill, s.resources]) ?? []);

  return (
    <div className="space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-widest text-white/40 mb-4">Gap Analysis</h3>

      {/* Match Summary */}
      <AccordionItem title="Match Summary" icon={<FileText size={16} />} accentColor="#3b82f6" defaultOpen>
        <p className="text-white/70 text-sm leading-relaxed">
          {report.match_summary || "No summary available."}
        </p>
      </AccordionItem>

      {/* Missing Skills */}
      <AccordionItem
        title="Missing Skills"
        icon={<AlertTriangle size={16} />}
        accentColor="#f59e0b"
        badge={report.missing_skills.length}
        defaultOpen
      >
        {report.missing_skills.length > 0 ? (
          <div className="space-y-1">
            {/* Select all toggle */}
            {onSelectionChange && (
              <div className="flex justify-between items-center mb-3">
                <span className="text-xs text-white/40">Select skills to add to your resume</span>
                <button
                  onClick={selectAllSkills}
                  className="text-xs text-amber-400 hover:text-amber-300 transition-colors"
                >
                  {selectedSkills.length === report.missing_skills.length ? "Deselect all" : "Select all"}
                </button>
              </div>
            )}

            {report.missing_skills.map((skill, i) => (
              <div key={i} className="space-y-2">
                <SelectableItem
                  text={skill}
                  selected={selectedSkills.includes(skill)}
                  onToggle={() => toggleSkill(skill)}
                  color="#f59e0b"
                />
                {/* Resource links for this skill */}
                {hasResources && resourcesMap.has(skill) && (
                  <div className="ml-8 flex flex-wrap gap-1.5 pb-2">
                    {resourcesMap.get(skill)!.map((r, j) => (
                      <ResourceLink key={j} resource={r} />
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-white/40 text-sm italic">None identified.</p>
        )}
      </AccordionItem>

      {/* Improvements */}
      <AccordionItem
        title="Improvements"
        icon={<Lightbulb size={16} />}
        accentColor="#10b981"
        badge={report.improvements.length}
      >
        {report.improvements.length > 0 ? (
          <div className="space-y-1">
            {onSelectionChange && (
              <div className="flex justify-between items-center mb-3">
                <span className="text-xs text-white/40">Select improvements to apply</span>
                <button
                  onClick={selectAllImprovements}
                  className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors"
                >
                  {selectedImprovements.length === report.improvements.length ? "Deselect all" : "Select all"}
                </button>
              </div>
            )}
            {report.improvements.map((imp, i) => (
              <SelectableItem
                key={i}
                text={imp}
                selected={selectedImprovements.includes(imp)}
                onToggle={() => toggleImprovement(imp)}
                color="#10b981"
              />
            ))}
          </div>
        ) : (
          <p className="text-white/40 text-sm italic">None identified.</p>
        )}
      </AccordionItem>
    </div>
  );
}
