"""Decisions store — insert + query shadow/paper/live decisions."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def insert_decision(
    conn: sqlite3.Connection,
    *,
    signal_id: int,
    mode: str,
    action: str,
    intended_position_usd: float | None = None,
    intended_shares: int | None = None,
    intended_entry_price: float | None = None,
    intended_stop_loss: float | None = None,
    intended_target: float | None = None,
    intended_holding_period_days: int | None = None,
    rule_triggered: str | None = None,
    reasoning: str = "",
    confidence: float = 0.5,
    passed_position_size_check: bool = True,
    passed_concurrent_check: bool = True,
    passed_sector_concentration_check: bool = True,
    passed_circuit_breaker_check: bool = True,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO decisions (
            signal_id, decided_at, mode, action,
            intended_position_usd, intended_shares, intended_entry_price,
            intended_stop_loss, intended_target, intended_holding_period_days,
            rule_triggered, reasoning, confidence,
            passed_position_size_check, passed_concurrent_check,
            passed_sector_concentration_check, passed_circuit_breaker_check
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal_id, now, mode, action,
            intended_position_usd, intended_shares, intended_entry_price,
            intended_stop_loss, intended_target, intended_holding_period_days,
            rule_triggered, reasoning, confidence,
            int(passed_position_size_check), int(passed_concurrent_check),
            int(passed_sector_concentration_check), int(passed_circuit_breaker_check),
        ),
    )
    return cursor.lastrowid


def list_recent_decisions(
    conn: sqlite3.Connection,
    since: datetime | None = None,
    mode: str | None = None,
    action: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    sql = """
        SELECT d.*, s.headline, s.catalyst_type, s.sector, s.conviction_score,
               t.symbol as ticker_symbol, t.exchange as ticker_exchange
        FROM decisions d
        JOIN signals s ON d.signal_id = s.id
        LEFT JOIN tickers t ON s.primary_ticker_id = t.id
        WHERE 1=1
    """
    args: list = []
    if since is not None:
        sql += " AND d.decided_at >= ?"
        args.append(since.isoformat())
    if mode is not None:
        sql += " AND d.mode = ?"
        args.append(mode)
    if action is not None:
        sql += " AND d.action = ?"
        args.append(action)
    sql += " ORDER BY d.decided_at DESC"
    if limit is not None:
        sql += " LIMIT ?"
        args.append(limit)
    rows = conn.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def count_concurrent_buys(conn: sqlite3.Connection, mode: str) -> int:
    """Count current 'buy' decisions in the given mode (Phase 1 has no exit logic
    yet so this counts all buys ever — Phase 2 will subtract closed positions)."""
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM decisions WHERE mode = ? AND action = 'buy'",
        (mode,),
    ).fetchone()
    return row["cnt"]


def get_sector_exposure(
    conn: sqlite3.Connection, mode: str
) -> dict[str, float]:
    """Total $ deployed per sector for current open buys."""
    rows = conn.execute(
        """
        SELECT s.sector, COALESCE(SUM(d.intended_position_usd), 0) as total
        FROM decisions d
        JOIN signals s ON d.signal_id = s.id
        WHERE d.mode = ? AND d.action = 'buy'
        GROUP BY s.sector
        """,
        (mode,),
    ).fetchall()
    return {r["sector"]: float(r["total"] or 0.0) for r in rows}


def total_deployed_capital(conn: sqlite3.Connection, mode: str) -> float:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(intended_position_usd), 0) as total
        FROM decisions
        WHERE mode = ? AND action = 'buy'
        """,
        (mode,),
    ).fetchone()
    return float(row["total"] or 0.0)


def total_deployed_this_month(conn: sqlite3.Connection, mode: str) -> float:
    """Sum of intended_position_usd for all buy decisions this calendar month."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    row = conn.execute(
        """
        SELECT COALESCE(SUM(intended_position_usd), 0) as total
        FROM decisions
        WHERE mode = ? AND action = 'buy' AND decided_at >= ?
        """,
        (mode, month_start.isoformat()),
    ).fetchone()
    return float(row["total"] or 0.0)
