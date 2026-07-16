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
  LinkIcon,
  Newspaper,
  ShieldAlert,
  TrendingDown,
  TrendingUp,
  Workflow,
} from "lucide-react";

import { fetchSignalCard, fetchSignalPredictions } from "@/lib/api";
import { extractThesis, splitNamedSections } from "@/lib/parse-analysis";
import { confidenceToTen, formatScore } from "@/lib/format";
import { buildCitationResolver, linkifyCitations } from "@/lib/citations";
import { sourceIdentity } from "@/lib/trust";
import {
  computeTokenUsage,
  formatCostUsd,
  formatTokens,
  hasTokenUsage,
} from "@/lib/token-cost";
import type { Prediction, Signal, SignalCard } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  MetricChip,
  Pill,
  RingSVG,
  friendlyValidationStatus,
  type PillVariant,
} from "@/components/primitives";

const SIGNAL_VARIANT: Record<Signal, PillVariant> = {
  BULLISH: "green",
  BEARISH: "red",
  NEUTRAL: "gray",
};

const SIGNAL_TYPE_LABELS: Record<string, string> = {
  FUNDAMENTAL_SHIFT: "Fundamental shift",
  MEDIA_NARRATIVE: "Media narrative",
  TECHNICAL_ONLY: "Technical only",
};

const SECTION_ICONS: Record<string, typeof FileText> = {
  EVIDENCE: CheckCircle2,
  CATALYST: TrendingUp,
  "KEY CATALYST": TrendingUp,
  "KEY DEVELOPMENTS": Newspaper,
  "RISK FACTORS": ShieldAlert,
  "RISK ASSESSMENT": ShieldAlert,
  "SUPPLY CHAIN": Workflow,
  "SUPPLY CHAIN ANALYSIS": Workflow,
  "TECHNICAL ANALYSIS": BarChart3,
  MACRO: Gauge,
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

function ageLabel(iso: string | null | undefined): string {
  if (!iso) return "-";
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return "-";
  const hours = Math.max(0, (Date.now() - ts) / 36e5);
  if (hours < 1) return "fresh";
  if (hours < 48) return `${Math.round(hours)}h old`;
  return `${Math.round(hours / 24)}d old`;
}

function fmtMoney(value: unknown): string {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "-";
  return `$${n.toFixed(2)}`;
}

function asText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

/**
 * Build a citation resolver from the card's source pack (article evidence +
 * sources) so inline [SOURCE: ...] markers link to the real article.
 */
function resolverForCard(card: SignalCard) {
  const entries = [
    ...(card.article_evidence ?? []).map((a) => ({
      title: a.title,
      url: a.link ?? a.url,
      source: a.source,
      domain: a.domain,
    })),
    ...(card.sources ?? []).map((s) => ({ title: s.title, url: s.url, domain: s.domain })),
  ];
  return buildCitationResolver(entries);
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

function SignalIcon({ signal }: { signal: Signal }) {
  if (signal === "BULLISH") return <TrendingUp className="size-4" aria-hidden />;
  if (signal === "BEARISH") return <TrendingDown className="size-4" aria-hidden />;
  return <Gauge className="size-4" aria-hidden />;
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

  return (
    <article className="rounded-xl border p-4" style={{ borderColor: "var(--al-outline)" }}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-mono text-lg font-bold">{prediction.ticker}</div>
          <div className="mt-1 text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
            {fmtMoney(prediction.price_at_report)} at signal
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
      {prediction.ai_reasoning ? (
        <p className="mt-3 text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
          {prediction.ai_reasoning}
        </p>
      ) : null}
      {prediction.ai_risk ? (
        <div className="mt-3 flex gap-2 text-xs text-amber-600 dark:text-amber-400">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>{prediction.ai_risk}</span>
        </div>
      ) : null}
    </article>
  );
}

function EvidenceCallouts({ card }: { card: SignalCard }) {
  const items = [
    { label: "Primary catalyst", value: card.key_catalyst, icon: TrendingUp },
    { label: "Invalidation risk", value: card.key_risk, icon: ShieldAlert },
  ].filter((item) => asText(item.value));

  if (!items.length && !(card.supply_chain_impact?.length)) return null;

  return (
    <section className="grid gap-4 lg:grid-cols-3">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <article key={item.label} className="al-glass p-5">
            <div className="flex items-center gap-2">
              <Icon className="size-4" aria-hidden style={{ color: "var(--al-gold)" }} />
              <div className="al-eyebrow">{item.label}</div>
            </div>
            <p className="mt-3 text-sm leading-7">{item.value}</p>
          </article>
        );
      })}

      {card.supply_chain_impact?.length ? (
        <article className="al-glass p-5">
          <div className="flex items-center gap-2">
            <Workflow className="size-4" aria-hidden style={{ color: "var(--al-gold)" }} />
            <div className="al-eyebrow">Supply-chain ripple</div>
          </div>
          <div className="mt-4 space-y-3">
            {card.supply_chain_impact.slice(0, 4).map((item) => (
              <div key={`${item.ticker}-${item.direction}`} className="flex gap-3 text-sm leading-6">
                <span className="font-mono font-bold">{item.direction} {item.ticker}</span>
                <span style={{ color: "var(--al-on-surface-muted)" }}>{item.reason}</span>
              </div>
            ))}
          </div>
        </article>
      ) : null}
    </section>
  );
}

function ClaimLedger({ card }: { card: SignalCard }) {
  const claims = card.numerical_claims ?? [];
  if (!claims.length) return null;

  return (
    <section className="al-glass p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="al-eyebrow">Validation ledger</div>
          <h2 className="text-lg">Numerical claims</h2>
        </div>
        <Pill variant="gray">{claims.length} claims</Pill>
      </div>
      <div className="space-y-3">
        {claims.map((claim, index) => (
          <div key={`${claim.claim}-${index}`} className="grid gap-2 rounded-xl border p-3 sm:grid-cols-[24px_1fr]" style={{ borderColor: "var(--al-outline)" }}>
            {claim.verified ? (
              <CheckCircle2 className="mt-0.5 size-4 text-emerald-500" aria-hidden />
            ) : (
              <AlertTriangle className="mt-0.5 size-4 text-amber-500" aria-hidden />
            )}
            <div className="text-sm leading-6">
              <div>{claim.claim}</div>
              {claim.source ? <div className="text-xs" style={{ color: "var(--al-on-surface-muted)" }}>{claim.source}</div> : null}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function SnapshotTable({ title, rows, keys }: { title: string; rows: Array<Record<string, unknown>>; keys: string[] }) {
  if (!rows.length) return null;

  return (
    <section className="al-glass p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="al-eyebrow">Market snapshot</div>
          <h2 className="text-lg">{title}</h2>
        </div>
        <Pill variant="gray">{rows.length} rows</Pill>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {rows.slice(0, 6).map((row, index) => {
          const ticker = asText(row.ticker) || asText(row.symbol) || `Item ${index + 1}`;
          return (
            <article key={`${title}-${ticker}-${index}`} className="rounded-xl border p-4" style={{ borderColor: "var(--al-outline)" }}>
              <div className="font-mono text-sm font-bold">{ticker}</div>
              <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
                {keys
                  .filter((key) => key !== "ticker" && row[key] != null && row[key] !== "")
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

function ArticleEvidence({ card }: { card: SignalCard }) {
  const articles = card.article_evidence ?? [];
  const sources = card.sources ?? [];
  const hasArticles = articles.length > 0;
  if (!hasArticles && !sources.length) return null;

  return (
    <section id="source-pack" className="al-glass p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="al-eyebrow">Source pack</div>
          <h2 className="text-lg">News and provenance</h2>
        </div>
        <Pill variant="gold">{hasArticles ? articles.length : sources.length} sources</Pill>
      </div>

      {card.news_summary ? <MarkdownBlock>{card.news_summary}</MarkdownBlock> : null}

      <div className="grid gap-3 md:grid-cols-2">
        {hasArticles
          ? articles.slice(0, 8).map((article, index) => {
              const title = asText(article.title) || `Source ${index + 1}`;
              const link = asText(article.link) || asText(article.url);
              const source = asText(article.source) || asText(article.domain);
              const summary = asText(article.condensed_summary) || asText(article.raw_summary);
              return (
                <article key={`${title}-${index}`} className="rounded-xl border p-4" style={{ borderColor: "var(--al-outline)" }}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="text-sm font-semibold leading-6">{title}</h3>
                      {source ? <p className="mt-1 text-xs" style={{ color: "var(--al-on-surface-muted)" }}>{source}</p> : null}
                    </div>
                    {link ? (
                      <a href={link} target="_blank" rel="noopener noreferrer" className="shrink-0" style={{ color: "var(--al-gold)" }} aria-label={`Open ${title}`}>
                        <LinkIcon className="size-4" aria-hidden />
                      </a>
                    ) : null}
                  </div>
                  {summary ? <p className="mt-3 line-clamp-4 text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>{summary}</p> : null}
                </article>
              );
            })
          : sources.slice(0, 8).map((source, index) => (
              <article key={`${source.url}-${index}`} className="rounded-xl border p-4" style={{ borderColor: "var(--al-outline)" }}>
                <h3 className="text-sm font-semibold leading-6">{source.title || source.domain || `Source ${index + 1}`}</h3>
                {source.domain ? <p className="mt-1 text-xs" style={{ color: "var(--al-on-surface-muted)" }}>{source.domain}</p> : null}
                {source.summary ? <p className="mt-3 line-clamp-4 text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>{source.summary}</p> : null}
                {source.url ? (
                  <a href={source.url} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex items-center gap-2 text-sm font-semibold hover:underline" style={{ color: "var(--al-gold)" }}>
                    <LinkIcon className="size-4" aria-hidden /> Open source
                  </a>
                ) : null}
              </article>
            ))}
      </div>
    </section>
  );
}

export default function SignalDetailPage() {
  const { id } = useParams<{ id: string }>();
  const cardId = Number(id);

  const { data: card, isLoading, isError } = useQuery({
    queryKey: ["signal", cardId],
    queryFn: () => fetchSignalCard(cardId),
    enabled: !Number.isNaN(cardId),
  });

  const { data: predictions } = useQuery({
    queryKey: ["signal-predictions", cardId],
    queryFn: () => fetchSignalPredictions(cardId),
    enabled: !Number.isNaN(cardId),
  });

  const parsed = useMemo(() => {
    const analysis = card?.analysis_text?.trim() ?? "";
    return {
      analysis,
      thesis: extractThesis(analysis) || card?.one_line || "",
      sections: splitNamedSections(analysis),
    };
  }, [card?.analysis_text, card?.one_line]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-52" />
        <Skeleton className="h-36 w-full rounded-2xl" />
        <Skeleton className="h-64 w-full rounded-2xl" />
      </div>
    );
  }

  if (isError || !card) {
    return <p className="text-sm text-red-500">Signal card not found.</p>;
  }

  const score = confidenceToTen(card.confidence);
  const validation = friendlyValidationStatus(card.validation_score);
  const sections = parsed.sections.length
    ? parsed.sections
    : parsed.analysis
      ? [{ heading: "Analysis", content: parsed.analysis }]
      : [];
  const sourceCount = card.sources?.length ?? 0;
  const publisherCount = new Set((card.sources ?? []).map(sourceIdentity).filter(Boolean)).size;
  const technicalRows = card.technical_snapshot ?? [];
  const priceRows = card.price_snapshot ?? [];
  const resolveCitation = resolverForCard(card);
  const tokenUsage = computeTokenUsage(card);

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <Link href="/tickers" className="inline-flex items-center gap-2 text-sm hover:underline" style={{ color: "var(--al-gold)" }}>
            <ArrowLeft className="size-4" aria-hidden /> Back to Decision Desk
          </Link>
          <div>
            <div className="al-eyebrow">Analyst evidence</div>
            <h1 className="mt-1 text-3xl md:text-4xl">{card.ticker}</h1>
            <p className="mt-2 text-sm" style={{ color: "var(--al-on-surface-muted)" }}>
              Signal card #{card.id} - {fmtDate(card.created_at)}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Pill variant={SIGNAL_VARIANT[card.signal]}><SignalIcon signal={card.signal} />{card.signal.toLowerCase()}</Pill>
          {validation ? <Pill variant={validation.variant}>{validation.label}</Pill> : null}
          {card.status ? <Pill variant="gray">{card.status}</Pill> : null}
        </div>
      </header>

      {parsed.thesis ? (
        <section className="al-thesis-banner rounded-r-[var(--al-radius-card)]">
          <div className="al-thesis-banner-label">Thesis</div>
          <div className="al-thesis-banner-text">{parsed.thesis}</div>
        </section>
      ) : null}

      <section className="grid gap-5 lg:grid-cols-[0.82fr_1.18fr]">
        <div className="al-glass flex flex-col items-center justify-center gap-3 p-5">
          <RingSVG score={score ?? 0} max={10} size={148} />
          <div className="text-center text-sm" style={{ color: "var(--al-on-surface-muted)" }}>
            Evidence score on the analyst card scale.
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <MetricChip label="Signal" value={card.signal.toLowerCase()} hint="The analyst's directional read for this name — e.g. bullish, bearish or neutral. It reflects the evidence in this card, not a buy/sell instruction." />
          <MetricChip label="Conviction" value={card.conviction_stated === false ? "not stated" : card.conviction == null ? "-" : `${card.conviction}/5`} hint="How strongly the analyst holds this view, from 1 (tentative) to 5 (high). 'Not stated' means the model did not express an explicit conviction, so a neutral default is used. Conviction does not measure how likely the view is to be right." />
          {card.signal_type ? (
            <MetricChip label="Signal type" value={SIGNAL_TYPE_LABELS[card.signal_type] ?? card.signal_type} hint="What kind of evidence drives this signal: a fundamental shift (filings, earnings, guidance), a media narrative (news flow and sentiment) or a technical-only setup (price and indicators, with little fresh fundamental news)." />
          ) : null}
          <MetricChip label="Evidence score" value={score == null ? "-" : `${formatScore(score)}/10`} hint="How well the claims in this card are backed by sources and surviving validation, from 0 to 10. Higher means better-supported reasoning." />
          <MetricChip label="Validation" value={validation?.label ?? card.validation_score ?? "pending"} hint="Whether the card's numeric claims were cross-checked against the underlying data and held up. 'Pending' means the check has not finished." />
          <MetricChip label="Freshness" value={ageLabel(card.created_at)} sub={fmtDate(card.created_at)} hint="How recently this analysis was produced. Older reads may not reflect the latest news or prices." />
          <MetricChip label="Articles" value={sourceCount || card.article_evidence?.length || 0} sub={publisherCount ? `${publisherCount} publishers` : undefined} hint="How many news articles fed this analysis, and from how many distinct publishers — more independent sources means less single-source bias." />
          {card.rag_metadata && (card.rag_metadata.total_results ?? 0) > 0 ? (
            <MetricChip
              label="Historical context"
              hint="How many documents from earlier runs (news, filings and this desk's own prior analyses) were retrieved to inform this read, so the analyst can reason about how the story has changed over time."
              value={`${card.rag_metadata.total_results} prior docs`}
              sub={[
                card.rag_metadata.news_hits ? `${card.rag_metadata.news_hits} news` : null,
                card.rag_metadata.filing_hits ? `${card.rag_metadata.filing_hits} filings` : null,
                card.rag_metadata.analysis_hits ? `${card.rag_metadata.analysis_hits} prior analyses` : null,
              ]
                .filter(Boolean)
                .join(" · ") || undefined}
            />
          ) : null}
          {hasTokenUsage(tokenUsage) ? (
            <>
              <MetricChip
                label="Token usage"
                value={`${formatTokens(tokenUsage.totalTokens)} tokens`}
                sub={`${formatTokens(tokenUsage.promptTokens)} in · ${formatTokens(tokenUsage.completionTokens)} out`}
                hint="How many tokens this run sent to the model (input) and got back (output), summed across every pipeline step. Tokens are the unit LLM providers bill on, so this is what drives the run's cost."
              />
              <MetricChip
                label="Est. cost"
                value={formatCostUsd(tokenUsage.estimatedCostUsd)}
                sub={tokenUsage.model ? tokenUsage.model : undefined}
                hint={
                  tokenUsage.estimatedCostUsd == null
                    ? "This model isn't in our price table (or it's self-hosted), so only token counts are shown. If you use your own API key, check your provider's dashboard for the exact charge."
                    : "A rough estimate of what this run cost, based on the model's published input/output token rates. Actual billing depends on your provider, caching and current prices — treat this as a guide, not an invoice."
                }
              />
            </>
          ) : null}
        </div>
      </section>

      {card.rag_metadata && (card.rag_metadata.total_results ?? 0) > 0 ? (
        <p className="flex items-start gap-2 text-xs leading-5" style={{ color: "var(--al-on-surface-muted)" }}>
          <Workflow className="mt-0.5 size-3.5 shrink-0" style={{ color: "var(--al-gold)" }} aria-hidden />
          <span>
            This read was informed by{" "}
            <span className="font-semibold text-foreground">{card.rag_metadata.total_results}</span> document
            {card.rag_metadata.total_results === 1 ? "" : "s"} retrieved from earlier runs (news, filings and
            this desk&apos;s own prior analyses), so the analyst can reason about how the story has changed over
            time — not just today&apos;s snapshot.
          </span>
        </p>
      ) : null}

      <EvidenceCallouts card={card} />

      {predictions && predictions.length > 0 ? (
        <section className="al-glass p-5 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="al-eyebrow">Signal predictions</div>
              <h2 className="text-xl">One-week directional calls</h2>
            </div>
            <Pill variant="gold">{predictions.length} calls</Pill>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {predictions.map((prediction) => <PredictionCard key={prediction.id} prediction={prediction} />)}
          </div>
        </section>
      ) : null}

      {card.sufficiency_reasoning || card.data_sufficiency ? (
        <section className="al-glass p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Gauge className="size-4" aria-hidden style={{ color: "var(--al-gold)" }} />
            <h2 className="text-lg">Data Quality</h2>
          </div>
          {card.data_sufficiency ? <Pill variant="gray">{card.data_sufficiency}</Pill> : null}
          {card.sufficiency_reasoning ? (
            <p className="text-sm leading-7" style={{ color: "var(--al-on-surface-muted)" }}>{card.sufficiency_reasoning}</p>
          ) : null}
        </section>
      ) : null}

      <ArticleEvidence card={card} />
      <ClaimLedger card={card} />
      <SnapshotTable title="Price action" rows={priceRows} keys={["ticker", "price", "change_1d_pct", "change_1w_pct", "volume", "market_cap"]} />
      <SnapshotTable title="Technical setup" rows={technicalRows} keys={["ticker", "price", "rsi", "macd_signal", "trend", "change_1w_pct", "sma_20", "sma_50"]} />

      {sections.length ? (
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
      ) : (
        <section className="al-glass p-5 space-y-3">
          <div className="flex items-center gap-2">
            <FileText className="size-4" aria-hidden style={{ color: "var(--al-gold)" }} />
            <h2 className="text-lg">Analysis</h2>
          </div>
          <p className="text-sm leading-7" style={{ color: "var(--al-on-surface-muted)" }}>
            This older card only contains the compact signal fields. Run the analyst board again to attach the full evidence archive.
          </p>
        </section>
      )}

      <div className="flex justify-end">
        <Link href="/tickers">
          <Button variant="outline" className="rounded-full">
            <ArrowLeft data-icon="inline-start" className="size-4" aria-hidden />
            Decision Desk
          </Button>
        </Link>
      </div>
    </div>
  );
}
