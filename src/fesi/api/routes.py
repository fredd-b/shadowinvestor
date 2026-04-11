"""All FastAPI routes — single file for personal-scale clarity."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from fesi import __version__
from fesi.api import schemas
from fesi.config import get_settings, load_sectors, load_sources
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
    add_ticker_to_watchlist,
    get_ticker_by_symbol,
    list_all_tickers,
    list_watchlist_tickers,
    remove_ticker_from_watchlist,
    update_ticker_status,
    update_ticker_thesis,
)
from fesi.store.signals import update_signal_user_action
from fesi.store.user_actions import insert_user_action, list_recent_actions

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
        # Join decision data for recommendation
        decision = conn.execute(text("""
            SELECT action, reasoning, confidence, rule_triggered,
                   intended_entry_price, intended_stop_loss, intended_target,
                   intended_position_usd
            FROM decisions WHERE signal_id = :sid
            ORDER BY decided_at DESC LIMIT 1
        """), {"sid": signal_id}).mappings().first()
    d = _signal_dict(row)
    if decision:
        dec = dict(decision)
        d["decision_action"] = dec.get("action")
        d["recommendation_reasoning"] = dec.get("reasoning")
        d["recommendation_confidence"] = dec.get("confidence")
        d["intended_entry_price"] = dec.get("intended_entry_price")
        d["intended_stop_loss"] = dec.get("intended_stop_loss")
        d["intended_target"] = dec.get("intended_target")
        d["intended_position_usd"] = dec.get("intended_position_usd")
        d["decision_rule"] = dec.get("rule_triggered")
        # Map to recommendation label
        conv = row.get("conviction_score", 0)
        if dec["action"] == "buy":
            d["recommendation"] = "BUY" if conv >= 15 else "CONSIDER"
        elif dec.get("rule_triggered") and "conviction" in (dec["rule_triggered"] or ""):
            d["recommendation"] = "SKIP"
        else:
            d["recommendation"] = "WATCH"
    return schemas.SignalOut(**d)


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


@router.get("/tickers/{symbol}/indicators", response_model=schemas.TickerIndicatorsOut)
def get_ticker_indicators(symbol: str) -> schemas.TickerIndicatorsOut:
    """Technical analysis indicators for a ticker."""
    from fesi.analysis.ta import compute_indicators
    from fesi.store.positions import get_open_position_for_ticker
    from fesi.store.prices import get_price_history

    with connect() as conn:
        ticker = get_ticker_by_symbol(conn, symbol)
        if ticker is None:
            raise HTTPException(status_code=404, detail="ticker not found")

        prices = get_price_history(conn, ticker["id"])
        indicators = compute_indicators(prices)

        entry_price = None
        price_vs_entry_pct = None
        pos = get_open_position_for_ticker(conn, ticker["id"], get_settings().mode)
        if pos and indicators.get("latest"):
            entry_price = pos["entry_price"]
            current = indicators["latest"]["close"]
            if entry_price and entry_price > 0:
                price_vs_entry_pct = round((current - entry_price) / entry_price * 100, 2)

    return schemas.TickerIndicatorsOut(
        symbol=symbol,
        data_points=indicators.get("data_points", 0),
        entry_price=entry_price,
        price_vs_entry_pct=price_vs_entry_pct,
        latest=indicators.get("latest"),
    )


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


# ============================================================================
# Research — per-sector Perplexity queries
# ============================================================================
@router.get("/research/status", response_model=list[schemas.ResearchSectorOut])
def get_research_status() -> list[schemas.ResearchSectorOut]:
    """List all 6 research sectors with their last run time and query description."""
    from fesi.ingest.perplexity import PerplexityAdapter

    sectors_cfg = load_sectors()
    adapter = PerplexityAdapter()
    queries = adapter._build_queries() if adapter.enabled else []
    query_map = {k: p for k, p in queries}

    # Get last Perplexity fetch per sector from raw_items
    # Use Postgres JSON operator or SQLite json_extract depending on DB
    s = get_settings()
    if s.database_url.startswith("postgresql"):
        sector_expr = "raw_payload::json->>'sector_query'"
    else:
        sector_expr = "json_extract(raw_payload, '$.sector_query')"
    with connect() as conn:
        rows = conn.execute(text(f"""
            SELECT
                {sector_expr} AS sector_key,
                MAX(fetched_at) AS last_fetched,
                COUNT(*) AS items_found
            FROM raw_items
            WHERE source = 'perplexity_api'
            GROUP BY {sector_expr}
        """)).mappings().all()
    last_runs = {r["sector_key"]: r for r in rows}

    schedule = [
        {"time": "15:00", "label": "pre_market"},
        {"time": "18:00", "label": "post_open"},
        {"time": "22:00", "label": "mid_session"},
        {"time": "02:00", "label": "post_close"},
        {"time": "08:00", "label": "morning_catchup"},
    ]

    result = []
    for key, sector in sectors_cfg.items():
        run = last_runs.get(key)
        result.append(schemas.ResearchSectorOut(
            sector_key=key,
            display_name=sector.display_name,
            description=sector.description,
            query_preview=query_map.get(key, "")[:300] if query_map.get(key) else None,
            last_run_at=run["last_fetched"] if run else None,
            items_found_last_run=run["items_found"] if run else 0,
            enabled=adapter.enabled,
            schedule=schedule,
        ))
    return result


@router.post("/research/run", response_model=schemas.ResearchRunOut)
def run_research(
    sector: str | None = Query(None, description="Sector key, or omit for all 6"),
) -> schemas.ResearchRunOut:
    """Run Perplexity research for one sector or all. Returns items found."""
    from fesi.ingest.perplexity import PerplexityAdapter
    from fesi.store.raw_items import insert_raw_items

    adapter = PerplexityAdapter()
    if not adapter.enabled:
        raise HTTPException(status_code=400, detail="PERPLEXITY_API_KEY not set")

    sectors_cfg = load_sectors()
    if sector and sector not in sectors_cfg:
        raise HTTPException(status_code=400, detail=f"Unknown sector: {sector}")

    items = adapter.fetch(only_sector=sector)
    with connect() as conn:
        result = insert_raw_items(conn, items)

    return schemas.ResearchRunOut(
        sector=sector or "all",
        items_fetched=len(items),
        items_inserted=result["inserted"],
        items_skipped=result["skipped"],
    )


# ============================================================================
# Prices
# ============================================================================
@router.post("/prices/fetch-watchlist")
def fetch_watchlist_prices(days: int = Query(30, ge=1, le=365)) -> dict:
    """Fetch yfinance prices for all watchlist tickers."""
    from fesi.store.prices import fetch_yfinance_history
    with connect() as conn:
        tickers = list_watchlist_tickers(conn)
        results = []
        for t in tickers:
            r = fetch_yfinance_history(conn, t["symbol"], days=days, exchange=t["exchange"])
            results.append(r)
    inserted = sum(r.get("inserted", 0) for r in results)
    failed = sum(1 for r in results if "error" in r)
    return {"tickers": len(results), "bars_inserted": inserted, "failures": failed}


# ============================================================================
# Research topics CRUD
# ============================================================================
@router.get("/research/topics", response_model=list[schemas.ResearchTopicOut])
def list_research_topics() -> list[schemas.ResearchTopicOut]:
    from fesi.store.research_topics import list_all_topics
    with connect() as conn:
        rows = list_all_topics(conn)
    return [schemas.ResearchTopicOut(**r) for r in rows]


@router.post("/research/topics", response_model=schemas.ResearchTopicOut)
def create_research_topic(body: schemas.CreateResearchTopicIn) -> schemas.ResearchTopicOut:
    from fesi.store.research_topics import create_topic, get_topic_by_id
    with connect() as conn:
        tid = create_topic(
            conn, name=body.name, query_template=body.query_template,
            sector_hint=body.sector_hint, schedule=body.schedule,
        )
        topic = get_topic_by_id(conn, tid)
    return schemas.ResearchTopicOut(**topic)


@router.patch("/research/topics/{topic_id}")
def update_research_topic(topic_id: int, body: schemas.UpdateResearchTopicIn) -> dict:
    from fesi.store.research_topics import update_topic, get_topic_by_id
    with connect() as conn:
        existing = get_topic_by_id(conn, topic_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Topic not found")
        updates = body.model_dump(exclude_none=True)
        if updates:
            update_topic(conn, topic_id, **updates)
    return {"ok": True, "topic_id": topic_id}


@router.delete("/research/topics/{topic_id}")
def delete_research_topic(topic_id: int) -> dict:
    from fesi.store.research_topics import delete_topic, get_topic_by_id
    with connect() as conn:
        existing = get_topic_by_id(conn, topic_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Topic not found")
        delete_topic(conn, topic_id)
    return {"ok": True, "topic_id": topic_id}


@router.post("/research/topics/{topic_id}/run")
def run_research_topic(topic_id: int) -> dict:
    """Manually run a single custom research topic."""
    from fesi.ingest.perplexity import PerplexityAdapter
    from fesi.store.raw_items import insert_raw_items
    from fesi.store.research_topics import get_topic_by_id, mark_topic_run

    with connect() as conn:
        topic = get_topic_by_id(conn, topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")

    adapter = PerplexityAdapter()
    if not adapter.enabled:
        raise HTTPException(status_code=400, detail="PERPLEXITY_API_KEY not set")

    items = adapter.fetch_custom_topics([topic])
    with connect() as conn:
        result = insert_raw_items(conn, items)
        mark_topic_run(conn, topic_id, len(items))

    return {
        "topic_id": topic_id,
        "items_fetched": len(items),
        "items_inserted": result["inserted"],
        "items_skipped": result["skipped"],
    }


# ============================================================================
# Watchlist management (CRUD)
# ============================================================================
@router.post("/tickers", response_model=schemas.TickerOut)
def add_ticker(body: schemas.AddTickerIn) -> schemas.TickerOut:
    """Add a new ticker to the watchlist."""
    with connect() as conn:
        existing = get_ticker_by_symbol(conn, body.symbol, body.exchange)
        if existing:
            raise HTTPException(status_code=409, detail=f"{body.symbol} already exists")
        ticker_id = add_ticker_to_watchlist(
            conn,
            symbol=body.symbol,
            exchange=body.exchange,
            name=body.name,
            sector=body.sector,
            thesis=body.thesis,
            sub_sector=body.sub_sector,
        )
        insert_user_action(
            conn,
            action_type="add_watchlist",
            target_type="ticker",
            target_id=ticker_id,
            note=body.thesis,
        )
        ticker = get_ticker_by_symbol(conn, body.symbol, body.exchange)
    return schemas.TickerOut(**ticker)


@router.patch("/tickers/{symbol}/status")
def patch_ticker_status(symbol: str, body: schemas.TickerStatusIn) -> dict:
    """Change a ticker's lifecycle status."""
    with connect() as conn:
        ticker = get_ticker_by_symbol(conn, symbol)
        if not ticker:
            raise HTTPException(status_code=404, detail=f"Ticker {symbol} not found")
        update_ticker_status(conn, ticker["id"], body.status)
        insert_user_action(
            conn,
            action_type="change_status",
            target_type="ticker",
            target_id=ticker["id"],
            note=f"{body.status}" + (f": {body.note}" if body.note else ""),
        )
    return {"ok": True, "symbol": symbol, "status": body.status}


@router.patch("/tickers/{symbol}/thesis")
def patch_ticker_thesis(symbol: str, body: schemas.TickerThesisIn) -> dict:
    """Edit a ticker's watchlist thesis."""
    with connect() as conn:
        ticker = get_ticker_by_symbol(conn, symbol)
        if not ticker:
            raise HTTPException(status_code=404, detail=f"Ticker {symbol} not found")
        update_ticker_thesis(conn, ticker["id"], body.thesis)
        insert_user_action(
            conn,
            action_type="edit_thesis",
            target_type="ticker",
            target_id=ticker["id"],
            note=body.thesis[:200],
        )
    return {"ok": True, "symbol": symbol}


@router.delete("/tickers/{symbol}/watchlist")
def delete_ticker_from_watchlist(symbol: str) -> dict:
    """Remove a ticker from the active watchlist (archives it)."""
    with connect() as conn:
        ticker = get_ticker_by_symbol(conn, symbol)
        if not ticker:
            raise HTTPException(status_code=404, detail=f"Ticker {symbol} not found")
        remove_ticker_from_watchlist(conn, ticker["id"])
        insert_user_action(
            conn,
            action_type="remove_watchlist",
            target_type="ticker",
            target_id=ticker["id"],
        )
    return {"ok": True, "symbol": symbol, "status": "archived"}


# ============================================================================
# Signal user actions (invest / skip / watch)
# ============================================================================
@router.post("/signals/{signal_id}/action")
def post_signal_action(signal_id: int, body: schemas.SignalActionIn) -> dict:
    """Mark a signal with Fred's decision. If 'invest', opens a position."""
    from fesi.store.signals import get_signal_by_id
    from fesi.store.positions import open_position, get_open_position_for_ticker
    from fesi.store.prices import get_latest_price
    from fesi.decision.sizing import plan_position
    from fesi.config import load_risk

    with connect() as conn:
        signal = get_signal_by_id(conn, signal_id)
        if not signal:
            raise HTTPException(status_code=404, detail="Signal not found")
        update_signal_user_action(conn, signal_id, body.action)
        insert_user_action(
            conn,
            action_type=body.action,
            target_type="signal",
            target_id=signal_id,
            note=body.note,
        )

        position_id = None
        if body.action == "invest" and signal.get("primary_ticker_id"):
            tid = signal["primary_ticker_id"]
            mode = get_settings().mode
            existing = get_open_position_for_ticker(conn, tid, mode)
            if existing is None:
                latest = get_latest_price(conn, tid)
                entry_price = float(latest["close"]) if latest else None
                if entry_price:
                    risk = load_risk()
                    plan = plan_position(
                        entry_price=entry_price,
                        conviction_score=signal["conviction_score"],
                        direction=signal.get("direction", "bullish"),
                        timeframe_bucket=signal.get("timeframe_bucket", "0-3m"),
                        risk=risk,
                    )
                    pid = open_position(
                        conn, ticker_id=tid, mode=mode,
                        entry_decision_id=None, entry_price=entry_price,
                        shares=plan.shares, sector=signal.get("sector"),
                        catalyst_type=signal.get("catalyst_type"),
                        thesis=signal.get("summary", "")[:500],
                    )
                    position_id = pid
                    update_ticker_status(conn, tid, "invested")

    return {
        "ok": True,
        "signal_id": signal_id,
        "action": body.action,
        "position_id": position_id,
    }


# ============================================================================
# Positions
# ============================================================================
@router.get("/positions", response_model=list[schemas.PositionOut])
def get_positions_list(
    mode: str = Query("shadow"),
    status: str | None = Query(None),
) -> list[schemas.PositionOut]:
    """List positions with unrealized P&L."""
    from fesi.store.positions import list_positions
    with connect() as conn:
        rows = list_positions(conn, mode=mode, status=status)
    result = []
    for r in rows:
        remaining_cost = (r["shares_held"] - r["shares_sold"]) * r["entry_price"]
        pnl_pct = None
        if remaining_cost > 0 and r.get("unrealized_pnl_usd") is not None:
            pnl_pct = round(r["unrealized_pnl_usd"] / remaining_cost * 100, 2)
        result.append(schemas.PositionOut(**r, pnl_pct=pnl_pct))
    return result


@router.get("/positions/{position_id}", response_model=schemas.PositionOut)
def get_position(position_id: int) -> schemas.PositionOut:
    from fesi.store.positions import get_position_by_id
    with connect() as conn:
        pos = get_position_by_id(conn, position_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    remaining = pos["shares_held"] - pos["shares_sold"]
    pnl_pct = None
    if pos.get("cost_basis_usd") and pos["cost_basis_usd"] > 0 and pos.get("unrealized_pnl_usd") is not None:
        pnl_pct = round(pos["unrealized_pnl_usd"] / pos["cost_basis_usd"] * 100, 2)
    return schemas.PositionOut(**pos, pnl_pct=pnl_pct)


@router.post("/positions/{position_id}/sell")
def sell_position(position_id: int, body: schemas.SellPositionIn) -> dict:
    """Sell (full or partial) a position."""
    from fesi.store.positions import get_position_by_id, close_position
    from fesi.store.prices import get_latest_price
    from fesi.execute.shadow import execute_shadow_sell

    with connect() as conn:
        pos = get_position_by_id(conn, position_id)
        if not pos:
            raise HTTPException(status_code=404, detail="Position not found")
        if pos["status"] == "closed":
            raise HTTPException(status_code=400, detail="Position already closed")

        latest = get_latest_price(conn, pos["ticker_id"])
        if not latest:
            log.warning("sell_no_price_data", ticker_id=pos["ticker_id"])
        exit_price = float(latest["close"]) if latest else pos["entry_price"]

        # close_position validates and clamps shares_to_sell
        updated = close_position(
            conn, position_id, exit_price=exit_price,
            shares_to_sell=body.shares,
        )
        actual_sold = updated["shares_sold"] - (pos["shares_sold"])
        execute_shadow_sell(
            conn, decision_id=None, ticker_id=pos["ticker_id"],
            shares=actual_sold, exit_price=exit_price,
        )
        insert_user_action(
            conn, action_type="sell", target_type="position",
            target_id=position_id, note=body.note,
        )
        if updated["status"] == "closed":
            update_ticker_status(conn, pos["ticker_id"], "monitoring")

    return {
        "ok": True,
        "position_id": position_id,
        "status": updated["status"],
        "realized_pnl": updated["realized_pnl_usd"],
        "shares_sold": sell_qty,
        "exit_price": exit_price,
    }


# ============================================================================
# Discoveries (new tickers from signals not in watchlist)
# ============================================================================
@router.get("/discoveries")
def get_discoveries(limit: int = Query(20, ge=1, le=100)) -> list[dict]:
    """Signals mentioning tickers not yet on the watchlist."""
    with connect() as conn:
        rows = conn.execute(text("""
            SELECT s.id AS signal_id, s.headline, s.catalyst_type, s.sector,
                   s.conviction_score, s.direction, s.created_at,
                   t.symbol, t.name AS company_name, t.exchange
            FROM signals s
            JOIN tickers t ON s.primary_ticker_id = t.id
            WHERE t.is_watchlist = 0 AND t.lifecycle_status != 'archived'
            ORDER BY s.conviction_score DESC
            LIMIT :limit
        """), {"limit": limit}).mappings().all()
    return [dict(r) for r in rows]


# ============================================================================
# Activity feed
# ============================================================================
@router.get("/actions", response_model=list[schemas.UserActionOut])
def get_actions(limit: int = Query(50, ge=1, le=200)) -> list[schemas.UserActionOut]:
    """Recent user actions (activity feed)."""
    with connect() as conn:
        rows = list_recent_actions(conn, limit=limit)
    return [schemas.UserActionOut(**r) for r in rows]
