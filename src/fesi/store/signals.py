"""Signals store — insert + query."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


def insert_signal(
    conn: sqlite3.Connection,
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
    cursor = conn.execute(
        """
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now, event_at.isoformat(), primary_ticker_id, catalyst_type, sector,
            headline, summary, economics_summary,
            impact_score, probability_score, conviction_score, timeframe_bucket, direction,
            feature_source_count, feature_source_diversity, feature_source_quality_avg,
            feature_sentiment_score, feature_market_cap_bucket, feature_market_cap_usd,
            feature_time_of_day, feature_day_of_week, feature_is_watchlist,
            feature_catalyst_prior_hit_rate, feature_catalyst_prior_avg_return,
            feature_embedding_id,
            json.dumps(raw_item_ids or []), json.dumps(source_urls or []), status,
        ),
    )
    return cursor.lastrowid


def list_signals_in_window(
    conn: sqlite3.Connection,
    since: datetime,
    until: datetime | None = None,
    min_conviction: float | None = None,
    sector: str | None = None,
) -> list[dict]:
    sql = """
        SELECT s.*, t.symbol as ticker_symbol, t.exchange as ticker_exchange,
               t.name as ticker_name
        FROM signals s
        LEFT JOIN tickers t ON s.primary_ticker_id = t.id
        WHERE s.created_at >= ?
    """
    args: list[Any] = [since.isoformat()]
    if until is not None:
        sql += " AND s.created_at <= ?"
        args.append(until.isoformat())
    if min_conviction is not None:
        sql += " AND s.conviction_score >= ?"
        args.append(min_conviction)
    if sector is not None:
        sql += " AND s.sector = ?"
        args.append(sector)
    sql += " ORDER BY s.conviction_score DESC, s.created_at DESC"
    rows = conn.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def get_signal_by_id(conn: sqlite3.Connection, signal_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT s.*, t.symbol as ticker_symbol, t.exchange as ticker_exchange,
               t.name as ticker_name
        FROM signals s
        LEFT JOIN tickers t ON s.primary_ticker_id = t.id
        WHERE s.id = ?
        """,
        (signal_id,),
    ).fetchone()
    return dict(row) if row else None


def list_signals_for_ticker(
    conn: sqlite3.Connection, ticker_id: int, limit: int = 50
) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM signals WHERE primary_ticker_id = ? ORDER BY created_at DESC LIMIT ?",
        (ticker_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def count_signals_in_window(conn: sqlite3.Connection, since: datetime) -> int:
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM signals WHERE created_at >= ?",
        (since.isoformat(),),
    ).fetchone()
    return row["cnt"]
