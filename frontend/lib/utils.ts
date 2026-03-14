import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Tailwind class merger — standard shadcn/ui pattern */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format a date string for display */
export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

/** Truncate long strings for display */
export function truncate(str: string, max = 80): string {
  return str.length > max ? str.slice(0, max - 1) + "…" : str;
}

/** Download a string as a file in the browser */
export function downloadText(content: string, filename: string, mimeType = "text/plain"): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** Convert a score (0–100) to a human-readable percentage string */
export function formatScore(score: number): string {
  return `${Math.round(score)}%`;
}

/** Clamp a number between min and max */
export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/** Generate the SVG arc path for the radial progress chart */
export function describeArc(
  cx: number,
  cy: number,
  r: number,
  startAngle: number,
  endAngle: number
): string {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const start = {
    x: cx + r * Math.cos(toRad(startAngle - 90)),
    y: cy + r * Math.sin(toRad(startAngle - 90)),
  };
  const end = {
    x: cx + r * Math.cos(toRad(endAngle - 90)),
    y: cy + r * Math.sin(toRad(endAngle - 90)),
  };
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 1 ${end.x} ${end.y}`;
}
