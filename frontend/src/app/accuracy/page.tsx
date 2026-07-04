"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, CheckCircle2, Clock, Gavel, ShieldCheck, Target, XCircle } from "lucide-react";

import { fetchAblation, fetchAccuracyStats, fetchChiefVerdictAccuracy, fetchReport, fetchReports, fetchSignals } from "@/lib/api";
import type { ChiefVerdictRecord, Prediction, ReportDetail, Signal, SignalTypeBreakdown } from "@/types/api";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/StateMessage";
import { MetricChip, Pill, type PillVariant } from "@/components/primitives";
import { useMarket, marketForTicker, MARKET_LABELS } from "@/lib/market-context";

const SIGNAL_VARIANT: Record<Signal, PillVariant> = {
  BULLISH: "green",
  BEARISH: "red",
  NEUTRAL: "gray",
};

// Below this many matured checks, accuracy figures are too small a sample to be
// statistically meaningful — we surface a persistent caveat to say so.
const ACCURACY_SIGNIFICANCE_MIN = 30;

interface AblationResultPayload {
  total_reports_analyzed?: number;
  reports_with_pipeline_state?: number;
  retry_rate_pct?: number;
  avg_discrepancies_before?: number;
  avg_discrepancies_after?: number;
  discrepancy_reduction_pct?: number;
  intervention_rate_pct?: number;
  avg_citation_rate_pct?: number;
  status_counts?: Record<string, number>;
  summary_bullets?: string[];
}

function fmtPct(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "-";
  return `${value.toFixed(digits)}%`;
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function fmtMoney(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "-";
  return `$${value.toFixed(2)}`;
}

function reportAccuracy(report: ReportDetail) {
  const checked = report.predictions.filter((prediction) => prediction.prediction_correct != null);
  const correct = checked.filter((prediction) => prediction.prediction_correct).length;
  const pending = report.predictions.length - checked.length;
  return {
    checked: checked.length,
    correct,
    pending,
    accuracy: checked.length ? Math.round((correct / checked.length) * 1000) / 10 : null,
  };
}

function PredictionCard({ prediction }: { prediction: Prediction }) {
  const direction = (prediction.ai_direction ?? "NEUTRAL").toUpperCase() as Signal;
  const result =
    prediction.prediction_correct == null
      ? { label: "pending", variant: "gray" as PillVariant, Icon: Clock }
      : prediction.prediction_correct
        ? { label: "correct", variant: "green" as PillVariant, Icon: CheckCircle2 }
        : { label: "missed", variant: "red" as PillVariant, Icon: XCircle };
  const ResultIcon = result.Icon;
  const actualChange = prediction.actual_change_1w;

  return (
    <article className="rounded-xl border p-4" style={{ borderColor: "var(--al-outline)" }}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-mono text-lg font-bold">{prediction.ticker}</div>
          <div className="mt-1 text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
            {fmtMoney(prediction.price_at_report)} at report
            {prediction.price_1w_later != null ? ` -> ${fmtMoney(prediction.price_1w_later)}` : " -> awaiting"}
          </div>
        </div>
        <div className="flex flex-wrap justify-end gap-1.5">
          <Pill variant={SIGNAL_VARIANT[direction] ?? "gray"}>{direction.toLowerCase()}</Pill>
          <Pill variant={result.variant}>
            <ResultIcon className="size-3" aria-hidden />
            {result.label}
          </Pill>
        </div>
      </div>

      {prediction.ai_predicted_change ? (
        <div className="mt-3 text-sm font-semibold">Expected move: {prediction.ai_predicted_change}</div>
      ) : null}

      {actualChange != null ? (
        <div className="mt-3 flex items-center gap-3 text-xs">
          <div className="bar-track flex-1">
            <div
              className={actualChange >= 0 ? "bar-fill bar-bullish" : "bar-fill bar-bearish"}
              style={{ width: `${Math.min(100, Math.max(8, Math.abs(actualChange) * 8))}%` }}
            />
          </div>
          <span className="tabular-nums" style={{ color: actualChange >= 0 ? "#16a34a" : "#dc2626" }}>
            {actualChange >= 0 ? "+" : ""}{actualChange.toFixed(1)}%
          </span>
        </div>
      ) : null}

      {prediction.ai_reasoning ? (
        <p className="mt-3 line-clamp-3 text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
          {prediction.ai_reasoning}
        </p>
      ) : null}
      {prediction.ai_risk ? (
        <p className="mt-2 line-clamp-2 text-xs text-amber-600 dark:text-amber-400">Risk: {prediction.ai_risk}</p>
      ) : null}
    </article>
  );
}

function AccuracyTimeline({ reports }: { reports: ReportDetail[] }) {
  const rows = reports.map((report) => ({ report, ...reportAccuracy(report) })).filter((row) => row.report.predictions.length > 0);

  return (
    <section className="al-glass p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="al-eyebrow">Accuracy over time</div>
          <h2 className="mt-1 text-lg">Per-report prediction score</h2>
        </div>
        <BarChart3 className="size-5" aria-hidden style={{ color: "var(--al-gold)" }} />
      </div>

      {rows.some((row) => row.accuracy != null) ? (
        <div className="space-y-3">
          {rows.slice(0, 12).map((row) => (
            <div key={row.report.id} className="grid gap-2 sm:grid-cols-[170px_1fr_110px] sm:items-center">
              <div>
                <Link href={`/reports/${row.report.id}`} className="text-sm font-semibold hover:underline">
                  {row.report.sector_name}
                </Link>
                <div className="text-xs" style={{ color: "var(--al-on-surface-muted)" }}>{fmtDate(row.report.created_at)}</div>
              </div>
              <div className="bar-track h-3">
                <div className="bar-fill" style={{ width: `${row.accuracy ?? 0}%` }} />
              </div>
              <div className="text-right text-sm tabular-nums">
                {row.accuracy == null ? "pending" : `${row.accuracy.toFixed(1)}%`}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-xl border p-5 text-sm leading-6" style={{ borderColor: "var(--al-outline)", color: "var(--al-on-surface-muted)" }}>
          Accuracy tracking activates after predictions mature. Run analyses now; one week later, the system can score the actual price path against the AI call.
        </div>
      )}
    </section>
  );
}

function ReportSelector({
  reports,
  selectedId,
  setSelectedId,
}: {
  reports: ReportDetail[];
  selectedId: number | null;
  setSelectedId: (id: number) => void;
}) {
  if (!reports.length) return null;

  return (
    <section className="al-glass p-5 space-y-4">
      <div>
        <div className="al-eyebrow">Report ledger</div>
        <h2 className="mt-1 text-lg">Predictions by report</h2>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {reports.map((report) => {
          const stats = reportAccuracy(report);
          const active = selectedId === report.id;
          return (
            <button
              key={report.id}
              type="button"
              onClick={() => setSelectedId(report.id)}
              className="min-w-[230px] rounded-xl border px-3 py-3 text-left transition"
              style={{
                borderColor: active ? "var(--al-gold)" : "var(--al-outline)",
                background: active ? "rgba(200,169,81,0.10)" : "transparent",
              }}
            >
              <div className="text-sm font-semibold">{report.sector_name}</div>
              <div className="mt-1 text-xs" style={{ color: "var(--al-on-surface-muted)" }}>{fmtDate(report.created_at)}</div>
              <div className="mt-3 flex gap-1.5">
                <Pill variant={stats.accuracy == null ? "gray" : stats.accuracy >= 60 ? "green" : "amber"}>
                  {stats.accuracy == null ? "pending" : `${stats.accuracy.toFixed(1)}%`}
                </Pill>
                <Pill variant="gray">{report.predictions.length} calls</Pill>
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function AblationStudy() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["ablation"],
    queryFn: fetchAblation,
    staleTime: 5 * 60_000,
  });

  if (isLoading) return <Skeleton className="h-44 w-full rounded-2xl" />;
  if (isError)
    return (
      <ErrorState
        title="Failed to load validation study"
        detail={String(error)}
        onRetry={() => refetch()}
      />
    );
  if (!data) return null;

  const result = data as AblationResultPayload;

  return (
    <section className="al-glass p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="al-eyebrow">Validation impact</div>
          <h2 className="mt-1 text-lg">Numerical claim checking</h2>
        </div>
        <ShieldCheck className="size-5" aria-hidden style={{ color: "var(--al-gold)" }} />
      </div>
      <div className="grid gap-3 md:grid-cols-4">
        <MetricChip label="Reports" value={result.total_reports_analyzed ?? 0} />
        <MetricChip label="Retry rate" value={fmtPct(result.retry_rate_pct)} />
        <MetricChip label="Discrepancy cut" value={fmtPct(result.discrepancy_reduction_pct)} />
        <MetricChip label="Citation rate" value={fmtPct(result.avg_citation_rate_pct)} />
      </div>
      {result.summary_bullets?.length ? (
        <div className="grid gap-2 md:grid-cols-2">
          {result.summary_bullets.slice(0, 4).map((bullet) => (
            <div key={bullet} className="rounded-xl border p-3 text-sm leading-6" style={{ borderColor: "var(--al-outline)", color: "var(--al-on-surface-muted)" }}>
              {bullet}
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function SignalTypeBreakdownSection({ byType }: { byType: Record<string, SignalTypeBreakdown> }) {
  const rows = Object.entries(byType)
    .filter(([, value]) => value.total > 0)
    .sort((a, b) => b[1].total - a[1].total);
  if (!rows.length) return null;

  return (
    <section className="al-glass p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="al-eyebrow">Where the edge lives</div>
          <h2 className="mt-1 text-lg">Hit rate by signal type</h2>
        </div>
        <Target className="size-5" aria-hidden style={{ color: "var(--al-gold)" }} />
      </div>
      <div className="space-y-3">
        {rows.map(([type, value]) => (
          <div key={type} className="grid gap-2 sm:grid-cols-[200px_1fr_120px] sm:items-center">
            <div className="text-sm font-semibold">{type.replace(/_/g, " ").toLowerCase()}</div>
            <div className="bar-track h-3">
              <div className="bar-fill" style={{ width: `${value.accuracy_pct ?? 0}%` }} />
            </div>
            <div className="text-right text-sm tabular-nums">
              {value.accuracy_pct == null ? "pending" : `${value.accuracy_pct.toFixed(1)}%`}
              <span className="ml-1 text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
                ({value.correct}/{value.total})
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function ScoringMethodology() {
  return (
    <details className="al-glass p-5">
      <summary className="cursor-pointer text-sm font-semibold">
        How outcomes are scored
      </summary>
      <div className="mt-3 space-y-2 text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
        <p>
          Every directional call is stored with the price at the time of the report. A background job
          runs daily and, once a prediction is at least <span className="font-semibold">7 days</span> old,
          records the current price as the realised ~1-week move.
        </p>
        <p>
          A call counts as <span className="font-semibold text-green-600 dark:text-green-400">correct</span> when a
          BULLISH call rose, a BEARISH call fell, or a NEUTRAL call moved less than 2% either way. The figures
          here are a directional hit-rate, not a tradeable backtest — they ignore position sizing, fees, and
          slippage, and a one-week horizon is short. Read them as evidence of calibration, not a return claim.
        </p>
      </div>
    </details>
  );
}

const VERDICT_ACTION_VARIANT: Record<string, PillVariant> = {
  BUY: "green",
  SELL: "red",
  HOLD: "gray",
};

function HouseCallRow({ record }: { record: ChiefVerdictRecord }) {
  const result =
    record.verdict_correct == null
      ? { label: "pending", variant: "gray" as PillVariant, Icon: Clock }
      : record.verdict_correct
        ? { label: "correct", variant: "green" as PillVariant, Icon: CheckCircle2 }
        : { label: "missed", variant: "red" as PillVariant, Icon: XCircle };
  const ResultIcon = result.Icon;
  const change = record.actual_change_1w;

  return (
    <div className="grid gap-2 rounded-xl border p-3 sm:grid-cols-[120px_1fr_auto] sm:items-center" style={{ borderColor: "var(--al-outline)" }}>
      <div className="flex items-center gap-2">
        <span className="font-mono text-sm font-bold">{record.ticker}</span>
        <Pill variant={VERDICT_ACTION_VARIANT[(record.action || "").toUpperCase()] ?? "gray"}>{record.action}</Pill>
      </div>
      <div className="min-w-0">
        <p className="line-clamp-2 text-sm leading-6" style={{ color: "var(--al-on-surface)" }}>
          {record.deciding_reason || record.summary || "—"}
        </p>
        <div className="mt-0.5 text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
          {fmtDate(record.created_at)} · conviction {record.conviction ?? "-"}/5
        </div>
      </div>
      <div className="flex items-center justify-end gap-2">
        {change != null ? (
          <span className="text-sm tabular-nums" style={{ color: change >= 0 ? "var(--al-positive, #16a34a)" : "var(--al-negative, #dc2626)" }}>
            {change >= 0 ? "+" : ""}{change.toFixed(1)}%
          </span>
        ) : null}
        <Pill variant={result.variant}>
          <ResultIcon className="size-3" aria-hidden />
          {result.label}
        </Pill>
      </div>
    </div>
  );
}

function HouseCallSection() {
  const { market } = useMarket();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["chief-verdict-accuracy", market],
    queryFn: () => fetchChiefVerdictAccuracy(market),
    staleTime: 60_000,
  });

  if (isLoading) return <Skeleton className="h-44 w-full rounded-2xl" />;
  if (isError || !data) return null;

  const hitRate = data.hit_rate != null ? `${(data.hit_rate * 100).toFixed(0)}%` : "-";

  return (
    <section className="al-glass p-5 space-y-4" style={{ borderColor: "var(--al-gold)" }}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="al-eyebrow">Chief Strategist</div>
          <h2 className="mt-1 text-lg">House Call track record</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
            The desk&apos;s own auto-generated BUY / SELL / HOLD verdicts, scored against the actual one-week move.
          </p>
        </div>
        <Gavel className="size-5" aria-hidden style={{ color: "var(--al-gold)" }} />
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <MetricChip label="House calls" value={data.total} sub={`${data.buy_calls} buy · ${data.sell_calls} sell · ${data.hold_calls} hold`} />
        <MetricChip label="Matured" value={`${data.checked}/${data.total}`} sub={`${data.total - data.checked} pending`} />
        <MetricChip label="Verdict hit rate" value={hitRate} sub={`${data.correct} correct`} />
        <MetricChip label="Pending checks" value={data.total - data.checked} sub="awaiting 1-week price" />
      </div>

      {data.recent.length ? (
        <div className="space-y-2">
          {data.recent.map((record) => <HouseCallRow key={record.id} record={record} />)}
        </div>
      ) : (
        <p className="text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
          No house calls yet. Run an analyst board for a ticker and the Chief Strategist will issue and record its verdict automatically.
        </p>
      )}
    </section>
  );
}

export default function AccuracyPage() {
  const { market } = useMarket();
  const [selectedReportId, setSelectedReportId] = useState<number | null>(null);

  const stats = useQuery({ queryKey: ["accuracy"], queryFn: fetchAccuracyStats });
  const signals = useQuery({ queryKey: ["signals", { page_size: 50, market }], queryFn: () => fetchSignals({ page_size: 50, market }) });
  const reportList = useQuery({ queryKey: ["reports", { page_size: 25 }], queryFn: () => fetchReports({ page_size: 25 }) });

  const reportIds = useMemo(() => reportList.data?.items.map((report) => report.id) ?? [], [reportList.data?.items]);
  const reportDetails = useQuery({
    queryKey: ["reports", "prediction-details", reportIds],
    queryFn: () => Promise.all(reportIds.map((id) => fetchReport(id))),
    enabled: reportIds.length > 0,
  });

  const reportsWithPredictions = useMemo(
    () =>
      (reportDetails.data ?? [])
        .map((report) => ({
          ...report,
          predictions: report.predictions.filter((p) => marketForTicker(p.ticker) === market),
        }))
        .filter((report) => report.predictions.length > 0),
    [reportDetails.data, market]
  );
  const selectedReport = reportsWithPredictions.find((report) => report.id === selectedReportId) ?? reportsWithPredictions[0] ?? null;
  const activeSignals = signals.data?.items.filter((signal) => signal.status === "active") ?? [];
  const selectedStats = selectedReport ? reportAccuracy(selectedReport) : null;

  const loading = stats.isLoading || reportList.isLoading || reportDetails.isLoading;

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="al-eyebrow">Prediction Tracker</div>
          <h1 className="mt-1 text-3xl md:text-4xl">Trust Ledger</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
            Every directional call should become a trackable prediction with a price, a horizon, and a later outcome. This page is an audit trail, not a proof claim, until checks mature.
          </p>
        </div>
        <Pill variant="gold">outcome ledger</Pill>
      </header>

      {stats.isError ? (
        <ErrorState
          title="Failed to load accuracy stats"
          detail={String(stats.error)}
          onRetry={() => stats.refetch()}
        />
      ) : null}

      {stats.data && stats.data.checked === 0 && stats.data.total > 0 ? (
        <section className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900 dark:border-amber-500/25 dark:bg-amber-500/10 dark:text-amber-100">
          Predictions exist, but none have matured into verified outcomes yet. Treat this page as a tracking ledger, not proof of model accuracy, until the weekly verification job checks real price movement.
        </section>
      ) : null}

      <section className="grid gap-3 md:grid-cols-4">
        <MetricChip label="Total predictions" value={stats.data?.total ?? 0} sub="all tracked rows" />
        <MetricChip label="Matured checks" value={stats.data ? `${stats.data.checked}/${stats.data.total}` : "-"} sub={`${stats.data?.unchecked ?? 0} pending`} />
        <MetricChip label="Verified direction accuracy" value={fmtPct(stats.data?.direction_accuracy_pct)} sub={`${stats.data?.direction_correct ?? 0} correct calls`} />
        <MetricChip label="Avg abs error" value={fmtPct(stats.data?.avg_absolute_error_pct, 2)} sub="actual weekly move" />
      </section>

      {stats.data && stats.data.checked > 0 && stats.data.checked < ACCURACY_SIGNIFICANCE_MIN ? (
        <section className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900 dark:border-amber-500/25 dark:bg-amber-500/10 dark:text-amber-100">
          Only <span className="font-semibold tabular-nums">{stats.data.checked}</span> prediction
          {stats.data.checked === 1 ? " has" : "s have"} matured so far — too few to be statistically
          meaningful. With a sample this small, the accuracy figure above can swing a lot from a single call
          and should be read as an early signal, not a track record. Significance grows as the count climbs
          past ~{ACCURACY_SIGNIFICANCE_MIN}.
        </section>
      ) : null}

      <ScoringMethodology />

      {stats.data && Object.keys(stats.data.by_signal_type).length > 0 ? (
        <SignalTypeBreakdownSection byType={stats.data.by_signal_type} />
      ) : null}

      <HouseCallSection />

      {loading ? (
        <div className="space-y-4">
          <Skeleton className="h-52 w-full rounded-2xl" />
          <Skeleton className="h-72 w-full rounded-2xl" />
        </div>
      ) : (
        <>
          <AccuracyTimeline reports={reportsWithPredictions} />
          <ReportSelector reports={reportsWithPredictions} selectedId={selectedReport?.id ?? null} setSelectedId={setSelectedReportId} />

          {selectedReport ? (
            <section className="al-glass p-5 space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="al-eyebrow">Selected report</div>
                  <h2 className="mt-1 text-xl">{selectedReport.sector_name}</h2>
                  <p className="mt-1 text-sm" style={{ color: "var(--al-on-surface-muted)" }}>{fmtDate(selectedReport.created_at)}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <MetricChip label="Accuracy" value={selectedStats?.accuracy == null ? "pending" : `${selectedStats.accuracy.toFixed(1)}%`} />
                  <MetricChip label="Checked" value={selectedStats ? `${selectedStats.checked}/${selectedReport.predictions.length}` : "-"} />
                  <MetricChip label="Pending" value={selectedStats?.pending ?? 0} />
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {selectedReport.predictions.map((prediction) => <PredictionCard key={prediction.id} prediction={prediction} />)}
              </div>
            </section>
          ) : (
            <section className="al-glass p-5 text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
              No report-level predictions yet. New signal-card runs will now persist prediction rows, so this page should begin filling after the next successful analysis.
            </section>
          )}
        </>
      )}

      <section className="al-glass p-5 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="al-eyebrow">Active signal cards</div>
            <h2 className="mt-1 text-lg">Awaiting verification · {MARKET_LABELS[market].short}</h2>
          </div>
          <Target className="size-5" aria-hidden style={{ color: "var(--al-gold)" }} />
        </div>
        {activeSignals.length ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {activeSignals.slice(0, 9).map((signal) => (
              <Link key={signal.id} href={`/signals/${signal.id}`} className="rounded-xl border p-4 transition hover:-translate-y-0.5" style={{ borderColor: "var(--al-outline)" }}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-mono text-sm font-bold">{signal.ticker}</div>
                    <div className="mt-1 text-xs" style={{ color: "var(--al-on-surface-muted)" }}>{new Date(signal.created_at).toLocaleDateString()}</div>
                  </div>
                  <Pill variant={SIGNAL_VARIANT[signal.signal]}>{signal.signal.toLowerCase()}</Pill>
                </div>
                {signal.one_line ? <p className="mt-3 line-clamp-3 text-sm leading-6">{signal.one_line}</p> : null}
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-sm" style={{ color: "var(--al-on-surface-muted)" }}>No active signal cards yet.</p>
        )}
      </section>

      <AblationStudy />
    </div>
  );
}
