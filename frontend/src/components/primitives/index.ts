/**
 * MarketPulse primitive components.
 *
 * These are the small, design-token-driven building blocks that every
 * higher-level surface (Today, Tickers, Agents, Track Record) composes
 * from. Each one is deliberately presentational: no fetching, no state.
 *
 * Source of truth for the styles: `app/globals.css` `.al-*` classes.
 */

export { Pill, friendlyValidationStatus } from "./Pill";
export type { PillProps, PillVariant } from "./Pill";

export { KpiCard } from "./KpiCard";
export type { KpiCardProps } from "./KpiCard";

export { MetricChip } from "./MetricChip";
export type { MetricChipProps } from "./MetricChip";

export { InfoHint } from "./InfoHint";
export type { InfoHintProps } from "./InfoHint";

export { RingSVG } from "./RingSVG";
export type { RingSVGProps } from "./RingSVG";

export { SectorDot, sectorKindFromId } from "./SectorDot";
export type { SectorDotProps, SectorKind } from "./SectorDot";

export { ThesisBanner } from "./ThesisBanner";
export type { ThesisBannerProps } from "./ThesisBanner";
