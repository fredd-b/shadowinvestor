"""raw_items store — insert + dedupe + query unprocessed items.

Cross-DB compatible: uses the `raw_items_signals` junction table to answer
"which raw items have not yet been turned into a signal" portably across
SQLite and Postgres (rather than SQLite-specific json_each).
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from fesi.ingest.base import RawItem
from fesi.logging import get_logger

log = get_logger(__name__)


def insert_raw_item(conn: Connection, item: RawItem) -> int | None:
    """Insert one raw item. Returns id, or None if duplicate (skipped silently)."""
    try:
        with conn.begin_nested():
            result = conn.execute(
                text("""
                    INSERT INTO raw_items (
                        source, source_id, fetched_at, published_at,
                        url, title, raw_payload, content_hash
                    )
                    VALUES (
                        :source, :source_id, :fetched_at, :published_at,
                        :url, :title, :raw_payload, :content_hash
                    )
                    RETURNING id
                """),
                {
                    "source": item.source,
                    "source_id": item.source_id,
                    "fetched_at": item.fetched_at.isoformat(),
                    "published_at": item.published_at.isoformat() if item.published_at else None,
                    "url": item.url,
                    "title": item.title,
                    "raw_payload": json.dumps(item.raw_payload),
                    "content_hash": item.content_hash,
                },
            )
            return result.scalar_one()
    except IntegrityError:
        return None


def insert_raw_items(conn: Connection, items: list[RawItem]) -> dict:
    """Bulk insert. Returns {'inserted': N, 'skipped': N}.

    Each insert is its own SAVEPOINT so a single duplicate doesn't poison
    the surrounding transaction (important for Postgres).
    """
    inserted = 0
    skipped = 0
    for item in items:
        # except must be OUTSIDE begin_nested() so the context manager can
        # ROLLBACK TO SAVEPOINT before we swallow the error (Postgres requirement)
        try:
            with conn.begin_nested():
                result = conn.execute(
                    text("""
                        INSERT INTO raw_items (
                            source, source_id, fetched_at, published_at,
                            url, title, raw_payload, content_hash
                        )
                        VALUES (
                            :source, :source_id, :fetched_at, :published_at,
                            :url, :title, :raw_payload, :content_hash
                        )
                        RETURNING id
                    """),
                    {
                        "source": item.source,
                        "source_id": item.source_id,
                        "fetched_at": item.fetched_at.isoformat(),
                        "published_at": item.published_at.isoformat() if item.published_at else None,
                        "url": item.url,
                        "title": item.title,
                        "raw_payload": json.dumps(item.raw_payload),
                        "content_hash": item.content_hash,
                    },
                )
                if result.scalar_one_or_none() is not None:
                    inserted += 1
        except IntegrityError:
            skipped += 1
    log.info("raw_items_insert", inserted=inserted, skipped=skipped, total=len(items))
    return {"inserted": inserted, "skipped": skipped}


def list_recent_raw_items(
    conn: Connection,
    since: datetime | None = None,
    source: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    sql = "SELECT * FROM raw_items WHERE 1=1"
    params: dict = {}
    if since is not None:
        sql += " AND fetched_at >= :since"
        params["since"] = since.isoformat()
    if source is not None:
        sql += " AND source = :source"
        params["source"] = source
    sql += " ORDER BY fetched_at DESC"
    if limit is not None:
        sql += " LIMIT :limit"
        params["limit"] = limit
    rows = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def get_unprocessed_raw_items(
    conn: Connection, since: datetime
) -> list[dict]:
    """Raw items fetched since X that haven't been linked to a signal yet.

    Uses the `raw_items_signals` junction table for cross-DB portability.
    A raw item is "unprocessed" if no row in the junction table references it.
    """
    rows = conn.execute(
        text("""
            SELECT r.* FROM raw_items r
            LEFT JOIN raw_items_signals ris ON r.id = ris.raw_item_id
            WHERE r.fetched_at >= :since AND ris.raw_item_id IS NULL
            ORDER BY r.fetched_at ASC
        """),
        {"since": since.isoformat()},
    ).mappings().all()
    return [dict(r) for r in rows]


def count_raw_items_by_source(conn: Connection) -> dict[str, int]:
    rows = conn.execute(
        text("SELECT source, COUNT(*) AS cnt FROM raw_items GROUP BY source")
    ).mappings().all()
    return {r["source"]: r["cnt"] for r in rows}


def latest_fetch_per_source(conn: Connection) -> dict[str, str]:
    rows = conn.execute(
        text("SELECT source, MAX(fetched_at) AS last FROM raw_items GROUP BY source")
    ).mappings().all()
    return {r["source"]: r["last"] for r in rows}
