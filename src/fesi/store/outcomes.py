"""Outcomes store — joins signals to realized P&L for ML training & backtest."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from fesi.logging import get_logger
from fesi.store.prices import get_price_on_or_after

log = get_logger(__name__)


def upsert_outcome_stub(conn: Connection, signal_id: int) -> int | None:
    """Create an empty outcomes row for a new signal so we can JOIN later."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        with conn.begin_nested():
            result = conn.execute(
                text("""
                    INSERT INTO outcomes (signal_id, last_updated_at, is_mature)
                    VALUES (:signal_id, :now, 0)
                    RETURNING id
                """),
                {"signal_id": signal_id, "now": now},
            )
            return result.scalar_one()
    except IntegrityError:
        return None  # already exists


def update_outcome_for_signal(
    conn: Connection, signal_id: int
) -> dict | None:
    """Compute T+N returns for a signal by joining to its ticker's prices."""
    signal = conn.execute(
        text("SELECT * FROM signals WHERE id = :id"),
        {"id": signal_id},
    ).mappings().first()
    if not signal:
        return None

    ticker_id = signal["primary_ticker_id"]
    if ticker_id is None:
        return None

    event_at = datetime.fromisoformat(signal["event_at"])
    event_date = event_at.strftime("%Y-%m-%d")

    p0 = get_price_on_or_after(conn, ticker_id, event_date)
    if p0 is None:
        return None

    base_price = p0["close"]
    base_date = datetime.strptime(p0["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)

    def at_offset(days: int) -> dict | None:
        target = (base_date + timedelta(days=days)).strftime("%Y-%m-%d")
        return get_price_on_or_after(conn, ticker_id, target)

    p1 = at_offset(1)
    p5 = at_offset(5)
    p30 = at_offset(30)
    p90 = at_offset(90)

    def ret(p: dict | None) -> float | None:
        if p is None or base_price == 0:
            return None
        return round((p["close"] - base_price) / base_price, 4)

    rows = conn.execute(
        text("""
            SELECT high, low FROM prices
            WHERE ticker_id = :ticker_id AND date BETWEEN :start AND :end
        """),
        {
            "ticker_id": ticker_id,
            "start": base_date.strftime("%Y-%m-%d"),
            "end": (base_date + timedelta(days=30)).strftime("%Y-%m-%d"),
        },
    ).mappings().all()

    max_drawup = None
    max_drawdown = None
    if rows:
        highs = [r["high"] for r in rows if r["high"] is not None]
        lows = [r["low"] for r in rows if r["low"] is not None]
        if highs:
            max_drawup = round((max(highs) - base_price) / base_price, 4)
        if lows:
            max_drawdown = round((min(lows) - base_price) / base_price, 4)

    is_mature = (datetime.now(timezone.utc) - event_at) >= timedelta(days=30)
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        text("""
            UPDATE outcomes
            SET price_at_signal = :p0,
                price_t1 = :p1, price_t5 = :p5, price_t30 = :p30, price_t90 = :p90,
                return_t1 = :r1, return_t5 = :r5, return_t30 = :r30, return_t90 = :r90,
                max_drawup_30d = :du, max_drawdown_30d = :dd,
                last_updated_at = :now, is_mature = :mature
            WHERE signal_id = :signal_id
        """),
        {
            "p0": base_price,
            "p1": p1["close"] if p1 else None,
            "p5": p5["close"] if p5 else None,
            "p30": p30["close"] if p30 else None,
            "p90": p90["close"] if p90 else None,
            "r1": ret(p1),
            "r5": ret(p5),
            "r30": ret(p30),
            "r90": ret(p90),
            "du": max_drawup,
            "dd": max_drawdown,
            "now": now,
            "mature": int(is_mature),
            "signal_id": signal_id,
        },
    )

    return {
        "signal_id": signal_id,
        "price_at_signal": base_price,
        "return_t1": ret(p1),
        "return_t5": ret(p5),
        "return_t30": ret(p30),
        "is_mature": is_mature,
    }


def update_all_outcomes(conn: Connection) -> dict:
    """Daily job: update outcomes for all signals that aren't yet fully mature."""
    rows = conn.execute(
        text("SELECT signal_id FROM outcomes WHERE is_mature = 0")
    ).mappings().all()
    updated = 0
    matured = 0
    for r in rows:
        result = update_outcome_for_signal(conn, r["signal_id"])
        if result:
            updated += 1
            if result["is_mature"]:
                matured += 1
    log.info("outcomes_updated", updated=updated, matured=matured)
    return {"updated": updated, "matured": matured}
