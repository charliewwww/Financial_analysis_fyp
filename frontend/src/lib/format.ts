/**
 * Shared date/time formatting helpers.
 *
 * Centralizes the date formats that were previously duplicated across pages
 * so timestamps read consistently everywhere (Tier 4.2).
 */

/** Date + time, e.g. "May 28, 4:30 PM". Used for freshness / "updated" stamps. */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Date only, e.g. "May 28, 2026". Used where time-of-day adds noise. */
export function formatDay(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/** Short clock time, e.g. "4:30 PM". Used for auto-refresh "updated" labels. */
export function formatClock(value: number | string | null | undefined): string {
  if (value == null) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
}

/**
 * Normalize a raw confidence value to the 0-10 analyst scale.
 *
 * Backends sometimes store confidence as 0-1 and sometimes as 0-10; this
 * collapses both into 0-10. Returns null when the input is not a number.
 */
export function confidenceToTen(value: number | null | undefined): number | null {
  if (value == null || Number.isNaN(value)) return null;
  const normalized = value <= 1 ? value * 10 : value;
  return Math.max(0, Math.min(normalized, 10));
}

/**
 * Render a numeric score with at most one decimal and no floating-point noise.
 * e.g. 7.800000000001 -> "7.8", 8 -> "8".
 */
export function formatScore(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return String(Number(value.toFixed(1)));
}

