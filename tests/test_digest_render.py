"""Tests for the digest renderer."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _make_signal(*, headline: str, conviction: float, sector: str = "biotech_pharma", watchlist: int = 1) -> dict:
    return {
        "id": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "event_at": datetime.now(timezone.utc).isoformat(),
        "primary_ticker_id": 1,
        "ticker_symbol": "ONC",
        "ticker_exchange": "NASDAQ",
        "ticker_name": "BeOne Medicines",
        "catalyst_type": "fda_approval",
        "sector": sector,
        "headline": headline,
        "summary": "Summary text here.",
        "economics_summary": "$200M upfront",
        "impact_score": 5,
        "probability_score": 4,
        "conviction_score": conviction,
        "timeframe_bucket": "0-3m",
        "direction": "bullish",
        "feature_source_count": 3,
        "feature_source_diversity": 3,
        "feature_is_watchlist": watchlist,
    }


def test_render_empty_signals(db_conn):
    from fesi.digest.render import render_digest
    md = render_digest(
        db_conn,
        signals=[],
        window_start=datetime.now(timezone.utc) - timedelta(hours=48),
        window_end=datetime.now(timezone.utc),
    )
    assert "FESI Digest" in md
    assert "No signals at conviction" in md


def test_render_includes_top_section(db_conn):
    from fesi.digest.render import render_digest
    signals = [
        _make_signal(headline="FDA approves drug", conviction=22.0),
        _make_signal(headline="Phase 3 success", conviction=18.0),
    ]
    md = render_digest(
        db_conn,
        signals=signals,
        window_start=datetime.now(timezone.utc) - timedelta(hours=48),
        window_end=datetime.now(timezone.utc),
    )
    assert "Top 10 High-Conviction Catalysts" in md
    assert "ONC" in md
    assert "FDA approves drug" in md


def test_render_emerging_section(db_conn):
    from fesi.digest.render import render_digest
    signals = [
        _make_signal(headline="Lower confidence rumor", conviction=8.0, watchlist=0),
    ]
    md = render_digest(
        db_conn,
        signals=signals,
        window_start=datetime.now(timezone.utc) - timedelta(hours=48),
        window_end=datetime.now(timezone.utc),
    )
    assert "Emerging" in md
    assert "low-confidence" in md


def test_render_includes_shadow_portfolio_section(db_conn):
    from fesi.digest.render import render_digest
    md = render_digest(
        db_conn,
        signals=[],
        window_start=datetime.now(timezone.utc) - timedelta(hours=48),
        window_end=datetime.now(timezone.utc),
    )
    assert "Shadow Portfolio Summary" in md
