// TypeScript types mirroring the FastAPI backend schemas exactly.
// Keep in sync with backend/app/schemas/*.py

// ── Common ──────────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ── Analysis / Signal Cards ──────────────────────────────────────────────────

export type Signal = "BULLISH" | "BEARISH" | "NEUTRAL";
export type Direction = "▲" | "▼" | "◆";

export interface NumericalClaim {
  claim: string;
  verified: boolean;
  source: string;
}

export interface SupplyChainImpact {
  ticker: string;
  direction: Direction;
  reason: string;
}

export interface SignalSource {
  url: string;
  title: string;
  domain: string;
  summary?: string;
}

export interface SignalCard {
  id: number;
  ticker: string;
  run_id: string | null;
  agent_id: number | null;
  signal: Signal;
  conviction: number | null;
  one_line: string | null;
  key_catalyst: string | null;
  key_risk: string | null;
  confidence: number | null;
  signal_type: string | null;
  conviction_stated: boolean;
  validation_score: string | null;
  supply_chain_impact: SupplyChainImpact[] | null;
  sources: SignalSource[] | null;
  numerical_claims: NumericalClaim[] | null;
  sector_context: string | null;
  analysis_text?: string;
  news_summary?: string;
  data_sufficiency?: string;
  sufficiency_reasoning?: string;
  anomaly_alerts?: Array<Record<string, unknown>>;
  article_evidence?: Array<Record<string, unknown>>;
  price_snapshot?: Array<Record<string, unknown>>;
  technical_snapshot?: Array<Record<string, unknown>>;
  reasoning_scores?: Record<string, unknown>;
  confidence_breakdown?: Record<string, unknown>;
  rag_metadata?: RagMetadata;
  created_at: string;
  status: string;
}

export interface RagMetadata {
  total_results?: number;
  query_time_seconds?: number;
  news_hits?: number;
  filing_hits?: number;
  analysis_hits?: number;
}

export interface SignalChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface SignalChatRequest {
  question: string;
  history?: SignalChatTurn[];
  context?: string | null;
}

export interface SignalChatCitation {
  label: string;
  source_type: "source" | "claim" | "supply_chain" | "snapshot" | "analysis" | "decision";
  source: string;
  url?: string | null;
  quote: string;
}

export interface SignalChatResponse {
  answer: string;
  citations: SignalChatCitation[];
  limitations: string[];
  grounded: boolean;
  suggested_questions: string[];
}

export interface ChiefVerdictAnalystView {
  agent_id: number | null;
  agent_name: string;
  signal: string;
  conviction: number;
  one_line: string;
}

export interface ChiefVerdict {
  ticker: string;
  action: "BUY" | "SELL" | "HOLD";
  conviction: number;
  deciding_reason: string;
  summary: string;
  agreement: "aligned" | "mixed" | "split";
  dissent: string;
  risk_assessment: string;
  analysts: ChiefVerdictAnalystView[];
  generated_at: string;
}

export interface ChiefVerdictRecord {
  id: number;
  ticker: string;
  run_id: string | null;
  action: string;
  conviction: number | null;
  deciding_reason: string;
  summary: string;
  agreement: string;
  dissent: string;
  risk_assessment: string;
  analyst_count: number;
  price_at_verdict: number | null;
  price_1w_later: number | null;
  actual_change_1w: number | null;
  checked_at: string | null;
  verdict_correct: boolean | null;
  created_at: string;
}

export interface ChiefVerdictAccuracy {
  total: number;
  checked: number;
  correct: number;
  hit_rate: number | null;
  buy_calls: number;
  sell_calls: number;
  hold_calls: number;
  recent: ChiefVerdictRecord[];
}

export interface WatchlistItem {
  id: number;
  ticker: string;
  notes: string | null;
  sector_id: string | null;
  added_at: string;
}

export interface WatchlistAddRequest {
  ticker: string;
  notes?: string | null;
  sector_id?: string | null;
}

export interface NodeExecution {
  node?: string;
  node_name?: string;
  label?: string | null;
  status: "running" | "completed" | "failed" | "skipped";
  started_at: string | null;
  finished_at: string | null;
  duration_seconds?: number;
  error: string | null;
  input_keys?: string[];
  output_keys?: string[];
  llm_model?: string | null;
  llm_prompt_tokens?: number;
  llm_completion_tokens?: number;
  decision?: string | null;
  decision_reason?: string | null;
}

// ── Pipeline Runs ────────────────────────────────────────────────────────────

export type RunStatus = "pending" | "running" | "completed" | "failed";
export type SSEEventType =
  | "node_started"
  | "node_completed"
  | "pipeline_completed"
  | "pipeline_failed"
  | "heartbeat";

export interface PipelineRun {
  run_id: string;
  ticker: string;
  sector_id: string;
  agent_id?: number | null;
  agent_name?: string | null;
  status: RunStatus;
  current_node: string | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  signal_card_id: number | null;
  node_executions: NodeExecution[];
}

export interface RunSummary {
  run_id: string;
  ticker: string;
  sector_id: string;
  agent_id?: number | null;
  agent_name?: string | null;
  status: RunStatus;
  created_at: string;
  started_at?: string | null;
  finished_at: string | null;
  current_node?: string | null;
  error?: string | null;
  signal_card_id: number | null;
}

export interface RunRequest {
  ticker: string;
  sector_id: string;
  agent_id?: number | null;
  max_fetch_retries?: number;
  max_validation_retries?: number;
  dry_run?: boolean;
  model?: string | null;
  api_key?: string | null;
  base_url?: string | null;
}

export interface RunStartResponse {
  run_id: string;
  status: "pending";
  dry_run: boolean;
  agent_id: number;
}

export interface RunFanoutRequest {
  ticker: string;
  sector_id?: string | null;
  agent_ids?: number[] | null;
  model?: string | null;
  max_fetch_retries?: number;
  max_validation_retries?: number;
  dry_run?: boolean;
  api_key?: string | null;
  base_url?: string | null;
}

export interface RunSectorFanoutRequest {
  sector_id: string;
  tickers?: string[] | null;
  agent_ids?: number[] | null;
  model?: string | null;
  max_fetch_retries?: number;
  max_validation_retries?: number;
  dry_run?: boolean;
  api_key?: string | null;
  base_url?: string | null;
}

export interface RunFanoutItem {
  run_id: string;
  agent_id: number;
  agent_name: string;
  status: "pending";
}

export interface RunSectorSynthesisRequest {
  sector_id: string;
  model?: string | null;
  max_fetch_retries?: number;
  max_validation_retries?: number;
  api_key?: string | null;
  base_url?: string | null;
}

export interface RunSynthesisResponse {
  run_id: string;
  sector_id: string;
  sector_label: string;
  status: "pending";
}

export interface RunFanoutResponse {
  ticker: string;
  sector_id: string;
  dry_run: boolean;
  runs: RunFanoutItem[];
}

// ── Agents ──────────────────────────────────────────────────────────────────

export interface AgentSummary {
  id: number;
  name: string;
  description: string | null;
  is_builtin: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface AgentCreateRequest {
  name: string;
  description?: string | null;
  skill_name?: string | null;
  skill_type?: "domain";
  skill_content: string;
}

export interface SSENodeUpdate {
  node: string;
  label: string;
  started_at?: string;
  finished_at?: string;
  error?: string;
}

export interface SSEEvent {
  event: SSEEventType;
  run_id: string;
  data: SSENodeUpdate | Record<string, unknown> | null;
}

// ── Reports ──────────────────────────────────────────────────────────────────

export interface ReportSummary {
  id: number;
  sector_id: string;
  sector_name: string;
  created_at: string;
  status: string;
  confidence_score: number | null;
  validation_status: string | null;
  news_used: number;
}

export interface Prediction {
  id: number;
  signal_card_id: number | null;
  report_id: number | null;
  ticker: string;
  price_at_report: number | null;
  change_1w_at_report: number | null;
  price_1w_later: number | null;
  actual_change_1w: number | null;
  checked_at: string | null;
  prediction_correct: boolean | null;
  ai_direction: string | null;
  ai_predicted_change: string | null;
  ai_reasoning: string | null;
  ai_risk: string | null;
}

export interface ReportDetail extends ReportSummary {
  analysis: string;
  validation: string | null;
  news_summary: string | null;
  predictions: Prediction[];
  prices_snapshot: Array<Record<string, unknown>>;
  technicals_snapshot: Array<Record<string, unknown>>;
  news_snapshot: Array<Record<string, unknown>>;
  filings_snapshot: Array<Record<string, unknown>>;
  timing_snapshot: Record<string, unknown>;
}

// ── Accuracy ─────────────────────────────────────────────────────────────────

export interface SignalTypeBreakdown {
  total: number;
  correct: number;
  accuracy_pct: number | null;
}

export interface AccuracyStats {
  total: number;
  checked: number;
  unchecked: number;
  direction_correct: number;
  direction_incorrect: number;
  direction_accuracy_pct: number | null;
  avg_absolute_error_pct: number | null;
  by_signal_type: Record<string, SignalTypeBreakdown>;
}

// ── User Profile ─────────────────────────────────────────────────────────────

export interface UserDetail {
  id: number;
  email: string;
  username: string | null;
  saved_sectors: string[];
  preferences: Record<string, unknown>;
  role: string;
  status: string;
  picture: string | null;
  last_login_at: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface UserUpdateRequest {
  username?: string | null;
  saved_sectors?: string[];
  preferences?: Record<string, unknown>;
}

// ── Sectors ──────────────────────────────────────────────────────────────────

export interface Sector {
  id: string;
  name: string;
  description?: string;
  tickers: string[];
}
