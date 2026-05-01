import type {
  AccuracyStats,
  PaginatedResponse,
  PipelineRun,
  Prediction,
  ReportDetail,
  ReportSummary,
  RunRequest,
  RunSummary,
  Sector,
  Signal,
  SignalCard,
  UserDetail,
  UserUpdateRequest,
} from "@/types/api";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const V1 = `${BASE}/api/v1`;

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${V1}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Signals ──────────────────────────────────────────────────────────────────

export interface ListSignalsParams {
  ticker?: string;
  signal?: Signal;
  signal_type?: string;
  page?: number;
  page_size?: number;
}

export function fetchSignals(
  params: ListSignalsParams = {}
): Promise<PaginatedResponse<SignalCard>> {
  const qs = new URLSearchParams();
  if (params.ticker) qs.set("ticker", params.ticker);
  if (params.signal) qs.set("signal", params.signal);
  if (params.signal_type) qs.set("signal_type", params.signal_type);
  if (params.page != null) qs.set("page", String(params.page));
  if (params.page_size != null) qs.set("page_size", String(params.page_size));
  const q = qs.toString();
  return apiFetch(`/signals/${q ? `?${q}` : ""}`);
}

export function fetchSignalCard(cardId: number): Promise<SignalCard> {
  return apiFetch(`/signals/${cardId}`);
}

export function fetchLatestSignal(ticker: string): Promise<SignalCard> {
  return apiFetch(`/signals/latest/${ticker}`);
}

export function fetchAccuracyStats(): Promise<AccuracyStats> {
  return apiFetch("/signals/accuracy");
}

export function fetchSignalPredictions(cardId: number): Promise<Prediction[]> {
  return apiFetch(`/signals/${cardId}/predictions`);
}

// ── Reports ───────────────────────────────────────────────────────────────────

export interface ListReportsParams {
  sector_id?: string;
  page?: number;
  page_size?: number;
}

export function fetchReports(
  params: ListReportsParams = {}
): Promise<PaginatedResponse<ReportSummary>> {
  const qs = new URLSearchParams();
  if (params.sector_id) qs.set("sector_id", params.sector_id);
  if (params.page != null) qs.set("page", String(params.page));
  if (params.page_size != null) qs.set("page_size", String(params.page_size));
  const q = qs.toString();
  return apiFetch(`/reports/${q ? `?${q}` : ""}`);
}

export function fetchReport(reportId: number): Promise<ReportDetail> {
  return apiFetch(`/reports/${reportId}`);
}

export function fetchReportPredictions(
  reportId: number
): Promise<Prediction[]> {
  return apiFetch(`/reports/${reportId}/predictions`);
}

// ── Pipeline ─────────────────────────────────────────────────────────────────

export interface ListRunsParams {
  ticker?: string;
  status?: string;
  page?: number;
  page_size?: number;
}

export function triggerRun(body: RunRequest): Promise<{ run_id: string }> {
  return apiFetch("/pipeline/runs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function fetchRuns(
  params: ListRunsParams = {}
): Promise<PaginatedResponse<RunSummary>> {
  const qs = new URLSearchParams();
  if (params.ticker) qs.set("ticker", params.ticker);
  if (params.status) qs.set("status", params.status);
  if (params.page != null) qs.set("page", String(params.page));
  if (params.page_size != null) qs.set("page_size", String(params.page_size));
  const q = qs.toString();
  return apiFetch(`/pipeline/runs${q ? `?${q}` : ""}`);
}

export function fetchRun(runId: string): Promise<PipelineRun> {
  return apiFetch(`/pipeline/runs/${runId}`);
}

/** Returns the full SSE URL for use with EventSource (not a fetch call). */
export function sseStreamUrl(runId: string): string {
  return `${V1}/pipeline/runs/${runId}/stream`;
}

// ── User Profile ──────────────────────────────────────────────────────────────

export function fetchMe(): Promise<UserDetail> {
  return apiFetch("/users/me");
}

export function updateMe(body: UserUpdateRequest): Promise<UserDetail> {
  return apiFetch("/users/me", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

// ── Sectors ──────────────────────────────────────────────────────────────────

export function fetchSectors(): Promise<Sector[]> {
  return apiFetch("/sectors");
}

export interface SupplyChainSummary {
  id: string;
  name: string;
  description?: string;
}

export interface SupplyChainCompany {
  ticker: string;
  name: string;
  layer?: string | null;
  products: string[];
  supplies_to: string[];
  receives_from: string[];
  revenue_segments: Record<string, { pct: number; description?: string }>;
  cost_inputs: Record<string, { pct: number; source?: string }>;
}

export interface SupplyChainFlow {
  from: string;
  to: string;
  label?: string;
  value: number;
}

export interface SupplyChainData {
  id: string;
  name: string;
  description: string;
  chain_layers: Array<{ name: string; color?: string }>;
  companies: SupplyChainCompany[];
  key_flows: SupplyChainFlow[];
}

export function fetchSupplyChainSectors(): Promise<SupplyChainSummary[]> {
  return apiFetch("/supply-chain");
}

export function fetchSupplyChain(sectorId: string): Promise<SupplyChainData> {
  return apiFetch(`/supply-chain/${sectorId}`);
}

// ── System health ────────────────────────────────────────────────────────────

export interface SystemHealth {
  llm_provider: string;
  llm_model: string;
  langgraph_ok: boolean;
  chromadb_docs: number;
  fred_key_set: boolean;
  sec_edgar_configured: boolean;
}

export function fetchSystemHealth(): Promise<SystemHealth> {
  return apiFetch("/system/health");
}

// ── Evaluations ──────────────────────────────────────────────────────────────

export function fetchAblation(): Promise<Record<string, unknown>> {
  return apiFetch("/evaluations/ablation");
}

export function fetchDetailedAccuracy(): Promise<Record<string, unknown>> {
  return apiFetch("/evaluations/accuracy-detailed");
}
