"""Digests store — journal of every digest delivered."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def insert_digest(
    conn: sqlite3.Connection,
    *,
    window_start: datetime,
    window_end: datetime,
    signal_count: int,
    decision_count: int,
    delivered_via: str,
    markdown_body: str,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO digests (
            sent_at, scan_window_start, scan_window_end,
            signal_count, decision_count, delivered_via, markdown_body
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now, window_start.isoformat(), window_end.isoformat(),
            signal_count, decision_count, delivered_via, markdown_body,
        ),
    )
    return cursor.lastrowid


def list_recent_digests(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    rows = conn.execute(
        "SELECT id, sent_at, scan_window_start, scan_window_end, "
        "signal_count, decision_count, delivered_via "
        "FROM digests ORDER BY sent_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_digest_by_id(conn: sqlite3.Connection, digest_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM digests WHERE id = ?", (digest_id,)
    ).fetchone()
    return dict(row) if row else None
