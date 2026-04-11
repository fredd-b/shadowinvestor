"""Signals store — insert + query.

Each insert also populates the `raw_items_signals` junction table so the
`get_unprocessed_raw_items` query can use a portable LEFT JOIN instead of
SQLite-specific json_each.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection


def insert_signal(
    conn: Connection,
    *,
    event_at: datetime,
    primary_ticker_id: int | None,
    catalyst_type: str,
    sector: str,
    headline: str,
    summary: str,
    economics_summary: str | None,
    impact_score: int,
    probability_score: int,
    conviction_score: float,
    timeframe_bucket: str,
    direction: str = "bullish",
    feature_source_count: int = 1,
    feature_source_diversity: int = 1,
    feature_source_quality_avg: float = 3.0,
    feature_sentiment_score: float = 0.0,
    feature_market_cap_bucket: str | None = None,
    feature_market_cap_usd: float | None = None,
    feature_time_of_day: str | None = None,
    feature_day_of_week: int | None = None,
    feature_is_watchlist: int = 0,
    feature_catalyst_prior_hit_rate: float | None = None,
    feature_catalyst_prior_avg_return: float | None = None,
    feature_embedding_id: int | None = None,
    raw_item_ids: list[int] | None = None,
    source_urls: list[str] | None = None,
    status: str = "active",
) -> int:
    """Insert a fully-formed signal row, ML feature vector included."""
    now = datetime.now(timezone.utc).isoformat()
    result = conn.execute(
        text("""
            INSERT INTO signals (
                created_at, event_at, primary_ticker_id, catalyst_type, sector,
                headline, summary, economics_summary,
                impact_score, probability_score, conviction_score, timeframe_bucket, direction,
                feature_source_count, feature_source_diversity, feature_source_quality_avg,
                feature_sentiment_score, feature_market_cap_bucket, feature_market_cap_usd,
                feature_time_of_day, feature_day_of_week, feature_is_watchlist,
                feature_catalyst_prior_hit_rate, feature_catalyst_prior_avg_return,
                feature_embedding_id,
                raw_item_ids, source_urls, status
            )
            VALUES (
                :created_at, :event_at, :primary_ticker_id, :catalyst_type, :sector,
                :headline, :summary, :economics_summary,
                :impact_score, :probability_score, :conviction_score, :timeframe_bucket, :direction,
                :feature_source_count, :feature_source_diversity, :feature_source_quality_avg,
                :feature_sentiment_score, :feature_market_cap_bucket, :feature_market_cap_usd,
                :feature_time_of_day, :feature_day_of_week, :feature_is_watchlist,
                :feature_catalyst_prior_hit_rate, :feature_catalyst_prior_avg_return,
                :feature_embedding_id,
                :raw_item_ids, :source_urls, :status
            )
            RETURNING id
        """),
        {
            "created_at": now,
            "event_at": event_at.isoformat(),
            "primary_ticker_id": primary_ticker_id,
            "catalyst_type": catalyst_type,
            "sector": sector,
            "headline": headline,
            "summary": summary,
            "economics_summary": economics_summary,
            "impact_score": impact_score,
            "probability_score": probability_score,
            "conviction_score": conviction_score,
            "timeframe_bucket": timeframe_bucket,
            "direction": direction,
            "feature_source_count": feature_source_count,
            "feature_source_diversity": feature_source_diversity,
            "feature_source_quality_avg": feature_source_quality_avg,
            "feature_sentiment_score": feature_sentiment_score,
            "feature_market_cap_bucket": feature_market_cap_bucket,
            "feature_market_cap_usd": feature_market_cap_usd,
            "feature_time_of_day": feature_time_of_day,
            "feature_day_of_week": feature_day_of_week,
            "feature_is_watchlist": feature_is_watchlist,
            "feature_catalyst_prior_hit_rate": feature_catalyst_prior_hit_rate,
            "feature_catalyst_prior_avg_return": feature_catalyst_prior_avg_return,
            "feature_embedding_id": feature_embedding_id,
            "raw_item_ids": json.dumps(raw_item_ids or []),
            "source_urls": json.dumps(source_urls or []),
            "status": status,
        },
    )
    signal_id = result.scalar_one()

    # Populate junction table for the unprocessed-items query
    if raw_item_ids:
        for rid in raw_item_ids:
            conn.execute(
                text("""
                    INSERT INTO raw_items_signals (raw_item_id, signal_id)
                    VALUES (:rid, :sid)
                """),
                {"rid": rid, "sid": signal_id},
            )

    return signal_id


def list_signals_in_window(
    conn: Connection,
    since: datetime,
    until: datetime | None = None,
    min_conviction: float | None = None,
    sector: str | None = None,
) -> list[dict]:
    sql = """
        SELECT s.*,
               t.symbol AS ticker_symbol,
               t.exchange AS ticker_exchange,
               t.name AS ticker_name
        FROM signals s
        LEFT JOIN tickers t ON s.primary_ticker_id = t.id
        WHERE s.created_at >= :since
    """
    params: dict = {"since": since.isoformat()}
    if until is not None:
        sql += " AND s.created_at <= :until"
        params["until"] = until.isoformat()
    if min_conviction is not None:
        sql += " AND s.conviction_score >= :min_conviction"
        params["min_conviction"] = min_conviction
    if sector is not None:
        sql += " AND s.sector = :sector"
        params["sector"] = sector
    sql += " ORDER BY s.conviction_score DESC, s.created_at DESC"
    rows = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def get_signal_by_id(conn: Connection, signal_id: int) -> dict | None:
    row = conn.execute(
        text("""
            SELECT s.*,
                   t.symbol AS ticker_symbol,
                   t.exchange AS ticker_exchange,
                   t.name AS ticker_name
            FROM signals s
            LEFT JOIN tickers t ON s.primary_ticker_id = t.id
            WHERE s.id = :id
        """),
        {"id": signal_id},
    ).mappings().first()
    return dict(row) if row else None


def list_signals_for_ticker(
    conn: Connection, ticker_id: int, limit: int = 50
) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT * FROM signals
            WHERE primary_ticker_id = :ticker_id
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        {"ticker_id": ticker_id, "limit": limit},
    ).mappings().all()
    return [dict(r) for r in rows]


def count_signals_in_window(conn: Connection, since: datetime) -> int:
    row = conn.execute(
        text("SELECT COUNT(*) AS cnt FROM signals WHERE created_at >= :since"),
        {"since": since.isoformat()},
    ).mappings().first()
    return int(row["cnt"]) if row else 0


VALID_USER_ACTIONS = {"invest", "skip", "watch_pullback"}


def update_signal_user_action(
    conn: Connection, signal_id: int, user_action: str
) -> None:
    """Set Fred's decision on a signal: invest / skip / watch_pullback."""
    if user_action not in VALID_USER_ACTIONS:
        raise ValueError(f"Invalid user_action: {user_action}")
    conn.execute(
        text("UPDATE signals SET user_action = :action WHERE id = :id"),
        {"action": user_action, "id": signal_id},
    )
