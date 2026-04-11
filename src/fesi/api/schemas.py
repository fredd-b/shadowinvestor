"""Pydantic response models for the FastAPI layer.

Designed to be JSON-serializable with no surprises. Frontend TypeScript
types should be derived from these via openapi-typescript or similar.
"""
from __future__ import annotations

from pydantic import BaseModel


class SignalOut(BaseModel):
    id: int
    created_at: str
    event_at: str
    ticker_id: int | None = None
    ticker_symbol: str | None = None
    ticker_exchange: str | None = None
    ticker_name: str | None = None
    catalyst_type: str
    sector: str
    headline: str
    summary: str
    economics_summary: str | None = None
    impact_score: int
    probability_score: int
    conviction_score: float
    timeframe_bucket: str
    direction: str
    feature_source_count: int | None = None
    feature_source_diversity: int | None = None
    feature_source_quality_avg: float | None = None
    feature_is_watchlist: int | None = None
    feature_market_cap_bucket: str | None = None
    feature_market_cap_usd: float | None = None
    status: str = "active"
    user_action: str | None = None


class DecisionOut(BaseModel):
    id: int
    signal_id: int
    decided_at: str
    mode: str
    action: str
    ticker_symbol: str | None = None
    ticker_exchange: str | None = None
    catalyst_type: str
    sector: str
    conviction_score: float
    headline: str
    intended_position_usd: float | None = None
    intended_shares: int | None = None
    intended_entry_price: float | None = None
    intended_stop_loss: float | None = None
    intended_target: float | None = None
    intended_holding_period_days: int | None = None
    rule_triggered: str | None = None
    reasoning: str
    confidence: float
    passed_position_size_check: int
    passed_concurrent_check: int
    passed_sector_concentration_check: int
    passed_circuit_breaker_check: int


class TickerOut(BaseModel):
    id: int
    symbol: str
    exchange: str
    name: str
    sector: str | None = None
    sub_sector: str | None = None
    market_cap_usd: float | None = None
    is_watchlist: int = 0
    watchlist_thesis: str | None = None
    alert_min_conviction: int | None = None
    lifecycle_status: str = "monitoring"
    added_by: str = "yaml"
    updated_at: str | None = None


class PortfolioOut(BaseModel):
    mode: str
    deployed_total_usd: float
    deployed_this_month_usd: float
    monthly_cap_usd: float
    cap_used_pct: float
    sector_exposure: dict[str, float]
    open_buy_count: int


class SourceHealthOut(BaseModel):
    key: str
    display_name: str
    type: str
    cost: str
    monthly_usd: float
    trust: int
    active: bool
    items_total: int
    last_fetch: str | None = None


class DigestSummaryOut(BaseModel):
    id: int
    sent_at: str
    scan_window_start: str
    scan_window_end: str
    signal_count: int
    decision_count: int
    delivered_via: str


class DigestOut(DigestSummaryOut):
    markdown_body: str


class PipelineRunOut(BaseModel):
    started_at: str
    ended_at: str | None = None
    raw_items_fetched: int
    raw_items_inserted: int
    raw_items_skipped: int
    candidates: int
    signals_created: int
    decisions_buy: int
    decisions_no_buy: int
    digest_id: int | None = None
    errors: list[str]


class StatusOut(BaseModel):
    version: str
    mode: str
    environment: str
    database: str
    timezone: str
    has_anthropic: bool
    has_pushover: bool
    has_telegram: bool


class ResearchSectorOut(BaseModel):
    sector_key: str
    display_name: str
    description: str
    query_preview: str | None = None
    last_run_at: str | None = None
    items_found_last_run: int = 0
    enabled: bool = False
    schedule: list[dict] = []


class ResearchRunOut(BaseModel):
    sector: str
    items_fetched: int
    items_inserted: int
    items_skipped: int


class AddTickerIn(BaseModel):
    symbol: str
    exchange: str
    name: str
    sector: str
    thesis: str
    sub_sector: str | None = None


class TickerStatusIn(BaseModel):
    status: str  # monitoring, considering, invested, paused, archived
    note: str | None = None


class TickerThesisIn(BaseModel):
    thesis: str


class SignalActionIn(BaseModel):
    action: str  # invest, skip, watch_pullback
    note: str | None = None


class UserActionOut(BaseModel):
    id: int
    action_type: str
    target_type: str
    target_id: int
    note: str | None = None
    created_at: str


class HealthOut(BaseModel):
    status: str
    db: str
