/**
 * MarketPulse brand mark — a rounded tile with a market "pulse" waveform.
 *
 * Pure SVG, themeable via the gold design tokens. Used in the header,
 * mobile nav, and anywhere the product needs to identify itself.
 */

interface BrandMarkProps {
  /** Pixel size of the square mark. Defaults to 24 (h-6 w-6). */
  size?: number;
  className?: string;
  title?: string;
}

export function BrandMark({ size = 24, className, title = "MarketPulse" }: BrandMarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      role="img"
      aria-label={title}
      className={className}
      style={{ filter: "drop-shadow(var(--al-shadow-gold))" }}
    >
      <defs>
        <linearGradient id="mp-brand-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--al-gold)" />
          <stop offset="100%" stopColor="var(--al-gold-light)" />
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="32" height="32" rx="8" fill="url(#mp-brand-grad)" />
      {/* Pulse / heartbeat-style market line */}
      <path
        d="M5 18 L11 18 L14 9 L18 23 L21 14 L24 18 L27 18"
        fill="none"
        stroke="#1a1205"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.92"
      />
    </svg>
  );
}
