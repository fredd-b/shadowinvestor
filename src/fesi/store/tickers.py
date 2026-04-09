"""Tickers store — load watchlist into DB, upsert, lookup by symbol."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from fesi.config import load_watchlist
from fesi.logging import get_logger

log = get_logger(__name__)


def upsert_ticker(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    exchange: str,
    name: str,
    sector: str | None = None,
    sub_sector: str | None = None,
    is_watchlist: bool = False,
    watchlist_thesis: str | None = None,
    alert_min_conviction: int = 3,
    market_cap_usd: float | None = None,
) -> int:
    """Insert ticker if missing, otherwise update mutable fields. Returns ticker_id."""
    now = datetime.now(timezone.utc).isoformat()
    row = conn.execute(
        "SELECT id FROM tickers WHERE symbol = ? AND exchange = ?",
        (symbol, exchange),
    ).fetchone()

    if row:
        ticker_id = row["id"]
        conn.execute(
            """
            UPDATE tickers
            SET name = ?, sector = ?, sub_sector = ?, is_watchlist = ?,
                watchlist_thesis = ?, alert_min_conviction = ?,
                market_cap_usd = COALESCE(?, market_cap_usd)
            WHERE id = ?
            """,
            (
                name, sector, sub_sector, int(is_watchlist),
                watchlist_thesis, alert_min_conviction, market_cap_usd, ticker_id,
            ),
        )
        return ticker_id

    cursor = conn.execute(
        """
        INSERT INTO tickers (
            symbol, exchange, name, sector, sub_sector,
            is_watchlist, watchlist_thesis, alert_min_conviction,
            market_cap_usd, added_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            symbol, exchange, name, sector, sub_sector,
            int(is_watchlist), watchlist_thesis, alert_min_conviction,
            market_cap_usd, now,
        ),
    )
    return cursor.lastrowid


def get_ticker_by_symbol(
    conn: sqlite3.Connection, symbol: str, exchange: str | None = None
) -> dict | None:
    if exchange:
        row = conn.execute(
            "SELECT * FROM tickers WHERE symbol = ? AND exchange = ?",
            (symbol, exchange),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM tickers WHERE symbol = ?", (symbol,)
        ).fetchone()
    return dict(row) if row else None


def get_ticker_by_id(conn: sqlite3.Connection, ticker_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM tickers WHERE id = ?", (ticker_id,)).fetchone()
    return dict(row) if row else None


def list_watchlist_tickers(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM tickers WHERE is_watchlist = 1 ORDER BY sector, symbol"
    ).fetchall()
    return [dict(r) for r in rows]


def list_all_tickers(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM tickers ORDER BY symbol").fetchall()
    return [dict(r) for r in rows]


def search_tickers_by_text(conn: sqlite3.Connection, text: str) -> list[dict]:
    """Match a symbol or company name appearing in `text`. For ticker resolution from news."""
    text_lower = text.lower()
    candidates = list_all_tickers(conn)
    matches = []
    for t in candidates:
        sym = (t["symbol"] or "").lower()
        nm = (t["name"] or "").lower()
        if sym and (f" {sym} " in f" {text_lower} " or f"({sym})" in text_lower):
            matches.append(t)
            continue
        if nm and len(nm) >= 4 and nm in text_lower:
            matches.append(t)
    return matches


def load_watchlist_to_db(conn: sqlite3.Connection) -> int:
    """Load all tickers from config/watchlist.yaml into the tickers table."""
    watchlist = load_watchlist()
    count = 0
    for t in watchlist:
        upsert_ticker(
            conn,
            symbol=t.symbol,
            exchange=t.exchange,
            name=t.name,
            sector=t.sector,
            sub_sector=t.sub_sector or None,
            is_watchlist=True,
            watchlist_thesis=t.thesis,
            alert_min_conviction=t.alert_min_conviction,
        )
        count += 1
    log.info("watchlist_loaded", count=count)
    return count
