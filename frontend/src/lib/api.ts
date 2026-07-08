import type {
  AccuracyStats,
  AgentCreateRequest,
  AgentSummary,
  ChiefVerdict,
  ChiefVerdictAccuracy,
  PaginatedResponse,
  PipelineRun,
  Prediction,
  ReportDetail,
  ReportSummary,
  RunFanoutRequest,
  RunFanoutResponse,
  RunRequest,
  RunSectorFanoutRequest,
  RunSectorSynthesisRequest,
  RunStartResponse,
  RunSummary,
  RunSynthesisResponse,
  Sector,
  Signal,
  SignalCard,
  SignalChatRequest,
  SignalChatResponse,
  UserDetail,
  UserUpdateRequest,
  WatchlistAddRequest,
  WatchlistItem,
} from "@/types/api";

import { withLlmCreds } from "@/lib/llm-creds";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const V1 = `${BASE}/api/v1`;

/** Default per-request timeout. Long enough for normal reads, short enough to fail fast. */
const DEFAULT_TIMEOUT_MS = 45_000;

/** A typed API error so callers can branch on HTTP status or detect network/timeout (status 0). */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  constructor(status: number, detail: string, message?: string) {
    super(message ?? detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** Turn a raw HTTP failure into a calm, human sentence (no stack traces in the UI). */
function friendlyHttpMessage(status: number, body: string): string {
  const trimmed = body.trim();
  if (status === 401 || status === 403) {
    return "You're not signed in, or this action isn't permitted.";
  }
  if (status === 404) {
    return "We couldn't find that — it may have been removed or never existed.";
  }
  if (status === 429) {
    return "The analysis service is rate-limited right now. Give it a moment and try again.";
  }
  if (status >= 500) {
    return "The server hit a problem completing this request. Please try again shortly.";
  }
  // 4xx with a useful body (e.g. validation detail) — surface it, but keep it short.
  return trimmed.length > 0 && trimmed.length < 240 ? trimmed : `Request failed (${status}).`;
}

type ApiInit = RequestInit & { timeoutMs?: number };

async function apiFetch<T>(path: string, init?: ApiInit): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, signal, ...rest } = init ?? {};
  const controller = new AbortController();
  // Honour an upstream abort signal (e.g. React Query cancellation) alongside our timeout.
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", () => controller.abort(), { once: true });
  }
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${V1}${path}`, {
      ...rest,
      // Send the session cookie on every request (cross-origin :3000 → :8000).
      credentials: "include",
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(rest.headers ?? {}) },
    });
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText);
      throw new ApiError(res.status, friendlyHttpMessage(res.status, text));
    }
    // 204 No Content (e.g. DELETE) — nothing to parse.
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(0, "This took too long and was stopped. The server may be busy — try again.");
    }
    throw new ApiError(
      0,
      "Couldn't reach the analysis server. Check your connection (or that the backend is running) and try again."
    );
  } finally {
    clearTimeout(timer);
  }
}

// ── Signals ──────────────────────────────────────────────────────────────────

export interface ListSignalsParams {
  ticker?: string;
  signal?: Signal;
  signal_type?: string;
  agent_id?: number;
  market?: string;
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
  if (params.agent_id != null) qs.set("agent_id", String(params.agent_id));
  if (params.market) qs.set("market", params.market);
  if (params.page != null) qs.set("page", String(params.page));
  if (params.page_size != null) qs.set("page_size", String(params.page_size));
  const q = qs.toString();
  return apiFetch(`/signals/${q ? `?${q}` : ""}`);
}

export function fetchSignalCard(cardId: number): Promise<SignalCard> {
  return apiFetch(`/signals/${cardId}`);
}

export function fetchLatestSignal(ticker: string, agentId?: number): Promise<SignalCard> {
  const qs = agentId != null ? `?agent_id=${agentId}` : "";
  return apiFetch(`/signals/latest/${ticker}${qs}`);
}

export function fetchChiefVerdict(ticker: string): Promise<ChiefVerdict> {
  // The verdict is synthesised on demand by an LLM, so allow a generous window.
  return apiFetch(`/signals/verdict/${encodeURIComponent(ticker)}`, { timeoutMs: 120_000 });
}

export function fetchChiefVerdictAccuracy(market?: string): Promise<ChiefVerdictAccuracy> {
  const qs = market ? `?market=${encodeURIComponent(market)}` : "";
  return apiFetch(`/signals/verdicts/accuracy${qs}`);
}

// ── Watchlist ("My Favourites") ───────────────────────────────────────────────

export function fetchWatchlist(): Promise<WatchlistItem[]> {
  return apiFetch("/watchlist");
}

export function addToWatchlist(body: WatchlistAddRequest): Promise<WatchlistItem> {
  return apiFetch("/watchlist", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function removeFromWatchlist(ticker: string): Promise<void> {
  const res = await fetch(`${V1}/watchlist/${encodeURIComponent(ticker)}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${text}`);
  }
}

export function fetchAccuracyStats(): Promise<AccuracyStats> {
  return apiFetch("/signals/accuracy");
}

export function fetchSignalPredictions(cardId: number): Promise<Prediction[]> {
  return apiFetch(`/signals/${cardId}/predictions`);
}

export function askSignalEvidence(
  cardId: number,
  body: SignalChatRequest
): Promise<SignalChatResponse> {
  return apiFetch(`/signals/${cardId}/chat`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ── Reports ───────────────────────────────────────────────────────────────────

export interface ListReportsParams {
  sector_id?: string;
  market?: string;
  page?: number;
  page_size?: number;
}

export function fetchReports(
  params: ListReportsParams = {}
): Promise<PaginatedResponse<ReportSummary>> {
  const qs = new URLSearchParams();
  if (params.sector_id) qs.set("sector_id", params.sector_id);
  if (params.market) qs.set("market", params.market);
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

export function triggerRun(body: RunRequest): Promise<RunStartResponse> {
  return apiFetch("/pipeline/runs", {
    method: "POST",
    body: JSON.stringify(withLlmCreds(body)),
  });
}

export function triggerBoardRun(body: RunFanoutRequest): Promise<RunFanoutResponse> {
  return apiFetch("/pipeline/runs/fanout", {
    method: "POST",
    body: JSON.stringify(withLlmCreds(body)),
  });
}

export function triggerSectorBoardRun(body: RunSectorFanoutRequest): Promise<RunFanoutResponse[]> {
  return apiFetch("/pipeline/runs/sector-fanout", {
    method: "POST",
    body: JSON.stringify(withLlmCreds(body)),
  });
}

export function triggerSectorSynthesis(
  body: RunSectorSynthesisRequest
): Promise<RunSynthesisResponse> {
  return apiFetch("/pipeline/runs/sector-synthesis", {
    method: "POST",
    body: JSON.stringify(withLlmCreds(body)),
  });
}

// ── Agents ──────────────────────────────────────────────────────────────────

export function fetchAgents(): Promise<AgentSummary[]> {
  return apiFetch("/agents");
}

export function createAgentSkill(body: AgentCreateRequest): Promise<AgentSummary> {
  return apiFetch("/agents", {
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

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface AuthConfig {
  google_configured: boolean;
  dev_login_available: boolean;
}

/** Whether Google sign-in is wired up on the server (drives the login page UI). */
export function fetchAuthConfig(): Promise<AuthConfig> {
  return apiFetch("/auth/config");
}

/** Full-page URL that begins the Google sign-in redirect (navigate, don't fetch). */
export function googleLoginUrl(): string {
  return `${V1}/auth/login`;
}

/** Development-only: clears the signed-out marker and returns to the app. */
export function devLoginUrl(): string {
  return `${V1}/auth/dev-login`;
}

/** Revoke the current session server-side and clear the cookie. */
export function logout(): Promise<{ ok: boolean }> {
  return apiFetch("/auth/logout", { method: "POST" });
}

/** Result of the public email-only signup (request access) endpoint. */
export interface SignupResult {
  ok: boolean;
  status: "invited" | "waitlist";
  message: string;
}

/**
 * Public: submit an email to request access (the Create Account page).
 * Adds the email to the waitlist for an admin to approve. Does NOT create a
 * session — the user must sign in after approval.
 */
export function requestSignup(body: {
  email: string;
  name?: string | null;
}): Promise<SignupResult> {
  return apiFetch("/auth/signup", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ── Sectors ──────────────────────────────────────────────────────────────────

export function fetchSectors(): Promise<Sector[]> {
  return apiFetch("/sectors");
}

// ── Markets (US / HK) ─────────────────────────────────────────────────────────

export interface MarketBenchmark {
  ticker: string;
  name: string;
}

export interface MarketInfo {
  id: "us" | "hk";
  name: string;
  short_name: string;
  currency: string;
  benchmarks: MarketBenchmark[];
  quick_picks: string[];
}

export interface SectorMover {
  ticker: string;
  price: number | null;
  change_1w_pct: number | null;
  market_cap: number | null;
}

export interface SectorRead {
  id: string;
  name: string;
  instrument: {
    ticker: string;
    name: string;
    price: number | null;
    change_1w_pct: number | null;
    change_1m_pct: number | null;
  };
  cap_weighted_change_1w_pct: number | null;
  breadth: { advancers: number; decliners: number; total: number };
  constituent_count: number;
  top_movers: SectorMover[];
  bottom_movers: SectorMover[];
}

export interface MarketSectorsResponse {
  market: { id: string; name: string; currency: string };
  sectors: SectorRead[];
}

export function fetchMarkets(): Promise<MarketInfo[]> {
  return apiFetch("/markets");
}

export function fetchMarketSectors(market: string): Promise<MarketSectorsResponse> {
  return apiFetch(`/markets/sectors?market=${encodeURIComponent(market)}`);
}

export interface MarketSectorCatalogItem {
  id: string;
  name: string;
  instrument: string;
  instrument_name: string;
  constituents: string[];
}

export interface MarketSectorCatalogResponse {
  market: { id: string; name: string; currency: string };
  sectors: MarketSectorCatalogItem[];
}

/** Fast, price-free sector list for a market — drives the Stocks sector picker. */
export function fetchMarketSectorCatalog(market: string): Promise<MarketSectorCatalogResponse> {
  return apiFetch(`/markets/sector-catalog?market=${encodeURIComponent(market)}`);
}


export interface SupplyChainSummary {
  id: string;
  name: string;
  description?: string;
  market?: string;
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

export function fetchSupplyChainSectors(market?: string): Promise<SupplyChainSummary[]> {
  return apiFetch(`/supply-chain${market ? `?market=${encodeURIComponent(market)}` : ""}`);
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

export interface VectorDbCollection {
  name: string;
  count: number;
}

export interface VectorDbStats {
  total_docs: number;
  news_articles: number;
  collections: VectorDbCollection[];
}

export function fetchVectorDbStats(): Promise<VectorDbStats> {
  return apiFetch("/system/vectordb");
}

export interface ModelOption {
  id: string;
  label: string;
  provider: string;
}

export interface ModelCatalog {
  provider: string;
  default: string;
  options: ModelOption[];
}

export function fetchModelCatalog(): Promise<ModelCatalog> {
  return apiFetch("/system/models");
}

// ── Admin (operator console) ──────────────────────────────────────────────────

export interface AllowlistEntry {
  email: string;
  role: string;
  note: string | null;
  invited_by: string | null;
  created_at: string | null;
}

export interface AccessRequest {
  email: string;
  name: string | null;
  status: string;
  requested_at: string | null;
  decided_at: string | null;
  decided_by: string | null;
}

export function fetchAllowlist(): Promise<AllowlistEntry[]> {
  return apiFetch("/admin/allowlist");
}

export function addAllowlist(body: {
  email: string;
  role?: "user" | "admin";
  note?: string | null;
}): Promise<AllowlistEntry> {
  return apiFetch("/admin/allowlist", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function removeAllowlist(email: string): Promise<void> {
  return apiFetch(`/admin/allowlist/${encodeURIComponent(email)}`, {
    method: "DELETE",
  });
}

export function fetchAccessRequests(status?: string): Promise<AccessRequest[]> {
  return apiFetch(
    `/admin/access-requests${status ? `?status=${encodeURIComponent(status)}` : ""}`
  );
}

export function approveAccessRequest(email: string): Promise<AllowlistEntry> {
  return apiFetch(`/admin/access-requests/${encodeURIComponent(email)}/approve`, {
    method: "POST",
  });
}

export function denyAccessRequest(email: string): Promise<{ ok: boolean }> {
  return apiFetch(`/admin/access-requests/${encodeURIComponent(email)}/deny`, {
    method: "POST",
  });
}

export function fetchUsers(): Promise<UserDetail[]> {
  return apiFetch("/admin/users");
}

export function setUserRole(
  email: string,
  role: "user" | "admin"
): Promise<UserDetail> {
  return apiFetch(`/admin/users/${encodeURIComponent(email)}/role`, {
    method: "POST",
    body: JSON.stringify({ role }),
  });
}

export function suspendUser(email: string): Promise<UserDetail> {
  return apiFetch(`/admin/users/${encodeURIComponent(email)}/suspend`, {
    method: "POST",
  });
}

export function reactivateUser(email: string): Promise<UserDetail> {
  return apiFetch(`/admin/users/${encodeURIComponent(email)}/reactivate`, {
    method: "POST",
  });
}

// ── Evaluations ──────────────────────────────────────────────────────────────

export function fetchAblation(): Promise<Record<string, unknown>> {
  return apiFetch("/evaluations/ablation");
}

export function fetchDetailedAccuracy(): Promise<Record<string, unknown>> {
  return apiFetch("/evaluations/accuracy-detailed");
}
