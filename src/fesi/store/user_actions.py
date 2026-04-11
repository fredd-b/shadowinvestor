"""user_actions store — append-only audit trail of every action Fred takes."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection

from fesi.logging import get_logger

log = get_logger(__name__)

VALID_ACTION_TYPES = {
    "invest", "skip", "watch_pullback", "add_watchlist",
    "remove_watchlist", "edit_thesis", "change_status",
    "sell", "override_decision",
}


def insert_user_action(
    conn: Connection,
    *,
    action_type: str,
    target_type: str,
    target_id: int,
    note: str | None = None,
) -> int:
    """Record a user action. Returns the action id."""
    if action_type not in VALID_ACTION_TYPES:
        raise ValueError(f"Invalid action_type: {action_type}")
    now = datetime.now(timezone.utc).isoformat()
    result = conn.execute(
        text("""
            INSERT INTO user_actions (action_type, target_type, target_id, note, created_at)
            VALUES (:action_type, :target_type, :target_id, :note, :created_at)
            RETURNING id
        """),
        {
            "action_type": action_type,
            "target_type": target_type,
            "target_id": target_id,
            "note": note,
            "created_at": now,
        },
    )
    return result.scalar_one()


def list_actions_for_target(
    conn: Connection, target_type: str, target_id: int
) -> list[dict]:
    """Get all actions for a specific signal/ticker/position."""
    rows = conn.execute(
        text("""
            SELECT * FROM user_actions
            WHERE target_type = :target_type AND target_id = :target_id
            ORDER BY created_at DESC
        """),
        {"target_type": target_type, "target_id": target_id},
    ).mappings().all()
    return [dict(r) for r in rows]


def list_recent_actions(conn: Connection, limit: int = 50) -> list[dict]:
    """Get the most recent user actions (activity feed)."""
    rows = conn.execute(
        text("SELECT * FROM user_actions ORDER BY created_at DESC LIMIT :limit"),
        {"limit": limit},
    ).mappings().all()
    return [dict(r) for r in rows]
