"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { TrendingDown, TrendingUp } from "lucide-react";
import {
  fetchMarketSectors,
  fetchReports,
  type SectorRead,
} from "@/lib/api";
import { useMarket, MARKET_LABELS } from "@/lib/market-context";
import { MetricChip, Pill } from "@/components/primitives";
import { ErrorState, EmptyState } from "@/components/StateMessage";
import { ReportTable } from "@/components/ReportTable";
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

function SectorPulseCard({ sector }: { sector: SectorRead }) {
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

function SectorPulse() {
  const { market } = useMarket();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["market-sectors", market],
    queryFn: () => fetchMarketSectors(market),
    staleTime: 5 * 60 * 1000,
  });

  if (isError) {
    return (
      <ErrorState
        title="Failed to load sector data"
        detail={String(error)}
        onRetry={() => refetch()}
      />
    );
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

function ArchiveTab() {
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["reports", { page }],
    queryFn: () => fetchReports({ page, page_size: PAGE_SIZE }),
  });

  const total = data?.total ?? 0;
  const totalPages = total ? Math.ceil(total / PAGE_SIZE) : 1;

  if (isError) {
    return (
      <ErrorState
        title="Failed to load archive"
        detail={String(error)}
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
        Legacy long-form sector essays kept for audit and historical context. New analysis
        lives on the Stocks desk as signal cards.
      </p>
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : total === 0 ? (
        <EmptyState
          title="No archived reports yet"
          detail="The current pipeline produces signal cards instead of long-form essays. This archive stays available for any legacy reports."
        />
      ) : (
        <section className="al-glass overflow-hidden p-2">
          <ReportTable reports={data?.items ?? []} />
        </section>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4 pt-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="text-sm text-muted-foreground hover:text-foreground disabled:opacity-40 transition-colors"
          >
            ← Previous
          </button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="text-sm text-muted-foreground hover:text-foreground disabled:opacity-40 transition-colors"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}

export default function SectorsPage() {
  const { market } = useMarket();
  const [tab, setTab] = useState<"pulse" | "archive">("pulse");

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="al-eyebrow">Sector research · {MARKET_LABELS[market].name}</div>
        <h1 className="text-3xl md:text-4xl">Sectors</h1>
        <p className="max-w-3xl text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
          Each sector is read from a real instrument — a sector ETF or index — alongside a
          market-cap weighted aggregate of its largest names, so the number reflects the whole
          sector rather than a handful of tickers.
        </p>
      </header>

      <div role="tablist" aria-label="Sector views" className="inline-flex rounded-full border border-border p-0.5 text-sm">
        <button
          role="tab"
          aria-selected={tab === "pulse"}
          onClick={() => setTab("pulse")}
          className={
            tab === "pulse"
              ? "rounded-full bg-muted px-3 py-1.5 font-medium text-foreground shadow-sm"
              : "rounded-full px-3 py-1.5 text-muted-foreground hover:text-foreground"
          }
        >
          Sector pulse
        </button>
        <button
          role="tab"
          aria-selected={tab === "archive"}
          onClick={() => setTab("archive")}
          className={
            tab === "archive"
              ? "rounded-full bg-muted px-3 py-1.5 font-medium text-foreground shadow-sm"
              : "rounded-full px-3 py-1.5 text-muted-foreground hover:text-foreground"
          }
        >
          Archive
        </button>
      </div>

      {tab === "pulse" ? <SectorPulse /> : <ArchiveTab />}
    </div>
  );
}
