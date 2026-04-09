"""Digests store — journal of every digest delivered."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection


def insert_digest(
    conn: Connection,
    *,
    window_start: datetime,
    window_end: datetime,
    signal_count: int,
    decision_count: int,
    delivered_via: str,
    markdown_body: str,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    result = conn.execute(
        text("""
            INSERT INTO digests (
                sent_at, scan_window_start, scan_window_end,
                signal_count, decision_count, delivered_via, markdown_body
            )
            VALUES (
                :sent_at, :ws, :we, :sc, :dc, :via, :body
            )
            RETURNING id
        """),
        {
            "sent_at": now,
            "ws": window_start.isoformat(),
            "we": window_end.isoformat(),
            "sc": signal_count,
            "dc": decision_count,
            "via": delivered_via,
            "body": markdown_body,
        },
    )
    return result.scalar_one()


def list_recent_digests(conn: Connection, limit: int = 10) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT id, sent_at, scan_window_start, scan_window_end,
                   signal_count, decision_count, delivered_via
            FROM digests
            ORDER BY sent_at DESC
            LIMIT :limit
        """),
        {"limit": limit},
    ).mappings().all()
    return [dict(r) for r in rows]


def get_digest_by_id(conn: Connection, digest_id: int) -> dict | None:
    row = conn.execute(
        text("SELECT * FROM digests WHERE id = :id"),
        {"id": digest_id},
    ).mappings().first()
    return dict(row) if row else None
