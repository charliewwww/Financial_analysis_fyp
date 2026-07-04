"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import {
  AlertTriangle,
  ArrowLeft,
  BarChart3,
  CheckCircle2,
  FileText,
  Gauge,
  LineChart,
  LinkIcon,
  ShieldAlert,
  Workflow,
} from "lucide-react";

import { fetchReport } from "@/lib/api";
import { extractSignals, extractThesis, splitNamedSections } from "@/lib/parse-analysis";
import { confidenceToTen, formatScore } from "@/lib/format";
import { buildCitationResolver, linkifyCitations } from "@/lib/citations";
import type { Prediction, Signal } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { MetricChip, Pill, RingSVG, friendlyValidationStatus, type PillVariant } from "@/components/primitives";

const SIGNAL_VARIANT: Record<Signal, PillVariant> = {
  BULLISH: "green",
  BEARISH: "red",
  NEUTRAL: "gray",
};

const SECTION_ICONS: Record<string, typeof FileText> = {
  EVIDENCE: CheckCircle2,
  "KEY DEVELOPMENTS": FileText,
  "DEEP CONTEXT": Gauge,
  MACRO: BarChart3,
  "MACROECONOMIC CONTEXT": BarChart3,
  "SUPPLY CHAIN": Workflow,
  "SUPPLY CHAIN ANALYSIS": Workflow,
  "COMPANY SPOTLIGHT": LineChart,
  "RISK FACTORS": ShieldAlert,
  "RISK ASSESSMENT": ShieldAlert,
};

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtMoney(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "-";
  return `$${value.toFixed(2)}`;
}

function MarkdownBlock({ children }: { children: string }) {
  return (
    <div className="prose prose-sm max-w-none prose-headings:mt-0 prose-p:leading-7 prose-li:my-1 dark:prose-invert">
      <ReactMarkdown
        components={{
          a: ({ href, children: linkChildren, ...rest }) => {
            const url = typeof href === "string" ? href : "";
            const external = /^https?:\/\//i.test(url);
            return (
              <a
                href={url || "#source-pack"}
                {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
                className="font-medium no-underline hover:underline"
                style={{ color: "var(--al-gold)" }}
                {...rest}
              >
                {linkChildren}
              </a>
            );
          },
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}

function PredictionCard({ prediction }: { prediction: Prediction }) {
  const direction = (prediction.ai_direction ?? "NEUTRAL").toUpperCase() as Signal;
  const variant = SIGNAL_VARIANT[direction] ?? "gray";
  const result =
    prediction.prediction_correct == null
      ? { label: "pending", variant: "gray" as PillVariant }
      : prediction.prediction_correct
        ? { label: "correct", variant: "green" as PillVariant }
        : { label: "missed", variant: "red" as PillVariant };
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
          <Pill variant={variant}>{direction.toLowerCase()}</Pill>
          <Pill variant={result.variant}>{result.label}</Pill>
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
        <div className="mt-3 flex gap-2 text-xs text-amber-600 dark:text-amber-400">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span className="line-clamp-2">{prediction.ai_risk}</span>
        </div>
      ) : null}
    </article>
  );
}

function ParsedSignalCard({ signal }: { signal: ReturnType<typeof extractSignals>[number] }) {
  return (
    <article className="rounded-xl border p-4" style={{ borderColor: "var(--al-outline)" }}>
      <div className="flex items-start justify-between gap-3">
        <div className="font-mono text-lg font-bold">{signal.ticker}</div>
        <Pill variant={SIGNAL_VARIANT[signal.direction]}>{signal.direction.toLowerCase()}</Pill>
      </div>
      {signal.move ? <div className="mt-3 text-sm font-semibold">Expected move: {signal.move}</div> : null}
      {signal.reasoning ? (
        <p className="mt-3 text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
          {signal.reasoning}
        </p>
      ) : null}
      {signal.risk ? (
        <div className="mt-3 flex gap-2 text-xs text-amber-600 dark:text-amber-400">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>{signal.risk}</span>
        </div>
      ) : null}
    </article>
  );
}

function TechnicalSnapshot({ rows }: { rows: Array<Record<string, unknown>> }) {
  if (!rows.length) return null;
  const preferredKeys = ["ticker", "price", "rsi", "macd_signal", "trend", "change_1w_pct", "sma_20", "sma_50"];

  return (
    <section className="al-glass p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="al-eyebrow">Technical analysis</div>
          <h2 className="text-lg">Snapshot</h2>
        </div>
        <Pill variant="gray">{rows.length} tickers</Pill>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {rows.slice(0, 6).map((row, index) => {
          const ticker = String(row.ticker ?? row.symbol ?? `Ticker ${index + 1}`);
          return (
            <article key={`${ticker}-${index}`} className="rounded-xl border p-4" style={{ borderColor: "var(--al-outline)" }}>
              <div className="font-mono text-sm font-bold">{ticker}</div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                {preferredKeys
                  .filter((key) => key !== "ticker" && row[key] != null)
                  .slice(0, 6)
                  .map((key) => (
                    <div key={key}>
                      <div className="al-eyebrow">{key.replaceAll("_", " ")}</div>
                      <div className="mt-1 tabular-nums">{String(row[key])}</div>
                    </div>
                  ))}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export default function ReportDetailPage() {
  const { id } = useParams<{ id: string }>();
  const reportId = Number(id);

  const { data: report, isLoading, isError } = useQuery({
    queryKey: ["report", reportId],
    queryFn: () => fetchReport(reportId),
    enabled: !Number.isNaN(reportId),
  });

  const parsed = useMemo(() => {
    const analysis = report?.analysis ?? "";
    return {
      thesis: extractThesis(analysis),
      parsedSignals: extractSignals(analysis),
      sections: splitNamedSections(analysis),
    };
  }, [report?.analysis]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-52" />
        <Skeleton className="h-36 w-full rounded-2xl" />
        <Skeleton className="h-64 w-full rounded-2xl" />
      </div>
    );
  }

  if (isError || !report) {
    return <p className="text-sm text-red-500">Report not found.</p>;
  }

  const score = confidenceToTen(report.confidence_score);
  const validation = friendlyValidationStatus(report.validation_status);
  const timingSeconds = typeof report.timing_snapshot?.total_seconds === "number"
    ? report.timing_snapshot.total_seconds
    : null;
  const sections = parsed.sections.length ? parsed.sections : [{ heading: "Analysis", content: report.analysis ?? "" }];
  const resolveCitation = buildCitationResolver(report.news_snapshot ?? []);

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <Link href="/reports" className="inline-flex items-center gap-2 text-sm hover:underline" style={{ color: "var(--al-gold)" }}>
            <ArrowLeft className="size-4" aria-hidden /> Back to reports
          </Link>
          <div>
            <div className="al-eyebrow">Analysis report</div>
            <h1 className="mt-1 text-3xl md:text-4xl">{report.sector_name}</h1>
            <p className="mt-2 text-sm" style={{ color: "var(--al-on-surface-muted)" }}>
              Report #{report.id} - {fmtDate(report.created_at)}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {validation ? <Pill variant={validation.variant}>{validation.label}</Pill> : null}
          {report.status ? <Pill variant="gray">{report.status}</Pill> : null}
        </div>
      </header>

      {parsed.thesis ? (
        <section className="al-thesis-banner rounded-r-[var(--al-radius-card)]">
          <div className="al-thesis-banner-label">Thesis</div>
          <div className="al-thesis-banner-text">{parsed.thesis}</div>
        </section>
      ) : null}

      <section className="grid gap-5 lg:grid-cols-[0.82fr_1.18fr]">
        <div className="al-glass p-5 flex flex-col items-center justify-center gap-3">
          <RingSVG score={score ?? 0} max={10} size={148} />
          <div className="text-center text-sm" style={{ color: "var(--al-on-surface-muted)" }}>
            Evidence confidence on the report&apos;s native 0-10 scale.
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <MetricChip label="Evidence" value={score == null ? "-" : `${formatScore(score)}/10`} />
          <MetricChip label="Validation" value={validation?.label ?? report.validation_status ?? "pending"} />
          <MetricChip label="Articles" value={report.news_used ?? report.news_snapshot.length} />
          <MetricChip label="Prices" value={report.prices_snapshot.length} />
          <MetricChip label="Filings" value={report.filings_snapshot.length} />
          <MetricChip label="Pipeline" value={timingSeconds == null ? "-" : `${Math.round(timingSeconds)}s`} />
        </div>
      </section>

      {report.predictions.length || parsed.parsedSignals.length ? (
        <section className="al-glass p-5 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="al-eyebrow">Signal predictions</div>
              <h2 className="text-xl">One-week directional calls</h2>
            </div>
            <Pill variant="gold">{report.predictions.length || parsed.parsedSignals.length} calls</Pill>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {report.predictions.length
              ? report.predictions.map((prediction) => <PredictionCard key={prediction.id} prediction={prediction} />)
              : parsed.parsedSignals.map((signal) => <ParsedSignalCard key={signal.ticker} signal={signal} />)}
          </div>
        </section>
      ) : null}

      {report.news_summary ? (
        <section id="source-pack" className="al-glass p-5 space-y-3">
          <div className="flex items-center gap-2">
            <LinkIcon className="size-4" aria-hidden style={{ color: "var(--al-gold)" }} />
            <h2 className="text-lg">News Summary</h2>
          </div>
          <MarkdownBlock>{linkifyCitations(report.news_summary, resolveCitation)}</MarkdownBlock>
        </section>
      ) : null}

      <TechnicalSnapshot rows={report.technicals_snapshot} />

      <section className="space-y-4">
        {sections.map((section) => {
          const Icon = SECTION_ICONS[section.heading.toUpperCase()] ?? FileText;
          return (
            <article key={section.heading} className="al-glass p-5">
              <div className="mb-4 flex items-center gap-2">
                <Icon className="size-4" aria-hidden style={{ color: "var(--al-gold)" }} />
                <h2 className="text-lg">{section.heading}</h2>
              </div>
              <MarkdownBlock>{linkifyCitations(section.content, resolveCitation)}</MarkdownBlock>
            </article>
          );
        })}
      </section>

      {report.validation ? (
        <section className="al-glass p-5 space-y-3">
          <div className="flex items-center gap-2">
            <ShieldAlert className="size-4" aria-hidden style={{ color: "var(--al-gold)" }} />
            <h2 className="text-lg">Validation Notes</h2>
          </div>
          <p className="text-sm leading-7" style={{ color: "var(--al-on-surface-muted)" }}>
            {report.validation}
          </p>
        </section>
      ) : null}

      <div className="flex justify-end">
        <Link href="/reports">
          <Button variant="outline" className="rounded-full">
            <ArrowLeft data-icon="inline-start" className="size-4" aria-hidden />
            Reports
          </Button>
        </Link>
      </div>
    </div>
  );
}
