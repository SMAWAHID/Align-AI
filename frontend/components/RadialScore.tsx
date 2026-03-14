"use client";

import { useEffect, useRef, useState } from "react";
import { cn, describeArc, formatScore } from "@/lib/utils";
import {
  getScoreTier,
  SCORE_TIER_COLORS,
  SCORE_TIER_LABELS,
  type ScoreBreakdown,
} from "@/types/api";

interface RadialScoreProps {
  breakdown: ScoreBreakdown;
  className?: string;
  animate?: boolean;
}

const TRACK_COLOR = "rgba(255,255,255,0.08)";
const CX = 120;
const CY = 120;
const R_OUTER = 95;
const R_INNER = 68;

function Arc({
  score,
  radius,
  color,
  trackColor,
  strokeWidth,
  animated,
  delay,
}: {
  score: number;
  radius: number;
  color: string;
  trackColor: string;
  strokeWidth: number;
  animated: boolean;
  delay: number;
}) {
  const [displayed, setDisplayed] = useState(animated ? 0 : score);

  useEffect(() => {
    if (!animated) return;
    let frame: number;
    let start: number | null = null;
    const duration = 1200;

    function tick(ts: number) {
      if (!start) start = ts + delay;
      const elapsed = ts - start;
      if (elapsed < 0) {
        frame = requestAnimationFrame(tick);
        return;
      }
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayed(eased * score);
      if (progress < 1) frame = requestAnimationFrame(tick);
    }

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [score, animated, delay]);

  const angle = (displayed / 100) * 360 * 0.999; // avoid full-circle SVG artifact
  const path = angle > 0 ? describeArc(CX, CY, radius, 0, angle) : null;
  const trackPath = describeArc(CX, CY, radius, 0, 360 * 0.999);

  return (
    <>
      {/* Track */}
      <path
        d={trackPath}
        fill="none"
        stroke={trackColor}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
      />
      {/* Fill */}
      {path && (
        <path
          d={path}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 6px ${color}88)` }}
        />
      )}
    </>
  );
}

export function RadialScore({
  breakdown,
  className,
  animate = true,
}: RadialScoreProps) {
  const tier = getScoreTier(breakdown.final);
  const color = SCORE_TIER_COLORS[tier];
  const label = SCORE_TIER_LABELS[tier];

  const [displayedFinal, setDisplayedFinal] = useState(animate ? 0 : breakdown.final);

  useEffect(() => {
    if (!animate) return;
    let frame: number;
    let start: number | null = null;
    const duration = 1400;
    const targetDelay = 0;

    function tick(ts: number) {
      if (!start) start = ts + targetDelay;
      const elapsed = ts - start;
      if (elapsed < 0) { frame = requestAnimationFrame(tick); return; }
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayedFinal(eased * breakdown.final);
      if (progress < 1) frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [breakdown.final, animate]);

  return (
    <div className={cn("flex flex-col items-center gap-6", className)}>
      {/* SVG Chart */}
      <div className="relative">
        <svg
          viewBox="0 0 240 240"
          width={240}
          height={240}
          className="overflow-visible"
          aria-label={`Match score: ${formatScore(breakdown.final)}`}
          role="img"
        >
          {/* Outer ring: final/composite score */}
          <Arc
            score={breakdown.final}
            radius={R_OUTER}
            color={color}
            trackColor={TRACK_COLOR}
            strokeWidth={14}
            animated={animate}
            delay={0}
          />
          {/* Inner ring: semantic score */}
          <Arc
            score={breakdown.semantic}
            radius={R_INNER}
            color="#6366f1"
            trackColor={TRACK_COLOR}
            strokeWidth={10}
            animated={animate}
            delay={200}
          />

          {/* Centre text */}
          <text
            x={CX}
            y={CY - 10}
            textAnchor="middle"
            dominantBaseline="central"
            fill={color}
            fontSize="36"
            fontWeight="700"
            fontFamily="'DM Mono', monospace"
            style={{ letterSpacing: "-1px" }}
          >
            {Math.round(displayedFinal)}
          </text>
          <text
            x={CX}
            y={CY + 22}
            textAnchor="middle"
            fill="rgba(255,255,255,0.5)"
            fontSize="13"
            fontFamily="'DM Sans', sans-serif"
          >
            out of 100
          </text>
        </svg>

        {/* Tier badge */}
        <div
          className="absolute -bottom-2 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full text-xs font-semibold tracking-wide"
          style={{ background: `${color}22`, color, border: `1px solid ${color}44` }}
        >
          {label}
        </div>
      </div>

      {/* Score breakdown bars */}
      <div className="w-full max-w-xs space-y-3">
        <ScoreBar label="Semantic Similarity" value={breakdown.semantic} color="#6366f1" delay={400} animate={animate} />
        <ScoreBar label="Keyword Overlap" value={breakdown.keyword} color="#06b6d4" delay={600} animate={animate} />
        <ScoreBar label="Composite Score" value={breakdown.final} color={color} delay={800} animate={animate} />
      </div>
    </div>
  );
}

function ScoreBar({
  label,
  value,
  color,
  delay,
  animate,
}: {
  label: string;
  value: number;
  color: string;
  delay: number;
  animate: boolean;
}) {
  const [width, setWidth] = useState(animate ? 0 : value);

  useEffect(() => {
    if (!animate) { setWidth(value); return; }
    let frame: number;
    let start: number | null = null;
    const duration = 900;

    function tick(ts: number) {
      if (!start) start = ts + delay;
      const elapsed = ts - start;
      if (elapsed < 0) { frame = requestAnimationFrame(tick); return; }
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setWidth(eased * value);
      if (progress < 1) frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, animate, delay]);

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-white/60">{label}</span>
        <span className="font-mono font-semibold" style={{ color }}>
          {Math.round(width)}%
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
        <div
          className="h-full rounded-full transition-none"
          style={{
            width: `${width}%`,
            background: color,
            boxShadow: `0 0 8px ${color}66`,
          }}
        />
      </div>
    </div>
  );
}
