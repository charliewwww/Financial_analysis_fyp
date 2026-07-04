import * as React from "react";

import { formatScore } from "@/lib/format";

export interface RingSVGProps {
  score: number;
  max?: number;
  size?: number;
  /** Threshold below which the ring shifts to the warning hue. Default 4/10. */
  warnBelow?: number;
  className?: string;
  /** Optional override for inner big number (e.g. show raw score not %). */
  format?: "percent" | "score";
}

/**
 * RingSVG — donut indicator showing `score / max` as a percentage.
 *
 * Port of `ring_svg()` from ui/components.py (line 52). Colours pull from
 * design tokens so dark/light mode stays consistent.
 */
export function RingSVG({
  score,
  max = 10,
  size = 144,
  warnBelow = 4,
  className,
  format = "percent",
}: RingSVGProps) {
  const safeMax = max > 0 ? max : 1;
  const pct = Math.max(0, Math.min(score / safeMax, 1));
  const r = 64;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - pct);
  const isWarn = score < warnBelow;

  // Use CSS variables so dark mode flips automatically.
  const ringColor = isWarn ? "var(--al-bearish)" : "var(--al-gold)";
  const trackColor = "var(--al-bar-track)";
  const labelColor = "var(--al-on-surface)";
  const subColor = "var(--al-on-surface-muted)";

  const big = format === "percent" ? Math.round(pct * 100) : formatScore(score);

  return (
    <div className={className} style={{ display: "inline-block", textAlign: "center" }}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 144 144"
        role="img"
        aria-label={`Score ${score} of ${safeMax}`}
      >
        <circle cx="72" cy="72" r={r} stroke={trackColor} strokeWidth={8} fill="none" />
        <circle
          cx="72"
          cy="72"
          r={r}
          stroke={ringColor}
          strokeWidth={12}
          fill="none"
          strokeDasharray={circ.toFixed(1)}
          strokeDashoffset={offset.toFixed(1)}
          transform="rotate(-90 72 72)"
          strokeLinecap="round"
        />
        <text
          x="72"
          y="66"
          textAnchor="middle"
          dominantBaseline="central"
          fontSize="32"
          fontWeight={800}
          fill={labelColor}
          fontFamily="var(--font-manrope), ui-sans-serif, system-ui, sans-serif"
        >
          {big}
          {format === "percent" ? (
            <tspan fontSize="14" dy="-4">
              %
            </tspan>
          ) : null}
        </text>
        <text
          x="72"
          y="92"
          textAnchor="middle"
          fontSize="10"
          fill={subColor}
          fontFamily="var(--font-inter), ui-sans-serif, system-ui, sans-serif"
        >
          {formatScore(score)}/{safeMax}
        </text>
      </svg>
    </div>
  );
}
