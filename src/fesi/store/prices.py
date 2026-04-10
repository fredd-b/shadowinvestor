"""Prices store — yfinance OHLCV cache."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from fesi.logging import get_logger
from fesi.store.tickers import get_ticker_by_symbol

log = get_logger(__name__)


def insert_price_bar(
    conn: Connection,
    *,
    ticker_id: int,
    date: str,
    open_: float | None,
    high: float | None,
    low: float | None,
    close: float,
    volume: int | None,
    source: str = "yfinance",
) -> bool:
    """Insert one OHLCV bar. Returns True if inserted, False if duplicate."""
    try:
        with conn.begin_nested():
            conn.execute(
                text("""
                    INSERT INTO prices (
                        ticker_id, date, open, high, low, close, volume, source
                    )
                    VALUES (
                        :ticker_id, :date, :open, :high, :low, :close, :volume, :source
                    )
                """),
                {
                    "ticker_id": ticker_id,
                    "date": date,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                    "source": source,
                },
            )
            return True
    except IntegrityError:
        return False


def get_latest_price(conn: Connection, ticker_id: int) -> dict | None:
    row = conn.execute(
        text("""
            SELECT * FROM prices
            WHERE ticker_id = :ticker_id
            ORDER BY date DESC
            LIMIT 1
        """),
        {"ticker_id": ticker_id},
    ).mappings().first()
    return dict(row) if row else None


def get_price_on_or_after(
    conn: Connection, ticker_id: int, date: str
) -> dict | None:
    row = conn.execute(
        text("""
            SELECT * FROM prices
            WHERE ticker_id = :ticker_id AND date >= :date
            ORDER BY date ASC
            LIMIT 1
        """),
        {"ticker_id": ticker_id, "date": date},
    ).mappings().first()
    return dict(row) if row else None


def get_price_history(
    conn: Connection,
    ticker_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    sql = "SELECT * FROM prices WHERE ticker_id = :ticker_id"
    params: dict = {"ticker_id": ticker_id}
    if start_date:
        sql += " AND date >= :start_date"
        params["start_date"] = start_date
    if end_date:
        sql += " AND date <= :end_date"
        params["end_date"] = end_date
    sql += " ORDER BY date ASC"
    rows = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def fetch_yfinance_history(
    conn: Connection,
    symbol: str,
    *,
    days: int = 90,
    exchange: str | None = None,
) -> dict:
    """Fetch daily OHLCV from yfinance and cache to the prices table.

    Uses `yf.Ticker(symbol).history(period=...)` which returns clean
    single-level columns regardless of yfinance version.
    """
    import yfinance as yf

    ticker = get_ticker_by_symbol(conn, symbol, exchange)
    if ticker is None:
        log.warning("price_fetch_unknown_ticker", symbol=symbol)
        return {"inserted": 0, "skipped": 0, "symbol": symbol, "error": "unknown_ticker"}

    period = "1mo"
    if days > 30:
        period = "3mo"
    if days > 90:
        period = "6mo"
    if days > 180:
        period = "1y"
    if days > 365:
        period = "2y"

    try:
        yf_ticker = yf.Ticker(symbol)
        df = yf_ticker.history(period=period, auto_adjust=False)
    except Exception as e:
        log.warning("yfinance_failed", symbol=symbol, error=str(e))
        return {"inserted": 0, "skipped": 0, "symbol": symbol, "error": str(e)}

    if df is None or df.empty:
        return {"inserted": 0, "skipped": 0, "symbol": symbol}

    inserted = 0
    skipped = 0
    for date_idx, row in df.iterrows():
        try:
            date_str = date_idx.strftime("%Y-%m-%d")
            open_ = float(row.get("Open")) if "Open" in df.columns else None
            high = float(row.get("High")) if "High" in df.columns else None
            low = float(row.get("Low")) if "Low" in df.columns else None
            close_val = row.get("Close")
            if close_val is None:
                continue
            close = float(close_val)
            volume = int(row.get("Volume")) if "Volume" in df.columns and row.get("Volume") is not None else None
        except (ValueError, TypeError):
            continue

        if insert_price_bar(
            conn,
            ticker_id=ticker["id"],
            date=date_str,
            open_=open_,
            high=high,
            low=low,
            close=close,
            volume=volume,
        ):
            inserted += 1
        else:
            skipped += 1

    log.info("price_fetch_done", symbol=symbol, inserted=inserted, skipped=skipped)
    return {"inserted": inserted, "skipped": skipped, "symbol": symbol}
