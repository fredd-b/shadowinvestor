"""Decisions store — insert + query shadow/paper/live decisions."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection


def insert_decision(
    conn: Connection,
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
    result = conn.execute(
        text("""
            INSERT INTO decisions (
                signal_id, decided_at, mode, action,
                intended_position_usd, intended_shares, intended_entry_price,
                intended_stop_loss, intended_target, intended_holding_period_days,
                rule_triggered, reasoning, confidence,
                passed_position_size_check, passed_concurrent_check,
                passed_sector_concentration_check, passed_circuit_breaker_check
            )
            VALUES (
                :signal_id, :decided_at, :mode, :action,
                :intended_position_usd, :intended_shares, :intended_entry_price,
                :intended_stop_loss, :intended_target, :intended_holding_period_days,
                :rule_triggered, :reasoning, :confidence,
                :pos, :conc, :sec, :cb
            )
            RETURNING id
        """),
        {
            "signal_id": signal_id,
            "decided_at": now,
            "mode": mode,
            "action": action,
            "intended_position_usd": intended_position_usd,
            "intended_shares": intended_shares,
            "intended_entry_price": intended_entry_price,
            "intended_stop_loss": intended_stop_loss,
            "intended_target": intended_target,
            "intended_holding_period_days": intended_holding_period_days,
            "rule_triggered": rule_triggered,
            "reasoning": reasoning,
            "confidence": confidence,
            "pos": int(passed_position_size_check),
            "conc": int(passed_concurrent_check),
            "sec": int(passed_sector_concentration_check),
            "cb": int(passed_circuit_breaker_check),
        },
    )
    return result.scalar_one()


def list_recent_decisions(
    conn: Connection,
    since: datetime | None = None,
    mode: str | None = None,
    action: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    sql = """
        SELECT d.*,
               s.headline,
               s.catalyst_type,
               s.sector,
               s.conviction_score,
               t.symbol AS ticker_symbol,
               t.exchange AS ticker_exchange
        FROM decisions d
        JOIN signals s ON d.signal_id = s.id
        LEFT JOIN tickers t ON s.primary_ticker_id = t.id
        WHERE 1=1
    """
    params: dict = {}
    if since is not None:
        sql += " AND d.decided_at >= :since"
        params["since"] = since.isoformat()
    if mode is not None:
        sql += " AND d.mode = :mode"
        params["mode"] = mode
    if action is not None:
        sql += " AND d.action = :action"
        params["action"] = action
    sql += " ORDER BY d.decided_at DESC"
    if limit is not None:
        sql += " LIMIT :limit"
        params["limit"] = limit
    rows = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def count_concurrent_buys(conn: Connection, mode: str) -> int:
    row = conn.execute(
        text("SELECT COUNT(*) AS cnt FROM decisions WHERE mode = :mode AND action = 'buy'"),
        {"mode": mode},
    ).mappings().first()
    return int(row["cnt"]) if row else 0


def get_sector_exposure(conn: Connection, mode: str) -> dict[str, float]:
    rows = conn.execute(
        text("""
            SELECT s.sector, COALESCE(SUM(d.intended_position_usd), 0) AS total
            FROM decisions d
            JOIN signals s ON d.signal_id = s.id
            WHERE d.mode = :mode AND d.action = 'buy'
            GROUP BY s.sector
        """),
        {"mode": mode},
    ).mappings().all()
    return {r["sector"]: float(r["total"] or 0.0) for r in rows}


def total_deployed_capital(conn: Connection, mode: str) -> float:
    row = conn.execute(
        text("""
            SELECT COALESCE(SUM(intended_position_usd), 0) AS total
            FROM decisions
            WHERE mode = :mode AND action = 'buy'
        """),
        {"mode": mode},
    ).mappings().first()
    return float(row["total"] or 0.0) if row else 0.0


def total_deployed_this_month(conn: Connection, mode: str) -> float:
    """Sum of intended_position_usd for all buy decisions this calendar month."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    row = conn.execute(
        text("""
            SELECT COALESCE(SUM(intended_position_usd), 0) AS total
            FROM decisions
            WHERE mode = :mode
              AND action = 'buy'
              AND decided_at >= :month_start
        """),
        {"mode": mode, "month_start": month_start.isoformat()},
    ).mappings().first()
    return float(row["total"] or 0.0) if row else 0.0
