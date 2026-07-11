"use client";

import { useQuery } from "@tanstack/react-query";
import { TrendingDown, TrendingUp } from "lucide-react";

import { fetchMarketSectors, type SectorRead } from "@/lib/api";
import { useMarket } from "@/lib/market-context";
import { MetricChip, Pill } from "@/components/primitives";
import { ErrorState, EmptyState } from "@/components/StateMessage";
import { Skeleton } from "@/components/ui/skeleton";

function pct(value: number | null): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function ChangeValue({ value }: { value: number | null }) {
  if (value == null || Number.isNaN(value)) return <span>—</span>;
  const tone =
    value > 0 ? "var(--al-bullish)" : value < 0 ? "var(--al-bearish)" : "var(--al-on-surface-muted)";
  return (
    <span style={{ color: tone }} className="inline-flex items-center gap-1">
      {value > 0 ? <TrendingUp className="size-3.5" aria-hidden /> : value < 0 ? <TrendingDown className="size-3.5" aria-hidden /> : null}
      {pct(value)}
    </span>
  );
}

export function SectorPulseCard({ sector }: { sector: SectorRead }) {
  const { advancers, decliners, total } = sector.breadth;
  return (
    <article className="al-glass p-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg">{sector.name}</h3>
          <p className="mt-0.5 text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
            {sector.instrument.name} · {sector.instrument.ticker}
          </p>
        </div>
        <Pill variant="gray">{sector.constituent_count} names</Pill>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <MetricChip
          label="Index / ETF · 1-week"
          value={<ChangeValue value={sector.instrument.change_1w_pct} />}
          sub={sector.instrument.price != null ? `level ${sector.instrument.price}` : "the sector instrument"}
        />
        <MetricChip
          label="Cap-weighted basket · 1-week"
          value={<ChangeValue value={sector.cap_weighted_change_1w_pct} />}
          sub="weighted by market cap"
        />
        <MetricChip
          label="Breadth"
          value={total > 0 ? `${advancers} up · ${decliners} down` : "—"}
          sub={`of ${total} priced names`}
        />
      </div>

      {sector.top_movers.length > 0 ? (
        <div className="flex flex-wrap gap-2 pt-1 text-xs">
          {sector.top_movers.map((m) => (
            <span
              key={`top-${m.ticker}`}
              className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5"
              style={{ color: "var(--al-bullish)" }}
            >
              <TrendingUp className="size-3" aria-hidden />
              {m.ticker} {pct(m.change_1w_pct)}
            </span>
          ))}
          {sector.bottom_movers.map((m) => (
            <span
              key={`bot-${m.ticker}`}
              className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5"
              style={{ color: "var(--al-bearish)" }}
            >
              <TrendingDown className="size-3" aria-hidden />
              {m.ticker} {pct(m.change_1w_pct)}
            </span>
          ))}
        </div>
      ) : null}
    </article>
  );
}

/**
 * SectorPulse — the market-structure overview grid (breadth, movers,
 * cap-weighted performance). Extracted so it can be shown both on the standalone
 * Sectors route and embedded inside the Stocks page's Sector tab.
 */
export function SectorPulse() {
  const { market } = useMarket();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["market-sectors", market],
    queryFn: () => fetchMarketSectors(market),
    staleTime: 5 * 60 * 1000,
  });

  if (isError) {
    return <ErrorState title="Failed to load sector data" detail={String(error)} onRetry={() => refetch()} />;
  }

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-44 w-full" />
        ))}
      </div>
    );
  }

  const sectors = data?.sectors ?? [];
  if (sectors.length === 0) {
    return <EmptyState title="No sectors configured for this market" />;
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {sectors.map((s) => (
        <SectorPulseCard key={s.id} sector={s} />
      ))}
    </div>
  );
}
