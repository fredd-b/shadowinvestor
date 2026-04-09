"""Position sizing — fixed-risk for Phase 1.

We use the simplest sane sizing: every position is sized at the configured
max_per_trade_usd cap, scaled down by conviction. Higher conviction → larger
position, up to the cap. This gives us a clean signal for the ML calibration
loop in Phase 3 (we'll learn whether conviction-scaled sizing actually
improves risk-adjusted returns).

Stop loss & target are set as a fixed % below/above entry, parameterized by
catalyst direction.
"""
from __future__ import annotations

from dataclasses import dataclass

from fesi.config import RiskConfig


@dataclass
class PositionPlan:
    intended_position_usd: float
    intended_shares: int
    intended_entry_price: float
    intended_stop_loss: float
    intended_target: float
    intended_holding_period_days: int


def plan_position(
    *,
    entry_price: float,
    conviction_score: float,
    direction: str,
    timeframe_bucket: str,
    risk: RiskConfig,
) -> PositionPlan:
    """Compute a position plan for one signal.

    - Position size scales linearly with conviction in [12, 25] → [0.5, 1.0] × max
    - Stop loss: 12% below entry for bullish, 12% above for bearish
    - Target: 30% above for bullish, 30% below for bearish
    - Holding period: from timeframe bucket
    """
    max_size = risk.position.max_per_trade_usd

    # conviction 12 = 0.5x, conviction 25 = 1.0x, clamp
    scale = max(0.5, min(1.0, 0.5 + (conviction_score - 12.0) / 26.0))
    position_usd = round(max_size * scale, 2)

    shares = max(1, int(position_usd // max(0.01, entry_price)))
    actual_position_usd = round(shares * entry_price, 2)

    if direction == "bearish":
        stop_loss = round(entry_price * 1.12, 2)
        target = round(entry_price * 0.70, 2)
    else:
        stop_loss = round(entry_price * 0.88, 2)
        target = round(entry_price * 1.30, 2)

    holding_days = {
        "0-3m": 60,
        "3-12m": 180,
        "1-3y": 365,
    }.get(timeframe_bucket, 90)

    return PositionPlan(
        intended_position_usd=actual_position_usd,
        intended_shares=shares,
        intended_entry_price=entry_price,
        intended_stop_loss=stop_loss,
        intended_target=target,
        intended_holding_period_days=holding_days,
    )
