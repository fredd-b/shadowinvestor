"""positions store — open, close, track P&L for shadow/paper/live positions."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection

from fesi.logging import get_logger
from fesi.store.prices import get_latest_price

log = get_logger(__name__)


def open_position(
    conn: Connection,
    *,
    ticker_id: int,
    mode: str,
    entry_decision_id: int | None,
    entry_price: float,
    shares: int,
    sector: str | None = None,
    catalyst_type: str | None = None,
    thesis: str | None = None,
) -> int:
    """Open a new position. Returns position id."""
    now = datetime.now(timezone.utc).isoformat()
    cost_basis = entry_price * shares
    result = conn.execute(
        text("""
            INSERT INTO positions (
                ticker_id, mode, status, opened_at,
                entry_decision_id, entry_price,
                shares_held, shares_sold, cost_basis_usd,
                realized_pnl_usd, unrealized_pnl_usd,
                current_price, last_price_at,
                sector, catalyst_type, thesis_at_entry
            )
            VALUES (
                :ticker_id, :mode, 'open', :now,
                :entry_decision_id, :entry_price,
                :shares, 0, :cost_basis,
                0, 0,
                :entry_price, :now,
                :sector, :catalyst_type, :thesis
            )
            RETURNING id
        """),
        {
            "ticker_id": ticker_id,
            "mode": mode,
            "now": now,
            "entry_decision_id": entry_decision_id,
            "entry_price": entry_price,
            "shares": shares,
            "cost_basis": cost_basis,
            "sector": sector,
            "catalyst_type": catalyst_type,
            "thesis": thesis,
        },
    )
    pid = result.scalar_one()
    log.info("position_opened", id=pid, ticker_id=ticker_id, entry=entry_price, shares=shares)
    return pid


def get_position_by_id(conn: Connection, position_id: int) -> dict | None:
    row = conn.execute(
        text("""
            SELECT p.*, t.symbol AS ticker_symbol, t.name AS ticker_name
            FROM positions p
            LEFT JOIN tickers t ON p.ticker_id = t.id
            WHERE p.id = :id
        """),
        {"id": position_id},
    ).mappings().first()
    return dict(row) if row else None


def get_open_position_for_ticker(
    conn: Connection, ticker_id: int, mode: str = "shadow"
) -> dict | None:
    """Find the open/partial position for a ticker (if any)."""
    row = conn.execute(
        text("""
            SELECT p.*, t.symbol AS ticker_symbol, t.name AS ticker_name
            FROM positions p
            LEFT JOIN tickers t ON p.ticker_id = t.id
            WHERE p.ticker_id = :tid AND p.mode = :mode
            AND p.status IN ('open', 'partial_closed')
            ORDER BY p.opened_at DESC LIMIT 1
        """),
        {"tid": ticker_id, "mode": mode},
    ).mappings().first()
    return dict(row) if row else None


def list_positions(
    conn: Connection,
    *,
    mode: str = "shadow",
    status: str | None = None,
) -> list[dict]:
    """List positions with ticker info. Filter by status if given."""
    sql = """
        SELECT p.*, t.symbol AS ticker_symbol, t.name AS ticker_name, t.exchange AS ticker_exchange
        FROM positions p
        LEFT JOIN tickers t ON p.ticker_id = t.id
        WHERE p.mode = :mode
    """
    params: dict = {"mode": mode}
    if status:
        sql += " AND p.status = :status"
        params["status"] = status
    sql += " ORDER BY p.opened_at DESC"
    rows = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def close_position(
    conn: Connection,
    position_id: int,
    *,
    exit_price: float,
    shares_to_sell: int | None = None,
    exit_decision_id: int | None = None,
) -> dict:
    """Close (fully or partially) a position. Returns updated position."""
    pos = get_position_by_id(conn, position_id)
    if pos is None:
        raise ValueError(f"Position {position_id} not found")

    remaining = pos["shares_held"] - pos["shares_sold"]
    if remaining <= 0:
        raise ValueError(f"Position {position_id} has no remaining shares")

    if shares_to_sell is not None:
        if shares_to_sell <= 0:
            raise ValueError("shares_to_sell must be positive")
        if shares_to_sell > remaining:
            raise ValueError(f"Cannot sell {shares_to_sell}, only {remaining} remaining")
    sell_qty = shares_to_sell if shares_to_sell is not None else remaining
    is_full_close = (sell_qty >= remaining)

    realized = (exit_price - pos["entry_price"]) * sell_qty
    new_shares_sold = pos["shares_sold"] + sell_qty
    new_realized = (pos["realized_pnl_usd"] or 0) + realized
    new_status = "closed" if is_full_close else "partial_closed"
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        text("""
            UPDATE positions
            SET status = :status,
                shares_sold = :shares_sold,
                realized_pnl_usd = :realized,
                exit_price = :exit_price,
                exit_decision_id = :exit_did,
                closed_at = CASE WHEN :status = 'closed' THEN :now ELSE closed_at END
            WHERE id = :id
        """),
        {
            "status": new_status,
            "shares_sold": new_shares_sold,
            "realized": new_realized,
            "exit_price": exit_price,
            "exit_did": exit_decision_id,
            "now": now,
            "id": position_id,
        },
    )
    log.info("position_closed", id=position_id, status=new_status, sold=sell_qty, realized=realized)
    return get_position_by_id(conn, position_id)


def update_unrealized_pnl(
    conn: Connection, position_id: int, current_price: float
) -> None:
    """Update a position's unrealized P&L based on current price."""
    pos = get_position_by_id(conn, position_id)
    if pos is None:
        return
    remaining = pos["shares_held"] - pos["shares_sold"]
    unrealized = (current_price - pos["entry_price"]) * remaining
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        text("""
            UPDATE positions
            SET unrealized_pnl_usd = :unrealized,
                current_price = :price,
                last_price_at = :now
            WHERE id = :id
        """),
        {"unrealized": unrealized, "price": current_price, "now": now, "id": position_id},
    )


def update_all_unrealized(conn: Connection, mode: str = "shadow") -> dict:
    """Batch update unrealized P&L for all open positions."""
    positions = list_positions(conn, mode=mode, status="open")
    positions += list_positions(conn, mode=mode, status="partial_closed")
    updated = 0
    total_unrealized = 0.0
    for pos in positions:
        latest = get_latest_price(conn, pos["ticker_id"])
        if latest and latest.get("close"):
            price = float(latest["close"])
            update_unrealized_pnl(conn, pos["id"], price)
            remaining = pos["shares_held"] - pos["shares_sold"]
            total_unrealized += (price - pos["entry_price"]) * remaining
            updated += 1
    log.info("unrealized_updated", updated=updated, total=total_unrealized)
    return {"updated": updated, "total_unrealized": round(total_unrealized, 2)}


def get_portfolio_summary(conn: Connection, mode: str = "shadow") -> dict:
    """Aggregate portfolio metrics from positions."""
    row = conn.execute(
        text("""
            SELECT
                COALESCE(SUM(CASE WHEN status IN ('open','partial_closed') THEN cost_basis_usd ELSE 0 END), 0) AS total_invested,
                COALESCE(SUM(CASE WHEN status IN ('open','partial_closed') THEN unrealized_pnl_usd ELSE 0 END), 0) AS total_unrealized,
                COALESCE(SUM(realized_pnl_usd), 0) AS total_realized,
                COUNT(CASE WHEN status IN ('open','partial_closed') THEN 1 END) AS open_count,
                COUNT(CASE WHEN status = 'closed' THEN 1 END) AS closed_count,
                COUNT(CASE WHEN status = 'closed' AND realized_pnl_usd > 0 THEN 1 END) AS win_count
            FROM positions
            WHERE mode = :mode
        """),
        {"mode": mode},
    ).mappings().first()
    r = dict(row) if row else {}
    closed = r.get("closed_count", 0)
    wins = r.get("win_count", 0)
    return {
        "total_invested": r.get("total_invested", 0),
        "total_unrealized": r.get("total_unrealized", 0),
        "total_realized": r.get("total_realized", 0),
        "open_count": r.get("open_count", 0),
        "closed_count": closed,
        "win_rate": round(wins / closed, 2) if closed > 0 else None,
    }
