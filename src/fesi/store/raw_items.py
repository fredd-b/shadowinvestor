"""raw_items store — insert + dedupe + query unprocessed items."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from fesi.ingest.base import RawItem
from fesi.logging import get_logger

log = get_logger(__name__)


def insert_raw_item(conn: sqlite3.Connection, item: RawItem) -> int | None:
    """Insert one raw item. Returns id, or None if duplicate (skipped silently)."""
    try:
        cursor = conn.execute(
            """
            INSERT INTO raw_items (
                source, source_id, fetched_at, published_at,
                url, title, raw_payload, content_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.source,
                item.source_id,
                item.fetched_at.isoformat(),
                item.published_at.isoformat() if item.published_at else None,
                item.url,
                item.title,
                json.dumps(item.raw_payload),
                item.content_hash,
            ),
        )
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None


def insert_raw_items(conn: sqlite3.Connection, items: list[RawItem]) -> dict:
    """Bulk insert. Returns {'inserted': N, 'skipped': N}."""
    inserted = 0
    skipped = 0
    for item in items:
        if insert_raw_item(conn, item) is not None:
            inserted += 1
        else:
            skipped += 1
    log.info("raw_items_insert", inserted=inserted, skipped=skipped, total=len(items))
    return {"inserted": inserted, "skipped": skipped}


def list_recent_raw_items(
    conn: sqlite3.Connection,
    since: datetime | None = None,
    source: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    sql = "SELECT * FROM raw_items WHERE 1=1"
    args: list = []
    if since is not None:
        sql += " AND fetched_at >= ?"
        args.append(since.isoformat())
    if source is not None:
        sql += " AND source = ?"
        args.append(source)
    sql += " ORDER BY fetched_at DESC"
    if limit is not None:
        sql += " LIMIT ?"
        args.append(limit)
    rows = conn.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def get_unprocessed_raw_items(
    conn: sqlite3.Connection, since: datetime
) -> list[dict]:
    """Raw items fetched since X that haven't been linked to a signal yet.

    Uses the JSON `raw_item_ids` column on signals via SQLite's json_each.
    Requires SQLite >= 3.38 (macOS ships with this).
    """
    rows = conn.execute(
        """
        SELECT r.* FROM raw_items r
        WHERE r.fetched_at >= ?
          AND r.id NOT IN (
              SELECT CAST(je.value AS INTEGER)
              FROM signals s, json_each(s.raw_item_ids) je
              WHERE s.raw_item_ids IS NOT NULL AND s.raw_item_ids != '[]'
          )
        ORDER BY r.fetched_at ASC
        """,
        (since.isoformat(),),
    ).fetchall()
    return [dict(r) for r in rows]


def count_raw_items_by_source(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT source, COUNT(*) as cnt FROM raw_items GROUP BY source"
    ).fetchall()
    return {r["source"]: r["cnt"] for r in rows}


def latest_fetch_per_source(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute(
        "SELECT source, MAX(fetched_at) as last FROM raw_items GROUP BY source"
    ).fetchall()
    return {r["source"]: r["last"] for r in rows}
