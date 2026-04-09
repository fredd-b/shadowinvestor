"""Outcomes store — joins signals to realized P&L for ML training & backtest."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from fesi.logging import get_logger
from fesi.store.prices import get_price_on_or_after

log = get_logger(__name__)


def upsert_outcome_stub(conn: sqlite3.Connection, signal_id: int) -> int | None:
    """Create an empty outcomes row for a new signal so we can JOIN later."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        cursor = conn.execute(
            """
            INSERT INTO outcomes (signal_id, last_updated_at, is_mature)
            VALUES (?, ?, 0)
            """,
            (signal_id, now),
        )
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None  # already exists


def update_outcome_for_signal(
    conn: sqlite3.Connection, signal_id: int
) -> dict | None:
    """Compute T+N returns for a signal by joining to its ticker's prices.

    A signal is 'mature' once T+30 days have elapsed since the signal's event_at.
    Sets price_t1, price_t5, price_t30, return_t*, max_drawup_30d, max_drawdown_30d.
    """
    signal = conn.execute(
        "SELECT * FROM signals WHERE id = ?", (signal_id,)
    ).fetchone()
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

    # Path metrics over 30 days
    rows = conn.execute(
        """
        SELECT high, low FROM prices
        WHERE ticker_id = ? AND date BETWEEN ? AND ?
        """,
        (
            ticker_id,
            base_date.strftime("%Y-%m-%d"),
            (base_date + timedelta(days=30)).strftime("%Y-%m-%d"),
        ),
    ).fetchall()

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
        """
        UPDATE outcomes
        SET price_at_signal = ?,
            price_t1 = ?, price_t5 = ?, price_t30 = ?, price_t90 = ?,
            return_t1 = ?, return_t5 = ?, return_t30 = ?, return_t90 = ?,
            max_drawup_30d = ?, max_drawdown_30d = ?,
            last_updated_at = ?, is_mature = ?
        WHERE signal_id = ?
        """,
        (
            base_price,
            p1["close"] if p1 else None,
            p5["close"] if p5 else None,
            p30["close"] if p30 else None,
            p90["close"] if p90 else None,
            ret(p1), ret(p5), ret(p30), ret(p90),
            max_drawup, max_drawdown,
            now, int(is_mature),
            signal_id,
        ),
    )

    return {
        "signal_id": signal_id,
        "price_at_signal": base_price,
        "return_t1": ret(p1),
        "return_t5": ret(p5),
        "return_t30": ret(p30),
        "is_mature": is_mature,
    }


def update_all_outcomes(conn: sqlite3.Connection) -> dict:
    """Daily job: update outcomes for all signals that aren't yet fully mature."""
    rows = conn.execute(
        """
        SELECT signal_id FROM outcomes WHERE is_mature = 0
        """
    ).fetchall()
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
