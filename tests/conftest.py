"""Shared pytest fixtures.

These fixtures give every test a clean DB with the watchlist loaded and
provide helpers for inserting synthetic raw_items / signals so unit tests
don't need to hit any real APIs.
"""
from __future__ import annotations

import importlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Create a fresh SQLite DB, apply migrations, load watchlist. Returns the path."""
    db_file = tmp_path / "fesi_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")

    # Reload config + db modules so they pick up the new env var
    import fesi.config
    import fesi.db
    importlib.reload(fesi.config)
    importlib.reload(fesi.db)

    from fesi.db import connect, init_db
    from fesi.store.tickers import load_watchlist_to_db

    init_db()
    with connect() as conn:
        load_watchlist_to_db(conn)

    return db_file


@pytest.fixture
def db_conn(tmp_db):
    """A live connection to the test DB. Auto-closed."""
    from fesi.db import connect
    with connect() as conn:
        yield conn


@pytest.fixture
def make_raw_item():
    """Factory: produce a RawItem with sensible defaults."""
    from fesi.ingest.base import RawItem

    counter = {"i": 0}

    def _make(
        *,
        title: str,
        source: str = "pr_newswire",
        body: str = "",
        url: str | None = None,
        published_at: datetime | None = None,
    ) -> RawItem:
        counter["i"] += 1
        url = url or f"https://example.com/news/{counter['i']}"
        if published_at is None:
            published_at = datetime.now(timezone.utc)
        return RawItem(
            source=source,
            source_id=f"test-{counter['i']}",
            fetched_at=datetime.now(timezone.utc),
            published_at=published_at,
            url=url,
            title=title,
            raw_payload={"title": title, "description": body, "url": url},
            content_hash=RawItem.make_content_hash(title, url, published_at),
        )

    return _make


@pytest.fixture
def insert_raw_item_dict(db_conn):
    """Insert a raw_item directly (bypassing the IngestAdapter type)."""
    counter = {"i": 0}

    def _insert(
        *,
        title: str,
        source: str = "pr_newswire",
        body: str = "",
        url: str | None = None,
    ) -> int:
        counter["i"] += 1
        now = datetime.now(timezone.utc)
        url = url or f"https://example.com/{counter['i']}"
        cursor = db_conn.execute(
            """
            INSERT INTO raw_items (
                source, source_id, fetched_at, published_at,
                url, title, raw_payload, content_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source,
                f"raw-{counter['i']}",
                now.isoformat(),
                now.isoformat(),
                url,
                title,
                json.dumps({"title": title, "description": body, "url": url}),
                f"hash-{counter['i']}",
            ),
        )
        return cursor.lastrowid

    return _insert
