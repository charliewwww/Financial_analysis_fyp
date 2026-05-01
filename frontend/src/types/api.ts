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
}

export interface SignalCard {
  id: number;
  ticker: string;
  run_id: string | null;
  signal: Signal;
  conviction: number | null;
  one_line: string | null;
  key_catalyst: string | null;
  key_risk: string | null;
  confidence: number | null;
  signal_type: string | null;
  validation_score: string | null;
  supply_chain_impact: SupplyChainImpact[] | null;
  sources: SignalSource[] | null;
  numerical_claims: NumericalClaim[] | null;
  sector_context: string | null;
  created_at: string;
  status: string;
}

export interface NodeExecution {
  node: string;
  label: string;
  status: "running" | "completed" | "failed" | "skipped";
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
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
  status: RunStatus;
  created_at: string;
  finished_at: string | null;
  signal_card_id: number | null;
}

export interface RunRequest {
  ticker: string;
  sector_id: string;
  agent_id?: number | null;
  max_fetch_retries?: number;
  max_validation_retries?: number;
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
}

// ── Accuracy ─────────────────────────────────────────────────────────────────

export interface SignalTypeBreakdown {
  total: number;
  correct: number;
  accuracy_pct: number;
}

export interface AccuracyStats {
  total: number;
  checked: number;
  unchecked: number;
  direction_correct: number;
  direction_incorrect: number;
  direction_accuracy_pct: number;
  avg_absolute_error_pct: number;
  by_signal_type: Record<string, SignalTypeBreakdown>;
}

// ── User Profile ─────────────────────────────────────────────────────────────

export interface UserDetail {
  id: number;
  email: string;
  username: string | null;
  saved_sectors: string[];
  preferences: Record<string, unknown>;
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
