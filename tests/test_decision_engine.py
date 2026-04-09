"""Tests for the decision engine + risk gates + sizing."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text


def _seed_signal(conn, *, ticker_symbol: str, conviction: float, sector: str = "biotech_pharma") -> int:
    """Insert a synthetic signal pointing at a watchlist ticker. Returns signal_id."""
    from fesi.store.tickers import get_ticker_by_symbol
    from fesi.store.signals import insert_signal

    ticker = get_ticker_by_symbol(conn, ticker_symbol)
    assert ticker is not None, f"watchlist ticker {ticker_symbol} not loaded"

    return insert_signal(
        conn,
        event_at=datetime.now(timezone.utc),
        primary_ticker_id=ticker["id"],
        catalyst_type="fda_approval",
        sector=sector,
        headline=f"FDA approves drug for {ticker_symbol}",
        summary=f"FDA approves drug for {ticker_symbol}",
        economics_summary=None,
        impact_score=4,
        probability_score=int(conviction / 4) if conviction > 0 else 1,
        conviction_score=conviction,
        timeframe_bucket="0-3m",
        direction="bullish",
        feature_source_count=2,
        feature_source_diversity=2,
        feature_is_watchlist=1,
    )


def _seed_price(conn, ticker_symbol: str, close: float) -> None:
    from fesi.store.prices import insert_price_bar
    from fesi.store.tickers import get_ticker_by_symbol
    ticker = get_ticker_by_symbol(conn, ticker_symbol)
    insert_price_bar(
        conn,
        ticker_id=ticker["id"],
        date="2026-04-08",
        open_=close * 0.99,
        high=close * 1.01,
        low=close * 0.98,
        close=close,
        volume=1_000_000,
        source="test",
    )


def _fetch_signal(conn, sid: int) -> dict:
    row = conn.execute(
        text("SELECT * FROM signals WHERE id = :id"),
        {"id": sid},
    ).mappings().first()
    return dict(row)


def test_high_conviction_watchlist_buy(db_conn):
    _seed_price(db_conn, "ONC", close=200.0)
    sid = _seed_signal(db_conn, ticker_symbol="ONC", conviction=20.0)
    signal = _fetch_signal(db_conn, sid)

    from fesi.decision.engine import make_decision
    result = make_decision(db_conn, signal)

    assert result["action"] == "buy"
    assert result["ticker"] == "ONC"
    assert result["position_usd"] <= 2000  # respects max_per_trade


def test_low_conviction_no_buy(db_conn):
    _seed_price(db_conn, "ONC", close=200.0)
    sid = _seed_signal(db_conn, ticker_symbol="ONC", conviction=4.0)
    signal = _fetch_signal(db_conn, sid)

    from fesi.decision.engine import make_decision
    result = make_decision(db_conn, signal)

    assert result["action"] == "no_buy"


def test_no_price_data_no_buy(db_conn):
    sid = _seed_signal(db_conn, ticker_symbol="ONC", conviction=20.0)
    signal = _fetch_signal(db_conn, sid)

    from fesi.decision.engine import make_decision
    result = make_decision(db_conn, signal)

    assert result["action"] == "no_buy"
    assert "price" in result["reason"].lower()


def test_decision_persists_to_db(db_conn):
    _seed_price(db_conn, "ONC", close=200.0)
    sid = _seed_signal(db_conn, ticker_symbol="ONC", conviction=20.0)
    signal = _fetch_signal(db_conn, sid)

    from fesi.decision.engine import make_decision
    make_decision(db_conn, signal)

    rows = db_conn.execute(
        text("SELECT * FROM decisions WHERE signal_id = :id"),
        {"id": sid},
    ).mappings().all()
    assert len(rows) == 1
    d = dict(rows[0])
    assert d["action"] == "buy"
    assert d["mode"] == "shadow"
    assert d["passed_position_size_check"] == 1
    assert d["passed_concurrent_check"] == 1


def test_position_sizing_scales_with_conviction(db_conn):
    _seed_price(db_conn, "ONC", close=100.0)
    from fesi.decision.sizing import plan_position
    from fesi.config import load_risk

    risk = load_risk()
    low = plan_position(
        entry_price=100, conviction_score=12.0, direction="bullish",
        timeframe_bucket="0-3m", risk=risk,
    )
    high = plan_position(
        entry_price=100, conviction_score=24.0, direction="bullish",
        timeframe_bucket="0-3m", risk=risk,
    )
    assert high.intended_position_usd > low.intended_position_usd
    assert high.intended_position_usd <= risk.position.max_per_trade_usd


def test_stop_and_target_for_bullish():
    from fesi.config import load_risk
    from fesi.decision.sizing import plan_position
    risk = load_risk()
    plan = plan_position(
        entry_price=100, conviction_score=20.0, direction="bullish",
        timeframe_bucket="0-3m", risk=risk,
    )
    assert plan.intended_stop_loss < plan.intended_entry_price
    assert plan.intended_target > plan.intended_entry_price


def test_stop_and_target_for_bearish():
    from fesi.config import load_risk
    from fesi.decision.sizing import plan_position
    risk = load_risk()
    plan = plan_position(
        entry_price=100, conviction_score=20.0, direction="bearish",
        timeframe_bucket="0-3m", risk=risk,
    )
    assert plan.intended_stop_loss > plan.intended_entry_price
    assert plan.intended_target < plan.intended_entry_price
