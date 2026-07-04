import * as React from "react";
import { cn } from "@/lib/utils";

export type PillVariant = "green" | "amber" | "red" | "gray" | "gold";

export interface PillProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: PillVariant;
  children: React.ReactNode;
}

/**
 * Pill — small status / category badge.
 *
 * Variants are wired through CSS in `globals.css` via `[data-variant=...]`,
 * so colours stay in one place (the design tokens file).
 */
export function Pill({ variant = "gray", className, children, ...rest }: PillProps) {
  return (
    <span
      data-variant={variant}
      className={cn("al-pill", className)}
      {...rest}
    >
      {children}
    </span>
  );
}

/**
 * Map a backend validation_status string to user-facing label + pill variant.
 * Mirrors `friendly_status()` and `pill_cls()` from ui/components.py.
 */
export function friendlyValidationStatus(status: string | null | undefined): {
  label: string;
  variant: PillVariant;
} | null {
  if (!status) return null;
  const s = status.toUpperCase();
  if (s.includes("FAILED")) return { label: "Needs Review", variant: "amber" };
  if (s.includes("WARNING")) return { label: "Reviewed", variant: "amber" };
  if (s.includes("PASSED")) return { label: "Verified", variant: "green" };
  return null;
}
