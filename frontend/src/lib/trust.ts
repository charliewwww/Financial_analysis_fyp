import type { Signal, SignalCard, SignalSource } from "@/types/api";

export type TrustState = "actionable" | "watchlist" | "insufficient_evidence" | "stale";
export type EvidenceQuality = "strong" | "medium" | "weak";
export type ConsensusSignal = Signal | "MIXED" | "NONE";

export interface ValidationSummary {
  verified: number;
  total: number;
  label: string;
  failed: boolean;
}

export interface CardTrustEvaluation {
  card: SignalCard;
  confidencePct: number | null;
  hasSummary: boolean;
  hasCatalyst: boolean;
  hasRisk: boolean;
  sourceCount: number;
  sourceDomainCount: number;
  validation: ValidationSummary;
  ageHours: number | null;
  stale: boolean;
  qualityPoints: number;
  evidenceQuality: EvidenceQuality;
  reasons: string[];
}

export interface AnalystAgreement {
  signal: ConsensusSignal;
  agreeing: number;
  total: number;
  required: number;
  detail: string;
}

export interface TickerTrustSummary {
  state: TrustState;
  stateLabel: string;
  posture: ConsensusSignal;
  recommendationAllowed: boolean;
  analystAgreement: AnalystAgreement;
  evidenceQuality: EvidenceQuality;
  evidenceScore: number;
  reasons: string[];
  checks: Array<{ label: string; passed: boolean; detail: string }>;
  latestCard: SignalCard | null;
  latestAgeHours: number | null;
}

const STALE_AFTER_HOURS = 72;
const METADATA_ONLY_RE = /^(\*\*)?(date|analyst|author|source|report|sector|role|objective)\b/i;

export function normalizeConfidenceToPct(value: number | null | undefined): number | null {
  if (value == null || Number.isNaN(value)) return null;
  const normalized = value <= 1 ? value * 100 : value * 10;
  return Math.max(0, Math.min(Math.round(normalized), 100));
}

function normalizeSourceLabel(value: string | null | undefined): string {
  return (value ?? "").trim().replace(/^www\./i, "");
}

function publisherFromTitle(title: string | null | undefined): string {
  const value = title ?? "";
  const [headline, publisher] = value.split(/\s+-\s+(?=[^-]+$)/);
  if (!headline || !publisher || publisher.length > 60) return "";
  return publisher.trim();
}

export function sourceIdentity(source: SignalSource): string {
  const domain = normalizeSourceLabel(source.domain);
  if (domain && !domain.includes("news.google.com") && !domain.includes("google.com")) return domain;
  return normalizeSourceLabel(publisherFromTitle(source.title)) || domain || normalizeSourceLabel(source.title) || normalizeSourceLabel(source.url);
}

export function isMeaningfulText(value: string | null | undefined): boolean {
  if (!value) return false;
  const cleaned = value
    .replace(/[*_`#>]/g, "")
    .replace(/\s+/g, " ")
    .trim();
  if (cleaned.length < 18) return false;
  if (METADATA_ONLY_RE.test(cleaned)) return false;
  return /[a-zA-Z]{4,}/.test(cleaned);
}

export function validationSummary(card: SignalCard): ValidationSummary {
  const claims = card.numerical_claims ?? [];
  const claimTotal = claims.length;
  const claimVerified = claims.filter((claim) => claim.verified).length;
  const raw = card.validation_score ?? "";
  const failed = raw.toUpperCase().includes("FAILED");

  if (claimTotal > 0) {
    return {
      verified: claimVerified,
      total: claimTotal,
      label: `${claimVerified}/${claimTotal} claims verified`,
      failed,
    };
  }

  const parsed = raw.match(/(\d+)\s*\/\s*(\d+)/);
  if (parsed) {
    const verified = Number(parsed[1]);
    const total = Number(parsed[2]);
    return {
      verified,
      total,
      label: `${verified}/${total} claims verified`,
      failed,
    };
  }

  return {
    verified: 0,
    total: 0,
    label: raw || "No claim validation yet",
    failed,
  };
}

function hoursSince(iso: string, now: Date): number | null {
  const timestamp = new Date(iso).getTime();
  if (Number.isNaN(timestamp)) return null;
  return Math.max(0, (now.getTime() - timestamp) / 36e5);
}

function qualityFromPoints(points: number): EvidenceQuality {
  if (points >= 5) return "strong";
  if (points >= 3) return "medium";
  return "weak";
}

export function evaluateSignalCard(
  card: SignalCard,
  now: Date = new Date()
): CardTrustEvaluation {
  const confidencePct = normalizeConfidenceToPct(card.confidence);
  const hasSummary = isMeaningfulText(card.one_line);
  const hasCatalyst = isMeaningfulText(card.key_catalyst);
  const hasRisk = isMeaningfulText(card.key_risk);
  const sourceCount = (card.sources ?? []).filter(
    (source) => Boolean(source.url || source.title || source.domain)
  ).length;
  const sourceDomainCount = new Set((card.sources ?? []).map(sourceIdentity).filter(Boolean)).size;
  const validation = validationSummary(card);
  const ageHours = hoursSince(card.created_at, now);
  const stale = ageHours != null && ageHours > STALE_AFTER_HOURS;
  const validationHealthy = !validation.failed && validation.total > 0 && validation.verified >= Math.ceil(validation.total * 0.5);

  let qualityPoints = 0;
  if (hasSummary) qualityPoints += 1;
  if (hasCatalyst) qualityPoints += 1;
  if (hasRisk) qualityPoints += 1;
  if (sourceCount > 0) qualityPoints += 1;
  if (validationHealthy) qualityPoints += 1;
  if ((confidencePct ?? 0) >= 70) qualityPoints += 1;
  if (!stale) qualityPoints += 1;
  if (!hasSummary || !hasCatalyst || !hasRisk || sourceCount === 0) {
    qualityPoints = Math.min(qualityPoints, 2);
  }
  if (validation.failed) qualityPoints = Math.min(qualityPoints, 2);

  const reasons: string[] = [];
  if (!hasSummary) reasons.push("summary is not investor-readable");
  if (!hasCatalyst) reasons.push("catalyst missing");
  if (!hasRisk) reasons.push("risk missing");
  if (sourceCount === 0) reasons.push("no sources attached");
  if (validation.failed) reasons.push("validation failed");
  else if (validation.total === 0) reasons.push("claims not yet validated");
  else if (!validationHealthy) reasons.push("claim validation is weak");
  if (stale) reasons.push("signal is stale");

  return {
    card,
    confidencePct,
    hasSummary,
    hasCatalyst,
    hasRisk,
    sourceCount,
    sourceDomainCount,
    validation,
    ageHours,
    stale,
    qualityPoints,
    evidenceQuality: qualityFromPoints(qualityPoints),
    reasons,
  };
}

function labelForConsensus(signal: ConsensusSignal): string {
  if (signal === "NONE") return "Awaiting signals";
  if (signal === "MIXED") return "Mixed board";
  return signal.toLowerCase();
}

export function analystAgreement(cards: SignalCard[], totalAnalysts: number): AnalystAgreement {
  const total = cards.length;
  const required = Math.max(2, Math.ceil(Math.max(totalAnalysts, total) * 0.75));

  if (total === 0) {
    return {
      signal: "NONE",
      agreeing: 0,
      total: totalAnalysts,
      required,
      detail: "No analyst has published a current card.",
    };
  }

  const counts: Record<Signal, number> = { BULLISH: 0, BEARISH: 0, NEUTRAL: 0 };
  for (const card of cards) counts[card.signal] += 1;

  const ordered = (Object.keys(counts) as Signal[]).sort((a, b) => counts[b] - counts[a]);
  const winner = ordered[0];
  const agreeing = counts[winner];
  const tied = counts[ordered[0]] === counts[ordered[1]];
  const clearSignal = !tied && agreeing >= required ? winner : "MIXED";

  return {
    signal: clearSignal,
    agreeing,
    total: totalAnalysts,
    required,
    detail:
      clearSignal === "MIXED"
        ? `${agreeing}/${totalAnalysts} analysts align; ${required}/${totalAnalysts} required for a directional call.`
        : `${agreeing}/${totalAnalysts} analysts support ${winner.toLowerCase()}.`,
  };
}

export function buildTickerTrustSummary(
  cards: SignalCard[],
  totalAnalysts: number,
  now: Date = new Date()
): TickerTrustSummary {
  const evaluations = cards.map((card) => evaluateSignalCard(card, now));
  const agreement = analystAgreement(cards, totalAnalysts);
  const latestCard = [...cards].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )[0] ?? null;
  const latestAgeHours = latestCard ? hoursSince(latestCard.created_at, now) : null;
  const latestIsStale = latestAgeHours != null && latestAgeHours > STALE_AFTER_HOURS;
  const averagePoints = evaluations.length
    ? evaluations.reduce((sum, item) => sum + item.qualityPoints, 0) / evaluations.length
    : 0;
  const evidenceScore = Math.round((averagePoints / 7) * 100);
  const evidenceQuality = qualityFromPoints(Math.round(averagePoints));
  const coverageComplete = cards.length >= totalAnalysts && totalAnalysts > 0;
  const completeEvidenceCount = evaluations.filter(
    (item) => item.hasSummary && item.hasCatalyst && item.hasRisk && item.sourceCount > 0
  ).length;
  const hasCoreEvidence = completeEvidenceCount === cards.length && cards.length > 0;
  const validationFailed = evaluations.some((item) => item.validation.failed);
  const hasValidationChecks = evaluations.some((item) => item.validation.total > 0);
  const recommendationAllowed =
    agreement.signal !== "MIXED" &&
    agreement.signal !== "NONE" &&
    coverageComplete &&
    evidenceQuality === "strong" &&
    hasCoreEvidence &&
    hasValidationChecks &&
    !latestIsStale &&
    !validationFailed;

  let state: TrustState = "watchlist";
  if (cards.length === 0) state = "insufficient_evidence";
  else if (latestIsStale) state = "stale";
  else if (!hasCoreEvidence || validationFailed) state = "insufficient_evidence";
  else if (recommendationAllowed) state = "actionable";

  const reasons: string[] = [];
  if (cards.length === 0) reasons.push("Run the analyst board to create the first evidence set.");
  if (!coverageComplete && cards.length > 0) reasons.push(`Only ${cards.length}/${totalAnalysts} analyst lanes have cards.`);
  if (agreement.signal === "MIXED") reasons.push("The analyst board is split, so this should remain decision support.");
  if (!hasCoreEvidence && cards.length > 0) reasons.push(`${completeEvidenceCount}/${cards.length} analyst cards include thesis, catalyst, risk, and sources.`);
  if (!hasValidationChecks && cards.length > 0) reasons.push("No numerical claim checks are attached yet.");
  if (validationFailed) reasons.push("One or more analyst cards failed validation.");
  if (latestIsStale) reasons.push("Latest signal is older than three market days; rerun before acting.");
  if (!reasons.length) reasons.push("Evidence is fresh, sourced, and directionally aligned.");

  const checks = [
    {
      label: "Analyst agreement",
      passed: agreement.signal !== "MIXED" && agreement.signal !== "NONE",
      detail: agreement.detail,
    },
    {
      label: "Coverage",
      passed: coverageComplete,
      detail: `${cards.length}/${totalAnalysts} analyst lanes populated`,
    },
    {
      label: "Evidence completeness",
      passed: hasCoreEvidence,
      detail: hasCoreEvidence
        ? "Every analyst card includes thesis, catalyst, risk, and sources"
        : cards.length > 0
          ? `${completeEvidenceCount}/${cards.length} cards include thesis, catalyst, risk, and sources`
          : "No analyst cards are available yet",
    },
    {
      label: "Freshness",
      passed: !latestIsStale && latestCard != null,
      detail: latestAgeHours == null ? "No timestamp available" : `${Math.round(latestAgeHours)}h since latest card`,
    },
    {
      label: "Validation",
      passed: !validationFailed && hasValidationChecks,
      detail: validationFailed
        ? "Validation failed"
        : hasValidationChecks
          ? "Numerical claim checks are attached with no failed validation flags"
          : "No numerical claim checks are attached yet",
    },
  ];

  const stateLabel: Record<TrustState, string> = {
    actionable: "Actionable",
    watchlist: "Watchlist",
    insufficient_evidence: "Insufficient evidence",
    stale: "Stale",
  };

  return {
    state,
    stateLabel: stateLabel[state],
    posture: agreement.signal,
    recommendationAllowed,
    analystAgreement: agreement,
    evidenceQuality,
    evidenceScore,
    reasons,
    checks,
    latestCard,
    latestAgeHours,
  };
}

export function consensusLabel(signal: ConsensusSignal): string {
  return labelForConsensus(signal);
}