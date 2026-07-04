import * as React from "react";
import { cn } from "@/lib/utils";

export type SectorKind = "ai" | "space" | "optical" | "unknown";

const SECTOR_ID_MAP: Record<string, SectorKind> = {
  ai_semiconductors: "ai",
  space_rockets: "space",
  optical_communications: "optical",
};

export function sectorKindFromId(sectorId?: string | null): SectorKind {
  if (!sectorId) return "unknown";
  return SECTOR_ID_MAP[sectorId] ?? "unknown";
}

export interface SectorDotProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** Either pass a known kind directly… */
  kind?: SectorKind;
  /** …or a sector_id and we'll map it. */
  sectorId?: string | null;
}

/**
 * SectorDot — small coloured disc that identifies which sector lens
 * something belongs to (AI / Space / Optical). Glow ring uses the
 * dot's own colour at 15% alpha, courtesy of color-mix() in CSS.
 */
export function SectorDot({ kind, sectorId, className, ...rest }: SectorDotProps) {
  const resolved: SectorKind = kind ?? sectorKindFromId(sectorId);
  return (
    <span
      data-sector={resolved}
      className={cn("al-sector-dot", className)}
      aria-hidden="true"
      {...rest}
    />
  );
}
