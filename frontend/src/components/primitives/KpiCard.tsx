import * as React from "react";
import { cn } from "@/lib/utils";

export interface KpiCardProps {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  /** Right-side adornment: pill, sparkline, etc. */
  adornment?: React.ReactNode;
  className?: string;
}

/**
 * KpiCard — frosted glass tile used on dashboard hero strips
 * (Market Pulse, Today summary, Track Record header).
 */
export function KpiCard({ label, value, sub, adornment, className }: KpiCardProps) {
  return (
    <div className={cn("al-glass p-4 flex flex-col gap-1", className)}>
      <div className="flex items-start justify-between gap-2">
        <span className="al-eyebrow">{label}</span>
        {adornment ? <div className="shrink-0">{adornment}</div> : null}
      </div>
      <div
        className="font-heading font-extrabold text-2xl tracking-tight tabular-nums"
        style={{ color: "var(--al-on-surface)" }}
      >
        {value}
      </div>
      {sub ? (
        <div className="text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
          {sub}
        </div>
      ) : null}
    </div>
  );
}
