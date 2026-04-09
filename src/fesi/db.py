"""Database engine + context-managed connection for FESI.

Phase 2: SQLAlchemy 2.0 core. Same code path for SQLite (dev) and Postgres
(Railway prod). Schema definitions live in `src/fesi/store/schema.py`.

`init_db()` calls `metadata.create_all(engine)` which is idempotent and
dialect-aware, so this works for both backends without separate migration
SQL files.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import Engine, create_engine, inspect
from sqlalchemy.engine import Connection

from fesi.config import get_settings
from fesi.logging import get_logger

log = get_logger(__name__)

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return (and lazily build) the SQLAlchemy Engine."""
    global _engine
    if _engine is None:
        url = _normalize_url(get_settings().database_url)
        connect_args: dict = {}
        if url.startswith("sqlite"):
            # Cooperate with SQLite default thread mode
            connect_args = {"check_same_thread": False}
        _engine = create_engine(
            url,
            future=True,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        log.info("engine_created", url=_redact(url))
    return _engine


def reset_engine() -> None:
    """Tear down the cached engine. Used by tests after monkeypatching DATABASE_URL."""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def _normalize_url(url: str) -> str:
    """Resolve relative SQLite paths so the file lands in the project's data/ dir."""
    if url.startswith("sqlite:///./"):
        project_root = Path(__file__).parent.parent.parent
        relative = url.removeprefix("sqlite:///./")
        absolute = project_root / relative
        absolute.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{absolute}"
    if url.startswith("sqlite:///"):
        path = Path(url.removeprefix("sqlite:///"))
        if path.is_absolute() or path.parent != Path("."):
            path.parent.mkdir(parents=True, exist_ok=True)
    return url


def _redact(url: str) -> str:
    """Hide credentials in log output."""
    if "@" not in url:
        return url
    try:
        scheme, rest = url.split("://", 1)
        _, host = rest.rsplit("@", 1)
        return f"{scheme}://***@{host}"
    except ValueError:
        return url


@contextmanager
def connect() -> Iterator[Connection]:
    """Context-managed connection.

    Auto-commits on success, rolls back on exception. Each `with connect()`
    block is one transaction.
    """
    engine = get_engine()
    with engine.begin() as conn:
        yield conn


def init_db() -> dict:
    """Create all tables. Idempotent — safe to call repeatedly.

    Returns: {'created': [tables created this call], 'existing': [tables
    that already existed]}
    """
    from fesi.store.schema import metadata
    engine = get_engine()
    inspector = inspect(engine)
    existing_before = set(inspector.get_table_names())
    metadata.create_all(engine)
    existing_after = set(inspect(engine).get_table_names())
    created = sorted(existing_after - existing_before)
    existing = sorted(existing_before & {t.name for t in metadata.sorted_tables})
    log.info("init_db_done", created=created, existing=existing)
    return {"created": created, "existing": existing}


def get_db_path() -> Path:
    """For SQLite engines: return the file path. Raises for other dialects."""
    url = _normalize_url(get_settings().database_url)
    if not url.startswith("sqlite:///"):
        raise ValueError(f"get_db_path() only valid for SQLite, got {url!r}")
    return Path(url.removeprefix("sqlite:///")).resolve()
