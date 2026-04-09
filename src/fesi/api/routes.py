"""All FastAPI routes — single file for personal-scale clarity."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from fesi import __version__
from fesi.api import schemas
from fesi.config import get_settings, load_sources
from fesi.db import connect
from fesi.intelligence.llm import has_anthropic
from fesi.logging import get_logger
from fesi.store.decisions import (
    count_concurrent_buys,
    get_sector_exposure,
    list_recent_decisions,
    total_deployed_capital,
    total_deployed_this_month,
)
from fesi.store.digests import get_digest_by_id, list_recent_digests
from fesi.store.raw_items import (
    count_raw_items_by_source,
    latest_fetch_per_source,
)
from fesi.store.signals import (
    get_signal_by_id,
    list_signals_for_ticker,
    list_signals_in_window,
)
from fesi.store.tickers import (
    get_ticker_by_symbol,
    list_all_tickers,
    list_watchlist_tickers,
)

log = get_logger(__name__)

router = APIRouter(prefix="/api")
health_router = APIRouter()


# ============================================================================
# Health (unauthenticated)
# ============================================================================
@health_router.get("/health", response_model=schemas.HealthOut)
def health() -> schemas.HealthOut:
    """Liveness + DB connectivity check (used by Railway probes)."""
    db_status = "ok"
    try:
        with connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e}"
    return schemas.HealthOut(status="ok", db=db_status)


# ============================================================================
# Status
# ============================================================================
@router.get("/status", response_model=schemas.StatusOut)
def get_status() -> schemas.StatusOut:
    s = get_settings()
    return schemas.StatusOut(
        version=__version__,
        mode=s.mode,
        environment=s.environment,
        database=_redact_db(s.database_url),
        timezone=s.tz,
        has_anthropic=has_anthropic(),
        has_pushover=bool(s.pushover_user_key and s.pushover_app_token),
        has_telegram=bool(s.telegram_bot_token and s.telegram_chat_id),
    )


def _redact_db(url: str) -> str:
    if "@" not in url:
        return url
    try:
        scheme, rest = url.split("://", 1)
        _, host = rest.rsplit("@", 1)
        return f"{scheme}://***@{host}"
    except ValueError:
        return url


# ============================================================================
# Signals
# ============================================================================
@router.get("/signals", response_model=list[schemas.SignalOut])
def get_signals(
    days: int = Query(7, ge=1, le=90),
    min_conviction: float | None = Query(None, ge=0, le=30),
    sector: str | None = None,
) -> list[schemas.SignalOut]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    with connect() as conn:
        rows = list_signals_in_window(
            conn, since=since, min_conviction=min_conviction, sector=sector
        )
    return [schemas.SignalOut(**_signal_dict(r)) for r in rows]


@router.get("/signals/{signal_id}", response_model=schemas.SignalOut)
def get_signal(signal_id: int) -> schemas.SignalOut:
    with connect() as conn:
        row = get_signal_by_id(conn, signal_id)
    if row is None:
        raise HTTPException(status_code=404, detail="signal not found")
    return schemas.SignalOut(**_signal_dict(row))


def _signal_dict(row: dict) -> dict:
    """Pluck only the fields SignalOut declares (drops the JSON arrays etc)."""
    keys = set(schemas.SignalOut.model_fields.keys())
    return {
        "ticker_id": row.get("primary_ticker_id"),
        **{k: row.get(k) for k in keys if k != "ticker_id"},
    }


# ============================================================================
# Decisions
# ============================================================================
@router.get("/decisions", response_model=list[schemas.DecisionOut])
def get_decisions(
    days: int = Query(7, ge=1, le=90),
    mode: str | None = None,
    action: str | None = None,
    limit: int | None = Query(None, ge=1, le=500),
) -> list[schemas.DecisionOut]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    with connect() as conn:
        rows = list_recent_decisions(
            conn, since=since, mode=mode, action=action, limit=limit
        )
    return [schemas.DecisionOut(**_decision_dict(r)) for r in rows]


def _decision_dict(row: dict) -> dict:
    keys = set(schemas.DecisionOut.model_fields.keys())
    return {k: row.get(k) for k in keys}


# ============================================================================
# Tickers
# ============================================================================
@router.get("/tickers", response_model=list[schemas.TickerOut])
def get_tickers(watchlist_only: bool = False) -> list[schemas.TickerOut]:
    with connect() as conn:
        rows = list_watchlist_tickers(conn) if watchlist_only else list_all_tickers(conn)
    return [schemas.TickerOut(**_ticker_dict(r)) for r in rows]


@router.get("/tickers/{symbol}", response_model=schemas.TickerOut)
def get_ticker(symbol: str) -> schemas.TickerOut:
    with connect() as conn:
        row = get_ticker_by_symbol(conn, symbol)
    if row is None:
        raise HTTPException(status_code=404, detail="ticker not found")
    return schemas.TickerOut(**_ticker_dict(row))


@router.get("/tickers/{symbol}/signals", response_model=list[schemas.SignalOut])
def get_ticker_signals(symbol: str, limit: int = Query(50, ge=1, le=200)) -> list[schemas.SignalOut]:
    with connect() as conn:
        ticker = get_ticker_by_symbol(conn, symbol)
        if ticker is None:
            raise HTTPException(status_code=404, detail="ticker not found")
        rows = list_signals_for_ticker(conn, ticker["id"], limit=limit)
    return [schemas.SignalOut(**_signal_dict(r)) for r in rows]


def _ticker_dict(row: dict) -> dict:
    keys = set(schemas.TickerOut.model_fields.keys())
    return {k: row.get(k) for k in keys}


# ============================================================================
# Portfolio
# ============================================================================
@router.get("/portfolio", response_model=schemas.PortfolioOut)
def get_portfolio(mode: str = "shadow") -> schemas.PortfolioOut:
    from fesi.config import load_risk
    risk = load_risk()
    cap = risk.capital.monthly_deployment_cap_usd
    with connect() as conn:
        deployed_total = total_deployed_capital(conn, mode)
        deployed_month = total_deployed_this_month(conn, mode)
        sector_exposure = get_sector_exposure(conn, mode)
        open_buys = count_concurrent_buys(conn, mode)
    return schemas.PortfolioOut(
        mode=mode,
        deployed_total_usd=deployed_total,
        deployed_this_month_usd=deployed_month,
        monthly_cap_usd=cap,
        cap_used_pct=(deployed_month / cap * 100) if cap else 0.0,
        sector_exposure=sector_exposure,
        open_buy_count=open_buys,
    )


# ============================================================================
# Sources
# ============================================================================
@router.get("/sources", response_model=list[schemas.SourceHealthOut])
def get_sources_health() -> list[schemas.SourceHealthOut]:
    sources_cfg = load_sources()
    with connect() as conn:
        counts = count_raw_items_by_source(conn)
        latest = latest_fetch_per_source(conn)
    return [
        schemas.SourceHealthOut(
            key=key,
            display_name=cfg.display_name,
            type=cfg.type,
            cost=cfg.cost,
            monthly_usd=cfg.monthly_usd,
            trust=cfg.trust,
            active=cfg.active,
            items_total=counts.get(key, 0),
            last_fetch=latest.get(key),
        )
        for key, cfg in sources_cfg.items()
    ]


# ============================================================================
# Digests
# ============================================================================
@router.get("/digests", response_model=list[schemas.DigestSummaryOut])
def get_digests(limit: int = Query(20, ge=1, le=100)) -> list[schemas.DigestSummaryOut]:
    with connect() as conn:
        rows = list_recent_digests(conn, limit=limit)
    return [schemas.DigestSummaryOut(**r) for r in rows]


@router.get("/digests/{digest_id}", response_model=schemas.DigestOut)
def get_digest(digest_id: int) -> schemas.DigestOut:
    with connect() as conn:
        row = get_digest_by_id(conn, digest_id)
    if row is None:
        raise HTTPException(status_code=404, detail="digest not found")
    return schemas.DigestOut(**row)


# ============================================================================
# Pipeline trigger
# ============================================================================
@router.post("/pipeline/run", response_model=schemas.PipelineRunOut)
def run_pipeline_endpoint(
    window_hours: int = Query(48, ge=1, le=168),
    silent: bool = False,
) -> schemas.PipelineRunOut:
    """Trigger one full pipeline cycle synchronously.

    For Phase 2 we run synchronously and block. Phase 3+ should move this
    to a background task with a job_id you can poll.
    """
    from fesi.ops.pipeline import run_pipeline
    stats = run_pipeline(scan_window_hours=window_hours, silent_alerts=silent)
    return schemas.PipelineRunOut(**stats.to_dict())
