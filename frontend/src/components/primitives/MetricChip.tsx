import * as React from "react";
import { cn } from "@/lib/utils";
import { InfoHint } from "./InfoHint";

export interface MetricChipProps {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  className?: string;
  /** Optional one-sentence explanation shown via an info tooltip on the label. */
  hint?: string;
}

/**
 * MetricChip — compact stat used inside report metric strips and
 * agent debate cards. Tighter than KpiCard, suitable for horizontal rows.
 */
export function MetricChip({ label, value, sub, className, hint }: MetricChipProps) {
  return (
    <div className={cn("al-metric-chip", className)}>
      <span className="al-metric-chip-label inline-flex items-center gap-1">
        {label}
        {hint ? <InfoHint label={hint} srLabel={`What \"${label}\" means`} /> : null}
      </span>
      <span className="al-metric-chip-value">{value}</span>
      {sub ? <span className="al-metric-chip-sub">{sub}</span> : null}
    </div>
  );
}
