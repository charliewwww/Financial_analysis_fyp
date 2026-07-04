import * as React from "react";
import { Info } from "lucide-react";
import { cn } from "@/lib/utils";

export interface InfoHintProps {
  /** Plain-language explanation of the term. */
  label: string;
  /** Accessible name for the trigger (defaults to "More information"). */
  srLabel?: string;
  className?: string;
}

/**
 * InfoHint — a tiny, dependency-free tooltip for explaining finance jargon.
 *
 * Reveals on hover AND keyboard focus (the trigger is a real button), so it
 * works for mouse, keyboard and screen-reader users without pulling in a
 * popover library. The copy is meant to demystify a term in one sentence.
 */
export function InfoHint({ label, srLabel = "More information", className }: InfoHintProps) {
  return (
    <span className={cn("group relative inline-flex align-middle", className)}>
      <button
        type="button"
        aria-label={srLabel}
        className="inline-grid size-4 place-items-center rounded-full text-muted-foreground transition-colors hover:text-foreground focus:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Info className="size-3.5" aria-hidden />
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 w-56 -translate-x-1/2 rounded-lg border p-2.5 text-xs leading-5 opacity-0 shadow-md transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100"
        style={{
          background: "var(--al-surface, hsl(var(--popover, var(--background))))",
          borderColor: "var(--al-outline)",
          color: "var(--al-on-surface-muted)",
        }}
      >
        {label}
      </span>
    </span>
  );
}
