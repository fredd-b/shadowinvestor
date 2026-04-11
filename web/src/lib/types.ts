// TypeScript types mirroring src/fesi/api/schemas.py
// Keep in sync when the API schemas change.

export type Mode = "shadow" | "paper" | "live";
export type Action = "buy" | "no_buy" | "sell" | "hold";
export type Sector =
  | "biotech_pharma"
  | "china_biotech_us_pipeline"
  | "ai_infrastructure"
  | "crypto_to_ai_pivot"
  | "commodities_critical_minerals"
  | "binary_event_other";

export type Signal = {
  id: number;
  created_at: string;
  event_at: string;
  ticker_id: number | null;
  ticker_symbol: string | null;
  ticker_exchange: string | null;
  ticker_name: string | null;
  catalyst_type: string;
  sector: string;
  headline: string;
  summary: string;
  economics_summary: string | null;
  impact_score: number;
  probability_score: number;
  conviction_score: number;
  timeframe_bucket: string;
  direction: string;
  feature_source_count: number | null;
  feature_source_diversity: number | null;
  feature_source_quality_avg: number | null;
  feature_is_watchlist: number | null;
  feature_market_cap_bucket: string | null;
  feature_market_cap_usd: number | null;
  status: string;
  user_action: string | null;
  // Recommendation (from decision engine)
  recommendation: string | null;
  recommendation_reasoning: string | null;
  recommendation_confidence: number | null;
  intended_entry_price: number | null;
  intended_stop_loss: number | null;
  intended_target: number | null;
  intended_position_usd: number | null;
  decision_action: string | null;
  decision_rule: string | null;
};

export type Decision = {
  id: number;
  signal_id: number;
  decided_at: string;
  mode: string;
  action: string;
  ticker_symbol: string | null;
  ticker_exchange: string | null;
  catalyst_type: string;
  sector: string;
  conviction_score: number;
  headline: string;
  intended_position_usd: number | null;
  intended_shares: number | null;
  intended_entry_price: number | null;
  intended_stop_loss: number | null;
  intended_target: number | null;
  intended_holding_period_days: number | null;
  rule_triggered: string | null;
  reasoning: string;
  confidence: number;
  passed_position_size_check: number;
  passed_concurrent_check: number;
  passed_sector_concentration_check: number;
  passed_circuit_breaker_check: number;
};

export type Ticker = {
  id: number;
  symbol: string;
  exchange: string;
  name: string;
  sector: string | null;
  sub_sector: string | null;
  market_cap_usd: number | null;
  is_watchlist: number;
  watchlist_thesis: string | null;
  alert_min_conviction: number | null;
  lifecycle_status: string;
  added_by: string;
  updated_at: string | null;
};

export type Portfolio = {
  mode: string;
  deployed_total_usd: number;
  deployed_this_month_usd: number;
  monthly_cap_usd: number;
  cap_used_pct: number;
  sector_exposure: Record<string, number>;
  open_buy_count: number;
};

export type SourceHealth = {
  key: string;
  display_name: string;
  type: string;
  cost: string;
  monthly_usd: number;
  trust: number;
  active: boolean;
  items_total: number;
  last_fetch: string | null;
};

export type DigestSummary = {
  id: number;
  sent_at: string;
  scan_window_start: string;
  scan_window_end: string;
  signal_count: number;
  decision_count: number;
  delivered_via: string;
};

export type Digest = DigestSummary & {
  markdown_body: string;
};

export type PipelineRun = {
  started_at: string;
  ended_at: string | null;
  raw_items_fetched: number;
  raw_items_inserted: number;
  raw_items_skipped: number;
  candidates: number;
  signals_created: number;
  decisions_buy: number;
  decisions_no_buy: number;
  digest_id: number | null;
  errors: string[];
};

export type Status = {
  version: string;
  mode: string;
  environment: string;
  database: string;
  timezone: string;
  has_anthropic: boolean;
  has_pushover: boolean;
  has_telegram: boolean;
};

export type ResearchSector = {
  sector_key: string;
  display_name: string;
  description: string;
  query_preview: string | null;
  last_run_at: string | null;
  items_found_last_run: number;
  enabled: boolean;
  schedule: { time: string; label: string }[];
};

export type ResearchRun = {
  sector: string;
  items_fetched: number;
  items_inserted: number;
  items_skipped: number;
};

export type ResearchTopic = {
  id: number;
  name: string;
  query_template: string;
  sector_hint: string | null;
  schedule: string;
  is_active: number;
  created_at: string;
  updated_at: string | null;
  last_run_at: string | null;
  total_items_found: number;
};

export type TickerResearchItem = {
  symbol: string;
  name: string;
  lifecycle_status: string;
};

export type TickerIndicators = {
  symbol: string;
  data_points: number;
  entry_price: number | null;
  price_vs_entry_pct: number | null;
  latest: {
    date: string;
    close: number;
    sma_20: number | null;
    sma_50: number | null;
    sma_200: number | null;
    rsi_14: number | null;
    trend: string | null;
  } | null;
};

export type Position = {
  id: number;
  ticker_id: number;
  ticker_symbol: string | null;
  ticker_name: string | null;
  ticker_exchange: string | null;
  mode: string;
  status: string;
  opened_at: string;
  closed_at: string | null;
  entry_price: number;
  exit_price: number | null;
  shares_held: number;
  shares_sold: number;
  cost_basis_usd: number;
  realized_pnl_usd: number;
  unrealized_pnl_usd: number | null;
  current_price: number | null;
  last_price_at: string | null;
  sector: string | null;
  catalyst_type: string | null;
  thesis_at_entry: string | null;
  pnl_pct: number | null;
};
