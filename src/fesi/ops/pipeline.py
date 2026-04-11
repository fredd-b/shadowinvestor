"""End-to-end pipeline orchestrator: ingest → normalize → score → decide → digest → notify.

This is the entry point called by the scheduler (5x/day) and by `fesi run-pipeline`
for manual runs. Each phase is wrapped in try/except so one failing source or
one bad signal can't kill the whole run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from fesi.config import get_settings, load_catalysts, load_sources
from fesi.db import connect
from fesi.decision.engine import make_decision
from fesi.digest.notify import deliver_digest
from fesi.digest.render import render_digest
from fesi.execute.shadow import execute_shadow_buy
from fesi.intelligence.classifier import classify
from fesi.intelligence.cross_ref import compute_conviction
from fesi.intelligence.normalize import normalize
from fesi.intelligence.scorer import score
from fesi.logging import get_logger
from fesi.store.decisions import list_recent_decisions
from fesi.store.digests import insert_digest
from fesi.store.outcomes import upsert_outcome_stub
from fesi.store.raw_items import get_unprocessed_raw_items, insert_raw_items
from fesi.store.signals import get_signal_by_id, insert_signal, list_signals_in_window
from fesi.store.tickers import get_ticker_by_symbol

log = get_logger(__name__)


@dataclass
class PipelineRunStats:
    started_at: datetime
    ended_at: datetime | None = None
    raw_items_fetched: int = 0
    raw_items_inserted: int = 0
    raw_items_skipped: int = 0
    candidates: int = 0
    signals_created: int = 0
    decisions_buy: int = 0
    decisions_no_buy: int = 0
    digest_id: int | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "raw_items_fetched": self.raw_items_fetched,
            "raw_items_inserted": self.raw_items_inserted,
            "raw_items_skipped": self.raw_items_skipped,
            "candidates": self.candidates,
            "signals_created": self.signals_created,
            "decisions_buy": self.decisions_buy,
            "decisions_no_buy": self.decisions_no_buy,
            "digest_id": self.digest_id,
            "errors": self.errors,
        }


def run_pipeline(
    *,
    scan_window_hours: int = 48,
    silent_alerts: bool = False,
    only_sources: list[str] | None = None,
    run_label: str | None = None,
) -> PipelineRunStats:
    """Run one full pipeline cycle. Called by the scheduler or `fesi run-pipeline`."""
    log.info("pipeline_start", scan_window_hours=scan_window_hours, run_label=run_label)
    stats = PipelineRunStats(started_at=datetime.now(timezone.utc))
    since = stats.started_at - timedelta(hours=scan_window_hours)

    # ---- Phase A: Ingest from all active sources ----
    all_items = _ingest_all(only_sources=only_sources, stats=stats, run_label=run_label)
    stats.raw_items_fetched = len(all_items)

    # ---- DB-bound work ----
    digest_md: str | None = None
    with connect() as conn:
        result = insert_raw_items(conn, all_items)
        stats.raw_items_inserted = result["inserted"]
        stats.raw_items_skipped = result["skipped"]

        # ---- Phase B: Normalize ----
        unprocessed = get_unprocessed_raw_items(conn, since=since)
        candidates = normalize(unprocessed)
        stats.candidates = len(candidates)

        # ---- Phase C: Classify, Score, Cross-ref → insert signals ----
        signals_inserted: list[int] = []
        catalysts = load_catalysts()
        sources_cfg = load_sources()

        for cand in candidates:
            try:
                with conn.begin_nested():
                    sid = _process_candidate(
                        conn, cand, catalysts, sources_cfg, stats.started_at
                    )
                    if sid is not None:
                        signals_inserted.append(sid)
            except Exception as e:
                log.exception("candidate_processing_failed", error=str(e))
                stats.errors.append(f"candidate: {e}")

        stats.signals_created = len(signals_inserted)

        # ---- Phase D: Decide ----
        from fesi.store.prices import get_latest_price
        for sid in signals_inserted:
            try:
                with conn.begin_nested():
                    signal = get_signal_by_id(conn, sid)
                    if signal is None:
                        continue
                    outcome = make_decision(conn, signal)
                    if outcome["action"] == "buy":
                        stats.decisions_buy += 1
                        if signal.get("primary_ticker_id"):
                            latest = get_latest_price(conn, signal["primary_ticker_id"])
                            if latest is not None:
                                entry_price = float(latest["close"])
                                execute_shadow_buy(
                                    conn,
                                    decision_id=outcome["decision_id"],
                                    ticker_id=signal["primary_ticker_id"],
                                    shares=outcome["shares"],
                                    entry_price=entry_price,
                                )
                                # Open a position (skip if one already exists)
                                from fesi.store.positions import (
                                    open_position, get_open_position_for_ticker,
                                )
                                existing = get_open_position_for_ticker(
                                    conn, signal["primary_ticker_id"],
                                    get_settings().mode,
                                )
                                if existing is None:
                                    open_position(
                                        conn,
                                        ticker_id=signal["primary_ticker_id"],
                                        mode=get_settings().mode,
                                        entry_decision_id=outcome["decision_id"],
                                        entry_price=entry_price,
                                        shares=outcome["shares"],
                                        sector=signal.get("sector"),
                                        catalyst_type=signal.get("catalyst_type"),
                                    )
                    else:
                        stats.decisions_no_buy += 1
            except Exception as e:
                log.exception("decision_failed", signal_id=sid, error=str(e))
                stats.errors.append(f"decide: {e}")

        # ---- Phase E: Render digest ----
        try:
            with conn.begin_nested():
                window_signals = list_signals_in_window(conn, since=since)
                digest_md = render_digest(
                    conn,
                    signals=window_signals,
                    window_start=since,
                    window_end=stats.started_at,
                )
                digest_id = insert_digest(
                    conn,
                    window_start=since,
                    window_end=stats.started_at,
                    signal_count=len(window_signals),
                    decision_count=stats.decisions_buy + stats.decisions_no_buy,
                    delivered_via="pending",
                    markdown_body=digest_md,
                )
                stats.digest_id = digest_id
        except Exception as e:
            log.exception("digest_render_failed", error=str(e))
            stats.errors.append(f"digest: {e}")

    # ---- Phase E2: Update unrealized P&L on open positions ----
    try:
        with connect() as conn:
            from fesi.store.positions import update_all_unrealized
            update_all_unrealized(conn, mode=get_settings().mode)
    except Exception as e:
        log.exception("unrealized_update_failed", error=str(e))
        stats.errors.append(f"unrealized: {e}")

    # ---- Phase F: Notify (outside DB context to release the lock) ----
    if digest_md:
        try:
            deliver_digest(digest_md, silent=silent_alerts)
        except Exception as e:
            log.exception("notify_failed", error=str(e))
            stats.errors.append(f"notify: {e}")

    stats.ended_at = datetime.now(timezone.utc)
    log.info("pipeline_done", stats=stats.to_dict())
    return stats


# ============================================================================
# Phase implementations
# ============================================================================

def _ingest_all(
    *, only_sources: list[str] | None, stats: PipelineRunStats,
    run_label: str | None = None,
) -> list:
    """Fetch from every active adapter, isolated by try/except."""
    from fesi.ingest import (
        clinicaltrials,
        fda_openfda,
        perplexity,
        sec_edgar,
        wires,
    )

    adapters = [
        sec_edgar.SecEdgarAdapter(),
        fda_openfda.FdaOpenfdaAdapter(),
        clinicaltrials.ClinicalTrialsAdapter(),
        wires.WiresAdapter(),
        perplexity.PerplexityAdapter(),
    ]
    if only_sources:
        adapters = [a for a in adapters if a.source_key in only_sources]

    all_items: list = []
    for adapter in adapters:
        try:
            items = adapter.fetch()
            log.info("ingest_done", source=adapter.source_key, count=len(items))
            all_items.extend(items)
        except Exception as e:
            log.exception("ingest_failed", source=adapter.source_key, error=str(e))
            stats.errors.append(f"{adapter.source_key}: {e}")

    # ---- Custom research topics (Perplexity) ----
    if not only_sources or "perplexity_api" in (only_sources or []):
        try:
            pplx = perplexity.PerplexityAdapter()
            if pplx.enabled:
                from fesi.store.research_topics import get_topics_due_for_run, mark_topic_run
                with connect() as conn:
                    topics = get_topics_due_for_run(conn, run_label=run_label or "")
                if topics:
                    topic_items = pplx.fetch_custom_topics(topics)
                    all_items.extend(topic_items)
                    with connect() as conn:
                        for t in topics:
                            count = sum(1 for i in topic_items if f"topic_{t['id']}" in i.source_id)
                            mark_topic_run(conn, t["id"], count)
                    log.info("custom_topics_done", topics=len(topics), items=len(topic_items))
        except Exception as e:
            log.exception("custom_topics_failed", error=str(e))
            stats.errors.append(f"custom_topics: {e}")

    # ---- Per-ticker daily research (morning_catchup only) ----
    if run_label == "morning_catchup" and (not only_sources or "perplexity_api" in (only_sources or [])):
        try:
            pplx = perplexity.PerplexityAdapter()
            if pplx.enabled:
                from fesi.store.tickers import list_tickers_for_daily_research
                with connect() as conn:
                    research_tickers = list_tickers_for_daily_research(conn)
                if research_tickers:
                    ticker_items = pplx.fetch_ticker_research(research_tickers)
                    all_items.extend(ticker_items)
                    log.info("ticker_research_done", tickers=len(research_tickers), items=len(ticker_items))
        except Exception as e:
            log.exception("ticker_research_failed", error=str(e))
            stats.errors.append(f"ticker_research: {e}")

    return all_items


def _process_candidate(
    conn,
    cand,
    catalysts,
    sources_cfg,
    started_at: datetime,
) -> int | None:
    """Classify, score, cross-ref a candidate signal and insert as a `signals` row."""
    primary_source = cand.sources[0] if cand.sources else ""
    cls = classify(cand.primary_title, cand.primary_body, primary_source)

    cat = catalysts.get(cls.catalyst_type)
    if cat is None:
        log.warning("unknown_catalyst_type_dropped", type=cls.catalyst_type)
        return None

    sc = score(cand.primary_title, cand.primary_body, cls, cat)

    conviction = compute_conviction(
        sc.impact_score,
        sc.probability_score,
        cand.source_count,
        cand.source_diversity,
        cand.sources,
    )

    # Resolve ticker
    ticker_id: int | None = None
    feature_is_watchlist = 0
    feature_market_cap_usd: float | None = None
    feature_market_cap_bucket: str | None = None
    if cls.primary_ticker_symbol:
        t = get_ticker_by_symbol(
            conn, cls.primary_ticker_symbol, cls.primary_ticker_exchange
        )
        if t:
            ticker_id = t["id"]
            feature_is_watchlist = int(t.get("is_watchlist") or 0)
            feature_market_cap_usd = t.get("market_cap_usd")
            feature_market_cap_bucket = _bucket_market_cap(feature_market_cap_usd)

    event_at = cand.earliest_published or started_at

    avg_quality = (
        sum(
            (sources_cfg.get(s).trust if s in sources_cfg else 3)
            for s in cand.sources
        ) / max(1, len(cand.sources))
    )

    signal_id = insert_signal(
        conn,
        event_at=event_at,
        primary_ticker_id=ticker_id,
        catalyst_type=cls.catalyst_type,
        sector=cls.sector,
        headline=cls.headline,
        summary=cls.summary,
        economics_summary=cls.economics_summary,
        impact_score=sc.impact_score,
        probability_score=sc.probability_score,
        conviction_score=conviction,
        timeframe_bucket=cls.timeframe_bucket,
        direction=cls.direction,
        feature_source_count=cand.source_count,
        feature_source_diversity=cand.source_diversity,
        feature_source_quality_avg=round(avg_quality, 2),
        feature_sentiment_score=sc.sentiment_score,
        feature_market_cap_bucket=feature_market_cap_bucket,
        feature_market_cap_usd=feature_market_cap_usd,
        feature_time_of_day=_time_of_day(started_at),
        feature_day_of_week=started_at.weekday(),
        feature_is_watchlist=feature_is_watchlist,
        raw_item_ids=cand.raw_item_ids,
        source_urls=cand.urls,
    )
    upsert_outcome_stub(conn, signal_id)
    return signal_id


def _bucket_market_cap(usd: float | None) -> str | None:
    if usd is None:
        return None
    if usd < 300_000_000:
        return "micro"
    if usd < 2_000_000_000:
        return "small"
    if usd < 10_000_000_000:
        return "mid"
    if usd < 200_000_000_000:
        return "large"
    return "mega"


def _time_of_day(dt: datetime) -> str:
    """Bucket UTC time into US Eastern trading session bucket (rough)."""
    et_hour = (dt.hour - 5) % 24
    if 4 <= et_hour < 9:
        return "pre_market"
    if 9 <= et_hour < 12:
        return "morning"
    if 12 <= et_hour < 14:
        return "midday"
    if 14 <= et_hour < 16:
        return "afternoon"
    if 16 <= et_hour < 20:
        return "after_hours"
    return "overnight"
