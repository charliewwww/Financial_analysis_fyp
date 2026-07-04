"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";

import { fetchReports } from "@/lib/api";
import type { ReportSummary } from "@/types/api";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState, EmptyState } from "@/components/StateMessage";
import { Pill, type PillVariant } from "@/components/primitives";
import { useMarket, MARKET_LABELS } from "@/lib/market-context";

const PAGE_SIZE = 15;

function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function validationVariant(status: string | null): PillVariant {
  if (!status) return "gray";
  const s = status.toLowerCase();
  if (s.includes("pass")) return "green";
  if (s.includes("warn")) return "amber";
  if (s.includes("fail")) return "red";
  return "gray";
}

function ReportRow({ report }: { report: ReportSummary }) {
  return (
    <Link
      href={`/reports/${report.id}`}
      className="grid grid-cols-[1fr_auto] items-center gap-3 rounded-xl border px-4 py-3 transition hover:-translate-y-0.5 sm:grid-cols-[minmax(0,1fr)_120px_120px_150px]"
      style={{ borderColor: "var(--al-outline)" }}
    >
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold">{report.sector_name}</div>
        <div className="mt-0.5 text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
          {fmtDateTime(report.created_at)}
        </div>
      </div>
      <div className="hidden sm:block">
        <Pill variant={report.confidence_score != null && report.confidence_score >= 7 ? "green" : "gray"}>
          {report.confidence_score != null ? `${report.confidence_score}/10` : "no score"}
        </Pill>
      </div>
      <div className="hidden sm:block">
        <Pill variant={validationVariant(report.validation_status)}>
          {report.validation_status ?? "unvalidated"}
        </Pill>
      </div>
      <div className="flex items-center justify-end gap-2 text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
        <span className="tabular-nums">{report.news_used} news</span>
        <Pill variant="gray">{report.status}</Pill>
      </div>
    </Link>
  );
}

export default function ReportsPage() {
  const { market } = useMarket();
  const [page, setPage] = useState(1);

  useEffect(() => {
    setPage(1);
  }, [market]);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["reports", { page, market }],
    queryFn: () => fetchReports({ page, page_size: PAGE_SIZE, market }),
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="al-eyebrow">Report archive</div>
          <h1 className="mt-1 text-3xl md:text-4xl">Recent Reports</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
            Every full pipeline run is archived here with its confidence score and validation status. Open one to read the
            full analysis, predictions, and the raw data it was built on.
          </p>
        </div>
        <Pill variant="gold">
          <FileText className="size-3.5" aria-hidden /> {MARKET_LABELS[market].short} · {data?.total ?? "—"} archived
        </Pill>
      </header>

      {isError ? (
        <ErrorState title="Failed to load reports" detail={String(error)} onRetry={() => refetch()} />
      ) : null}

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      ) : data && data.items.length > 0 ? (
        <section className="space-y-2">
          {data.items.map((report) => (
            <ReportRow key={report.id} report={report} />
          ))}
        </section>
      ) : (
        <EmptyState
          title="No reports yet"
          detail="Run an analysis from the Decision Desk; finished runs are archived here automatically."
        />
      )}

      {totalPages > 1 ? (
        <div className="flex items-center justify-center gap-4 pt-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="text-sm text-muted-foreground transition-colors hover:text-foreground disabled:opacity-40"
          >
            ← Previous
          </button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="text-sm text-muted-foreground transition-colors hover:text-foreground disabled:opacity-40"
          >
            Next →
          </button>
        </div>
      ) : null}
    </div>
  );
}
