import * as React from "react";
import { cn } from "@/lib/utils";

export interface ThesisBannerProps {
  /** Eyebrow label, e.g. "Investment thesis" or "Today's read". */
  label?: string;
  children: React.ReactNode;
  className?: string;
}

/**
 * ThesisBanner — leading quote block at the top of a report or signal
 * detail page. Gold left rail + tinted gradient wash. Ports the
 * "thesis banner" element from ui/page_reports.py.
 */
export function ThesisBanner({
  label = "Investment thesis",
  children,
  className,
}: ThesisBannerProps) {
  return (
    <section className={cn("al-thesis-banner", className)} role="note">
      <div className="al-thesis-banner-label">{label}</div>
      <div className="al-thesis-banner-text">{children}</div>
    </section>
  );
}
