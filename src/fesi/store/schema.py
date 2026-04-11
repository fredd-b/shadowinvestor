"""SQLAlchemy schema — single source of truth for all FESI tables.

This module replaces the raw SQL migration files. `metadata.create_all(engine)`
is idempotent and dialect-aware, so the same definitions work for SQLite (dev)
and Postgres (Railway prod).

Schema changes after this point should be additive and accompanied by an
explicit upgrade in `db.upgrade_schema()` (which is currently empty).
"""
from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
)

metadata = MetaData()

# ============================================================================
# raw_items: every fetched item from any source, before normalization.
# ============================================================================
raw_items = Table(
    "raw_items",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("source", Text, nullable=False),
    Column("source_id", Text, nullable=False),
    Column("fetched_at", Text, nullable=False),
    Column("published_at", Text),
    Column("url", Text),
    Column("title", Text),
    Column("raw_payload", Text, nullable=False),
    Column("content_hash", Text, nullable=False),
    UniqueConstraint("source", "source_id", name="uq_raw_items_source_id"),
    Index("idx_raw_items_fetched", "fetched_at"),
    Index("idx_raw_items_published", "published_at"),
    Index("idx_raw_items_hash", "content_hash"),
)

# ============================================================================
# tickers: master list of tradeable instruments.
# ============================================================================
tickers = Table(
    "tickers",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("symbol", Text, nullable=False),
    Column("exchange", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("sector", Text),
    Column("sub_sector", Text),
    Column("market_cap_usd", Float),
    Column("country", Text),
    Column("is_watchlist", Integer, nullable=False, default=0),
    Column("watchlist_thesis", Text),
    Column("alert_min_conviction", Integer, default=3),
    Column("added_at", Text, nullable=False),
    # Phase 2.7: dynamic watchlist lifecycle
    Column("lifecycle_status", Text, nullable=False, default="monitoring"),
    Column("added_by", Text, nullable=False, default="yaml"),
    Column("updated_at", Text),
    UniqueConstraint("symbol", "exchange", name="uq_tickers_symbol_exchange"),
    CheckConstraint(
        "lifecycle_status IN ('monitoring','considering','invested','paused','archived')",
        name="ck_tickers_lifecycle",
    ),
    Index("idx_tickers_symbol", "symbol"),
    Index("idx_tickers_watchlist", "is_watchlist"),
    Index("idx_tickers_lifecycle", "lifecycle_status"),
)

# ============================================================================
# signals: normalized + classified events. ML feature vector frozen at creation.
# ============================================================================
signals = Table(
    "signals",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("created_at", Text, nullable=False),
    Column("event_at", Text, nullable=False),
    Column("primary_ticker_id", Integer, ForeignKey("tickers.id")),
    Column("catalyst_type", Text, nullable=False),
    Column("sector", Text, nullable=False),
    Column("headline", Text, nullable=False),
    Column("summary", Text, nullable=False),
    Column("economics_summary", Text),
    Column("impact_score", Integer, nullable=False),
    Column("probability_score", Integer, nullable=False),
    Column("conviction_score", Float, nullable=False),
    Column("timeframe_bucket", Text, nullable=False),
    Column("direction", Text, nullable=False, default="bullish"),
    # ML feature vector (frozen at creation, point-in-time correct)
    Column("feature_source_count", Integer),
    Column("feature_source_diversity", Integer),
    Column("feature_source_quality_avg", Float),
    Column("feature_sentiment_score", Float),
    Column("feature_market_cap_bucket", Text),
    Column("feature_market_cap_usd", Float),
    Column("feature_time_of_day", Text),
    Column("feature_day_of_week", Integer),
    Column("feature_is_watchlist", Integer),
    Column("feature_catalyst_prior_hit_rate", Float),
    Column("feature_catalyst_prior_avg_return", Float),
    Column("feature_embedding_id", Integer),
    # Source materials (denormalized JSON for quick read; junction table is canonical)
    Column("raw_item_ids", Text),
    Column("source_urls", Text),
    Column("status", Text, nullable=False, default="active"),
    # Phase 2.7: user decision override
    Column("user_action", Text),  # invest / skip / watch_pullback / null
    CheckConstraint("impact_score BETWEEN 1 AND 5", name="ck_signals_impact"),
    CheckConstraint("probability_score BETWEEN 1 AND 5", name="ck_signals_probability"),
    Index("idx_signals_created", "created_at"),
    Index("idx_signals_event", "event_at"),
    Index("idx_signals_ticker", "primary_ticker_id"),
    Index("idx_signals_catalyst", "catalyst_type"),
    Index("idx_signals_sector", "sector"),
    Index("idx_signals_conviction", "conviction_score"),
    Index("idx_signals_status", "status"),
)

# ============================================================================
# raw_items_signals: junction (replaces SQLite-specific json_each query).
# Lets us answer "which raw items have not yet been turned into a signal"
# portably across SQLite and Postgres.
# ============================================================================
raw_items_signals = Table(
    "raw_items_signals",
    metadata,
    Column("raw_item_id", Integer, ForeignKey("raw_items.id"), primary_key=True),
    Column("signal_id", Integer, ForeignKey("signals.id"), primary_key=True),
    Index("idx_ris_raw", "raw_item_id"),
    Index("idx_ris_signal", "signal_id"),
)

# ============================================================================
# decisions: every shadow / paper / live decision the system made.
# ============================================================================
decisions = Table(
    "decisions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("signal_id", Integer, ForeignKey("signals.id"), nullable=False),
    Column("decided_at", Text, nullable=False),
    Column("mode", Text, nullable=False),
    Column("action", Text, nullable=False),
    Column("intended_position_usd", Float),
    Column("intended_shares", Integer),
    Column("intended_entry_price", Float),
    Column("intended_stop_loss", Float),
    Column("intended_target", Float),
    Column("intended_holding_period_days", Integer),
    Column("rule_triggered", Text),
    Column("reasoning", Text, nullable=False),
    Column("confidence", Float, nullable=False),
    Column("passed_position_size_check", Integer, nullable=False),
    Column("passed_concurrent_check", Integer, nullable=False),
    Column("passed_sector_concentration_check", Integer, nullable=False),
    Column("passed_circuit_breaker_check", Integer, nullable=False),
    CheckConstraint("mode IN ('shadow','paper','live')", name="ck_decisions_mode"),
    CheckConstraint("action IN ('buy','no_buy','sell','hold')", name="ck_decisions_action"),
    Index("idx_decisions_signal", "signal_id"),
    Index("idx_decisions_decided", "decided_at"),
    Index("idx_decisions_mode_action", "mode", "action"),
)

# ============================================================================
# trades: actual executions (paper or live).
# ============================================================================
trades = Table(
    "trades",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("decision_id", Integer, ForeignKey("decisions.id")),  # nullable for manual sells
    Column("mode", Text, nullable=False),
    Column("side", Text, nullable=False),
    Column("ticker_id", Integer, ForeignKey("tickers.id"), nullable=False),
    Column("submitted_at", Text, nullable=False),
    Column("filled_at", Text),
    Column("requested_shares", Integer, nullable=False),
    Column("filled_shares", Integer),
    Column("requested_price", Float),
    Column("filled_price", Float),
    Column("broker_order_id", Text),
    Column("status", Text, nullable=False),
    Column("fees_usd", Float, default=0),
    CheckConstraint("side IN ('buy','sell')", name="ck_trades_side"),
    Index("idx_trades_decision", "decision_id"),
    Index("idx_trades_ticker", "ticker_id"),
    Index("idx_trades_mode_status", "mode", "status"),
)

# ============================================================================
# outcomes: joins signals → realized P&L for ML training & backtest.
# ============================================================================
outcomes = Table(
    "outcomes",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("signal_id", Integer, ForeignKey("signals.id"), nullable=False, unique=True),
    Column("price_at_signal", Float),
    Column("price_t1", Float),
    Column("price_t5", Float),
    Column("price_t30", Float),
    Column("price_t90", Float),
    Column("return_t1", Float),
    Column("return_t5", Float),
    Column("return_t30", Float),
    Column("return_t90", Float),
    Column("max_drawup_30d", Float),
    Column("max_drawdown_30d", Float),
    Column("last_updated_at", Text, nullable=False),
    Column("is_mature", Integer, nullable=False, default=0),
    Index("idx_outcomes_mature", "is_mature"),
)

# ============================================================================
# prices: OHLCV cache (one row per ticker per day).
# ============================================================================
prices = Table(
    "prices",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ticker_id", Integer, ForeignKey("tickers.id"), nullable=False),
    Column("date", Text, nullable=False),
    Column("open", Float),
    Column("high", Float),
    Column("low", Float),
    Column("close", Float, nullable=False),
    Column("volume", Integer),
    Column("source", Text, nullable=False),
    UniqueConstraint("ticker_id", "date", name="uq_prices_ticker_date"),
    Index("idx_prices_ticker_date", "ticker_id", "date"),
)

# ============================================================================
# embeddings: text vectors for semantic dedupe and ML.
# ============================================================================
embeddings = Table(
    "embeddings",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("text_hash", Text, nullable=False, unique=True),
    Column("model", Text, nullable=False),
    Column("vector", LargeBinary, nullable=False),
    Column("created_at", Text, nullable=False),
)

# ============================================================================
# catalyst_priors: historical baselines per catalyst type, learned from outcomes.
# ============================================================================
catalyst_priors = Table(
    "catalyst_priors",
    metadata,
    Column("catalyst_type", Text, primary_key=True),
    Column("sample_size", Integer, nullable=False),
    Column("hit_rate", Float),
    Column("avg_return_t1", Float),
    Column("avg_return_t5", Float),
    Column("avg_return_t30", Float),
    Column("avg_max_drawup", Float),
    Column("avg_max_drawdown", Float),
    Column("updated_at", Text, nullable=False),
)

# ============================================================================
# user_actions: append-only audit trail of every action Fred takes.
# ============================================================================
user_actions = Table(
    "user_actions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("action_type", Text, nullable=False),
    Column("target_type", Text, nullable=False),  # signal, ticker, decision, position
    Column("target_id", Integer, nullable=False),
    Column("note", Text),
    Column("created_at", Text, nullable=False),
    CheckConstraint(
        "action_type IN ('invest','skip','watch_pullback','add_watchlist',"
        "'remove_watchlist','edit_thesis','change_status','sell','override_decision')",
        name="ck_user_actions_type",
    ),
    Index("idx_user_actions_target", "target_type", "target_id"),
    Index("idx_user_actions_created", "created_at"),
)

# ============================================================================
# research_topics: user-created research queries.
# ============================================================================
research_topics = Table(
    "research_topics",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", Text, nullable=False),
    Column("query_template", Text, nullable=False),
    Column("sector_hint", Text),
    Column("schedule", Text, nullable=False, default="daily"),
    Column("is_active", Integer, nullable=False, default=1),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text),
    Column("last_run_at", Text),
    Column("total_items_found", Integer, nullable=False, default=0),
    UniqueConstraint("name", name="uq_research_topics_name"),
    CheckConstraint("schedule IN ('daily','every_run')", name="ck_research_topics_schedule"),
    Index("idx_research_topics_active", "is_active"),
)

# ============================================================================
# positions: tracks open/closed positions with P&L.
# ============================================================================
positions = Table(
    "positions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ticker_id", Integer, ForeignKey("tickers.id"), nullable=False),
    Column("mode", Text, nullable=False),
    Column("status", Text, nullable=False, default="open"),
    Column("opened_at", Text, nullable=False),
    Column("closed_at", Text),
    Column("entry_decision_id", Integer, ForeignKey("decisions.id")),
    Column("exit_decision_id", Integer, ForeignKey("decisions.id")),
    Column("entry_price", Float, nullable=False),
    Column("exit_price", Float),
    Column("shares_held", Integer, nullable=False),
    Column("shares_sold", Integer, nullable=False, default=0),
    Column("cost_basis_usd", Float, nullable=False),
    Column("realized_pnl_usd", Float, default=0),
    Column("unrealized_pnl_usd", Float),
    Column("current_price", Float),
    Column("last_price_at", Text),
    Column("sector", Text),
    Column("catalyst_type", Text),
    Column("thesis_at_entry", Text),
    CheckConstraint("status IN ('open','partial_closed','closed')", name="ck_positions_status"),
    CheckConstraint("mode IN ('shadow','paper','live')", name="ck_positions_mode"),
    Index("idx_positions_ticker", "ticker_id"),
    Index("idx_positions_status", "status"),
    Index("idx_positions_mode", "mode", "status"),
)

# ============================================================================
# digests: every digest sent (for journaling and audit).
# ============================================================================
digests = Table(
    "digests",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("sent_at", Text, nullable=False),
    Column("scan_window_start", Text, nullable=False),
    Column("scan_window_end", Text, nullable=False),
    Column("signal_count", Integer, nullable=False),
    Column("decision_count", Integer, nullable=False),
    Column("delivered_via", Text, nullable=False),
    Column("markdown_body", Text, nullable=False),
    Index("idx_digests_sent", "sent_at"),
)
