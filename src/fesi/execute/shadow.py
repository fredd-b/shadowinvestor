"""Shadow execution — virtual fills for shadow mode.

In shadow mode, every 'buy' decision generates a virtual `trades` row with
status='filled' at the planned entry_price. No broker is called.

Phase 4 will add `ibkr.py` for real paper / live execution, gated behind
MODE=paper or MODE=live. The interface here is intentionally identical so the
pipeline doesn't care which one is wired.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def execute_shadow_buy(
    conn: sqlite3.Connection,
    *,
    decision_id: int,
    ticker_id: int,
    shares: int,
    entry_price: float,
) -> int:
    """Record a virtual filled buy in the trades table."""
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO trades (
            decision_id, mode, side, ticker_id,
            submitted_at, filled_at,
            requested_shares, filled_shares,
            requested_price, filled_price,
            broker_order_id, status, fees_usd
        )
        VALUES (?, 'shadow', 'buy', ?, ?, ?, ?, ?, ?, ?, ?, 'filled', 0)
        """,
        (
            decision_id, ticker_id,
            now, now,
            shares, shares,
            entry_price, entry_price,
            f"shadow-{decision_id}",
        ),
    )
    return cursor.lastrowid
