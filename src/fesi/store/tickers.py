"""Tickers store — load watchlist into DB, upsert, lookup by symbol."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection

from fesi.config import load_watchlist
from fesi.logging import get_logger

log = get_logger(__name__)


def upsert_ticker(
    conn: Connection,
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
        text("SELECT id FROM tickers WHERE symbol = :symbol AND exchange = :exchange"),
        {"symbol": symbol, "exchange": exchange},
    ).mappings().first()

    if row:
        ticker_id = row["id"]
        conn.execute(
            text("""
                UPDATE tickers
                SET name = :name,
                    sector = :sector,
                    sub_sector = :sub_sector,
                    is_watchlist = :is_watchlist,
                    watchlist_thesis = :watchlist_thesis,
                    alert_min_conviction = :alert_min_conviction,
                    market_cap_usd = COALESCE(:market_cap_usd, market_cap_usd)
                WHERE id = :id
            """),
            {
                "name": name,
                "sector": sector,
                "sub_sector": sub_sector,
                "is_watchlist": int(is_watchlist),
                "watchlist_thesis": watchlist_thesis,
                "alert_min_conviction": alert_min_conviction,
                "market_cap_usd": market_cap_usd,
                "id": ticker_id,
            },
        )
        return ticker_id

    result = conn.execute(
        text("""
            INSERT INTO tickers (
                symbol, exchange, name, sector, sub_sector,
                is_watchlist, watchlist_thesis, alert_min_conviction,
                market_cap_usd, added_at, lifecycle_status, added_by
            )
            VALUES (
                :symbol, :exchange, :name, :sector, :sub_sector,
                :is_watchlist, :watchlist_thesis, :alert_min_conviction,
                :market_cap_usd, :added_at, :lifecycle_status, :added_by
            )
            RETURNING id
        """),
        {
            "symbol": symbol,
            "exchange": exchange,
            "name": name,
            "sector": sector,
            "sub_sector": sub_sector,
            "is_watchlist": int(is_watchlist),
            "watchlist_thesis": watchlist_thesis,
            "alert_min_conviction": alert_min_conviction,
            "market_cap_usd": market_cap_usd,
            "added_at": now,
            "lifecycle_status": "monitoring",
            "added_by": "yaml",
        },
    )
    return result.scalar_one()


def get_ticker_by_symbol(
    conn: Connection, symbol: str, exchange: str | None = None
) -> dict | None:
    if exchange:
        row = conn.execute(
            text("SELECT * FROM tickers WHERE symbol = :symbol AND exchange = :exchange"),
            {"symbol": symbol, "exchange": exchange},
        ).mappings().first()
    else:
        row = conn.execute(
            text("SELECT * FROM tickers WHERE symbol = :symbol"),
            {"symbol": symbol},
        ).mappings().first()
    return dict(row) if row else None


def get_ticker_by_id(conn: Connection, ticker_id: int) -> dict | None:
    row = conn.execute(
        text("SELECT * FROM tickers WHERE id = :id"),
        {"id": ticker_id},
    ).mappings().first()
    return dict(row) if row else None


def list_watchlist_tickers(conn: Connection) -> list[dict]:
    rows = conn.execute(
        text("SELECT * FROM tickers WHERE is_watchlist = 1 ORDER BY sector, symbol")
    ).mappings().all()
    return [dict(r) for r in rows]


def list_all_tickers(conn: Connection) -> list[dict]:
    rows = conn.execute(
        text("SELECT * FROM tickers ORDER BY symbol")
    ).mappings().all()
    return [dict(r) for r in rows]


def search_tickers_by_text(conn: Connection, search_text: str) -> list[dict]:
    """Match a symbol or company name appearing in `search_text`."""
    text_lower = search_text.lower()
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


def load_watchlist_to_db(conn: Connection) -> int:
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


# ============================================================================
# Phase 2.7: Dynamic watchlist CRUD
# ============================================================================

VALID_LIFECYCLE = {"monitoring", "considering", "invested", "paused", "archived"}


def add_ticker_to_watchlist(
    conn: Connection,
    *,
    symbol: str,
    exchange: str,
    name: str,
    sector: str,
    thesis: str,
    sub_sector: str | None = None,
    alert_min_conviction: int = 3,
) -> int:
    """Add a user-discovered ticker to the watchlist. Returns ticker id."""
    now = datetime.now(timezone.utc).isoformat()
    result = conn.execute(
        text("""
            INSERT INTO tickers (
                symbol, exchange, name, sector, sub_sector,
                is_watchlist, watchlist_thesis, alert_min_conviction,
                market_cap_usd, added_at, lifecycle_status, added_by, updated_at
            )
            VALUES (
                :symbol, :exchange, :name, :sector, :sub_sector,
                1, :thesis, :alert_min_conviction,
                NULL, :now, 'monitoring', 'user', :now
            )
            RETURNING id
        """),
        {
            "symbol": symbol.upper(),
            "exchange": exchange.upper(),
            "name": name,
            "sector": sector,
            "sub_sector": sub_sector,
            "thesis": thesis,
            "alert_min_conviction": alert_min_conviction,
            "now": now,
        },
    )
    return result.scalar_one()


def update_ticker_status(
    conn: Connection, ticker_id: int, status: str
) -> None:
    """Change lifecycle status. Validates against allowed values."""
    if status not in VALID_LIFECYCLE:
        raise ValueError(f"Invalid lifecycle_status: {status}")
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        text("UPDATE tickers SET lifecycle_status = :status, updated_at = :now WHERE id = :id"),
        {"status": status, "now": now, "id": ticker_id},
    )


def update_ticker_thesis(conn: Connection, ticker_id: int, thesis: str) -> None:
    """Edit a ticker's watchlist thesis."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        text("UPDATE tickers SET watchlist_thesis = :thesis, updated_at = :now WHERE id = :id"),
        {"thesis": thesis, "now": now, "id": ticker_id},
    )


def remove_ticker_from_watchlist(conn: Connection, ticker_id: int) -> None:
    """Archive a ticker and remove from active watchlist."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        text("""
            UPDATE tickers
            SET is_watchlist = 0, lifecycle_status = 'archived', updated_at = :now
            WHERE id = :id
        """),
        {"now": now, "id": ticker_id},
    )


def list_tickers_for_daily_research(conn: Connection) -> list[dict]:
    """Tickers with lifecycle 'invested' or 'considering' — get daily Perplexity queries."""
    rows = conn.execute(
        text("""
            SELECT * FROM tickers
            WHERE is_watchlist = 1
            AND lifecycle_status IN ('invested', 'considering')
            ORDER BY symbol
        """)
    ).mappings().all()
    return [dict(r) for r in rows]
