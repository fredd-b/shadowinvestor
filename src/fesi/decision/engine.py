"""Decision engine — converts a signal into a shadow/paper/live decision.

Decision rule (Phase 1):
  - Required: signal.conviction_score >= MIN_CONVICTION_TO_ACT (default 12.0,
    which is 3*4 or 4*3 in impact*probability terms)
  - Required: signal must have a resolved primary_ticker_id (we can't trade
    a signal we can't map to a tradeable instrument)
  - Required: ALL FOUR risk gates pass
  - Watchlist boost: if the signal's ticker is on the watchlist with a
    `alert_min_conviction <= conviction_score`, we drop the threshold by 2

If all gates pass → action='buy' with a PositionPlan
Otherwise → action='no_buy' with the failing reason in `reasoning`

Decisions are always written to DB (so we have a forward backtest journal of
both buys AND no-buys). Mode is whatever `get_settings().mode` says, defaulting
to 'shadow' so live trading never happens by accident.
"""
from __future__ import annotations

from sqlalchemy.engine import Connection

from fesi.config import get_settings, load_risk
from fesi.decision.risk_gates import check_all
from fesi.decision.sizing import plan_position
from fesi.logging import get_logger
from fesi.store.decisions import insert_decision
from fesi.store.prices import get_latest_price
from fesi.store.tickers import get_ticker_by_id

log = get_logger(__name__)

MIN_CONVICTION_TO_ACT = 12.0
WATCHLIST_CONVICTION_DROP = 2.0


def make_decision(conn: Connection, signal: dict) -> dict:
    """Decide buy/no_buy for a signal, write the decision row, return summary."""
    settings = get_settings()
    risk = load_risk()
    mode = settings.mode  # shadow | paper | live

    signal_id = signal["id"]
    conviction = float(signal["conviction_score"])
    sector = signal["sector"]
    direction = signal["direction"]
    timeframe = signal["timeframe_bucket"]
    ticker_id = signal.get("primary_ticker_id")

    # ---- Hard requirement: must have a resolvable ticker
    if ticker_id is None:
        return _record_no_buy(
            conn, signal_id, mode,
            reason="no_primary_ticker_resolved",
            rule="ticker_required",
        )

    ticker = get_ticker_by_id(conn, ticker_id)
    if ticker is None:
        return _record_no_buy(
            conn, signal_id, mode,
            reason=f"ticker_id_{ticker_id}_not_found",
            rule="ticker_required",
        )

    # ---- Conviction threshold (with watchlist boost)
    threshold = MIN_CONVICTION_TO_ACT
    if ticker.get("is_watchlist"):
        threshold = max(0, MIN_CONVICTION_TO_ACT - WATCHLIST_CONVICTION_DROP)

    if conviction < threshold:
        return _record_no_buy(
            conn, signal_id, mode,
            reason=f"conviction {conviction:.1f} < threshold {threshold:.1f}",
            rule="conviction_threshold",
        )

    # ---- Need an entry price
    latest = get_latest_price(conn, ticker_id)
    if latest is None or latest.get("close") is None:
        return _record_no_buy(
            conn, signal_id, mode,
            reason="no_recent_price_data",
            rule="entry_price_required",
        )
    entry_price = float(latest["close"])

    # ---- Plan position size
    plan = plan_position(
        entry_price=entry_price,
        conviction_score=conviction,
        direction=direction,
        timeframe_bucket=timeframe,
        risk=risk,
    )

    # ---- Risk gates (all 4 must pass)
    gates = check_all(
        conn,
        sector=sector,
        intended_position_usd=plan.intended_position_usd,
        risk=risk,
        mode=mode,
    )

    if not gates["all_passed"]:
        failing = [
            f"{name}: {info['reason']}"
            for name, info in gates.items()
            if isinstance(info, dict) and not info["passed"]
        ]
        decision_id = insert_decision(
            conn,
            signal_id=signal_id,
            mode=mode,
            action="no_buy",
            intended_position_usd=plan.intended_position_usd,
            intended_shares=plan.intended_shares,
            intended_entry_price=plan.intended_entry_price,
            intended_stop_loss=plan.intended_stop_loss,
            intended_target=plan.intended_target,
            intended_holding_period_days=plan.intended_holding_period_days,
            rule_triggered="risk_gate_failure",
            reasoning="; ".join(failing),
            confidence=conviction / 25.0,
            passed_position_size_check=gates["position_size"]["passed"],
            passed_concurrent_check=gates["concurrent"]["passed"],
            passed_sector_concentration_check=gates["sector_concentration"]["passed"],
            passed_circuit_breaker_check=gates["circuit_breaker"]["passed"],
        )
        log.info(
            "decision_no_buy",
            signal_id=signal_id,
            decision_id=decision_id,
            reason=failing,
        )
        return {"action": "no_buy", "decision_id": decision_id, "reason": failing}

    # ---- All systems go: record buy intent
    reasoning = (
        f"conviction={conviction:.1f} (impact×prob), "
        f"sector={sector}, direction={direction}, timeframe={timeframe}, "
        f"entry=${entry_price:.2f}, stop=${plan.intended_stop_loss:.2f}, "
        f"target=${plan.intended_target:.2f}, hold {plan.intended_holding_period_days}d"
    )
    decision_id = insert_decision(
        conn,
        signal_id=signal_id,
        mode=mode,
        action="buy",
        intended_position_usd=plan.intended_position_usd,
        intended_shares=plan.intended_shares,
        intended_entry_price=plan.intended_entry_price,
        intended_stop_loss=plan.intended_stop_loss,
        intended_target=plan.intended_target,
        intended_holding_period_days=plan.intended_holding_period_days,
        rule_triggered="conviction_threshold_passed",
        reasoning=reasoning,
        confidence=min(1.0, conviction / 25.0),
        passed_position_size_check=True,
        passed_concurrent_check=True,
        passed_sector_concentration_check=True,
        passed_circuit_breaker_check=True,
    )
    log.info(
        "decision_buy",
        signal_id=signal_id,
        decision_id=decision_id,
        ticker=ticker["symbol"],
        position_usd=plan.intended_position_usd,
    )
    return {
        "action": "buy",
        "decision_id": decision_id,
        "ticker": ticker["symbol"],
        "position_usd": plan.intended_position_usd,
        "shares": plan.intended_shares,
    }


def _record_no_buy(
    conn: sqlite3.Connection,
    signal_id: int,
    mode: str,
    *,
    reason: str,
    rule: str,
) -> dict:
    decision_id = insert_decision(
        conn,
        signal_id=signal_id,
        mode=mode,
        action="no_buy",
        rule_triggered=rule,
        reasoning=reason,
        confidence=0.0,
    )
    log.info("decision_no_buy", signal_id=signal_id, decision_id=decision_id, reason=reason)
    return {"action": "no_buy", "decision_id": decision_id, "reason": reason}
