"""research_topics store — CRUD for user-created research queries."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection

from fesi.logging import get_logger

log = get_logger(__name__)

MAX_ACTIVE_TOPICS = 8


def create_topic(
    conn: Connection,
    *,
    name: str,
    query_template: str,
    sector_hint: str | None = None,
    schedule: str = "daily",
) -> int:
    """Create a research topic. Enforces max active topics."""
    if count_active_topics(conn) >= MAX_ACTIVE_TOPICS:
        raise ValueError(f"Maximum {MAX_ACTIVE_TOPICS} active topics allowed")
    now = datetime.now(timezone.utc).isoformat()
    result = conn.execute(
        text("""
            INSERT INTO research_topics (
                name, query_template, sector_hint, schedule,
                is_active, created_at, updated_at, total_items_found
            )
            VALUES (
                :name, :query_template, :sector_hint, :schedule,
                1, :now, :now, 0
            )
            RETURNING id
        """),
        {
            "name": name,
            "query_template": query_template,
            "sector_hint": sector_hint,
            "schedule": schedule,
            "now": now,
        },
    )
    return result.scalar_one()


def update_topic(conn: Connection, topic_id: int, **fields: str | int | None) -> None:
    """Update specific fields on a topic."""
    allowed = {"name", "query_template", "sector_hint", "schedule", "is_active"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["id"] = topic_id
    conn.execute(text(f"UPDATE research_topics SET {set_clause} WHERE id = :id"), updates)


def delete_topic(conn: Connection, topic_id: int) -> None:
    conn.execute(text("DELETE FROM research_topics WHERE id = :id"), {"id": topic_id})


def get_topic_by_id(conn: Connection, topic_id: int) -> dict | None:
    row = conn.execute(
        text("SELECT * FROM research_topics WHERE id = :id"), {"id": topic_id}
    ).mappings().first()
    return dict(row) if row else None


def list_all_topics(conn: Connection) -> list[dict]:
    rows = conn.execute(
        text("SELECT * FROM research_topics ORDER BY created_at DESC")
    ).mappings().all()
    return [dict(r) for r in rows]


def list_active_topics(conn: Connection) -> list[dict]:
    rows = conn.execute(
        text("SELECT * FROM research_topics WHERE is_active = 1 ORDER BY name")
    ).mappings().all()
    return [dict(r) for r in rows]


def count_active_topics(conn: Connection) -> int:
    row = conn.execute(
        text("SELECT COUNT(*) AS cnt FROM research_topics WHERE is_active = 1")
    ).mappings().first()
    return int(row["cnt"]) if row else 0


def get_topics_due_for_run(conn: Connection, *, run_label: str) -> list[dict]:
    """Return topics that should run for the given scheduler label.

    - morning_catchup: all active topics (daily + every_run)
    - other labels: only 'every_run' topics
    """
    if run_label == "morning_catchup":
        return list_active_topics(conn)
    rows = conn.execute(
        text("""
            SELECT * FROM research_topics
            WHERE is_active = 1 AND schedule = 'every_run'
            ORDER BY name
        """)
    ).mappings().all()
    return [dict(r) for r in rows]


def mark_topic_run(conn: Connection, topic_id: int, items_found: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        text("""
            UPDATE research_topics
            SET last_run_at = :now, total_items_found = total_items_found + :found, updated_at = :now
            WHERE id = :id
        """),
        {"now": now, "found": items_found, "id": topic_id},
    )
