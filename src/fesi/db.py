"""Database connection, schema bootstrap, and migration runner.

Phase 0/1 uses SQLite with raw SQL migrations in `src/fesi/migrations/*.sql`.
Phase 2+ migrates to Postgres on Railway via Alembic if/when complexity demands it.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from fesi.config import get_settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def get_db_path() -> Path:
    """Resolve the SQLite db path from settings."""
    url = get_settings().database_url
    if not url.startswith("sqlite:///"):
        raise ValueError(
            f"Only sqlite:/// URLs are supported in Phase 0/1, got {url!r}"
        )
    raw = url.removeprefix("sqlite:///")
    # Allow both relative ./data/fesi.db and absolute /Users/.../fesi.db
    return Path(raw).resolve()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Context-managed connection with FK enforcement and commit-on-success."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _migrations (
            id TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )


def _applied_migrations(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT id FROM _migrations").fetchall()
    return {r["id"] for r in rows}


def init_db() -> dict[str, list[str]]:
    """Apply any unapplied migrations. Returns a summary dict."""
    applied: list[str] = []
    skipped: list[str] = []
    with connect() as conn:
        _ensure_migrations_table(conn)
        already = _applied_migrations(conn)
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            mig_id = path.name
            if mig_id in already:
                skipped.append(mig_id)
                continue
            sql = path.read_text()
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO _migrations (id, applied_at) VALUES (?, datetime('now'))",
                (mig_id,),
            )
            applied.append(mig_id)
    return {"applied": applied, "skipped": skipped}
