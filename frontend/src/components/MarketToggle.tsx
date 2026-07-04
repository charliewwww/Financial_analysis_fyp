"use client";

import { MARKET_LABELS, useMarket, type MarketId } from "@/lib/market-context";

const MARKETS: MarketId[] = ["us", "hk"];

/**
 * MarketToggle — global US / HK switch shown in the header.
 *
 * The selected market scopes quick-picks, sector reads and benchmarks across
 * every page via the MarketProvider context.
 */
export function MarketToggle() {
  const { market, setMarket } = useMarket();

  return (
    <div
      role="group"
      aria-label="Market"
      className="inline-flex items-center rounded-full border border-border p-0.5 text-xs"
    >
      {MARKETS.map((m) => {
        const active = market === m;
        return (
          <button
            key={m}
            type="button"
            aria-pressed={active}
            onClick={() => setMarket(m)}
            title={MARKET_LABELS[m].name}
            className={
              active
                ? "rounded-full px-2.5 py-1 font-semibold text-foreground shadow-sm transition-colors"
                : "rounded-full px-2.5 py-1 text-muted-foreground hover:text-foreground transition-colors"
            }
            style={active ? { background: "var(--al-gold)", color: "#1a1206" } : undefined}
          >
            {MARKET_LABELS[m].short}
          </button>
        );
      })}
    </div>
  );
}
