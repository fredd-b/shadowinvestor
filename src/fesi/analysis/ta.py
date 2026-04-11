"""Technical analysis indicators — pure Python, no external dependencies.

Computes SMA, RSI from OHLCV price history. Used by the ticker detail page
and optionally by the decision engine for entry/exit timing confirmation.
"""
from __future__ import annotations


def sma(closes: list[float], period: int) -> list[float | None]:
    """Simple Moving Average. First (period-1) values are None."""
    if period <= 0 or not closes:
        return [None] * len(closes)
    result: list[float | None] = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        result[i] = sum(closes[i - period + 1 : i + 1]) / period
    return result


def rsi(closes: list[float], period: int = 14) -> list[float | None]:
    """Relative Strength Index using Wilder's smoothing. First `period` values are None."""
    if period <= 0 or len(closes) < period + 1:
        return [None] * len(closes)

    result: list[float | None] = [None] * len(closes)

    # Calculate initial average gain/loss over the first `period` changes
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100.0 - (100.0 / (1.0 + rs))

    # Wilder's smoothing for subsequent values
    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        gain = max(change, 0)
        loss = max(-change, 0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - (100.0 / (1.0 + rs))

    return result


def compute_indicators(prices: list[dict]) -> dict:
    """Compute all indicators from a price history list (ordered by date ASC).

    Each dict must have at least 'date' and 'close' keys.
    Returns a dict with arrays and a 'latest' summary.
    """
    if not prices:
        return {"latest": None, "data_points": 0, "dates": [], "closes": []}

    dates = [p["date"] for p in prices]
    closes = [float(p["close"]) for p in prices]

    sma_20 = sma(closes, 20)
    sma_50 = sma(closes, 50)
    sma_200 = sma(closes, 200)
    rsi_14 = rsi(closes, 14)

    last_idx = len(closes) - 1
    current = closes[last_idx]

    # Determine trend
    s50 = sma_50[last_idx]
    s200 = sma_200[last_idx]
    if s50 is not None and s200 is not None:
        if current > s50 > s200:
            trend = "bullish"
        elif current < s50 < s200:
            trend = "bearish"
        else:
            trend = "neutral"
    else:
        trend = None

    return {
        "data_points": len(closes),
        "dates": dates,
        "closes": closes,
        "sma_20": sma_20,
        "sma_50": sma_50,
        "sma_200": sma_200,
        "rsi_14": rsi_14,
        "latest": {
            "date": dates[last_idx],
            "close": round(current, 2),
            "sma_20": round(sma_20[last_idx], 2) if sma_20[last_idx] is not None else None,
            "sma_50": round(s50, 2) if s50 is not None else None,
            "sma_200": round(s200, 2) if s200 is not None else None,
            "rsi_14": round(rsi_14[last_idx], 1) if rsi_14[last_idx] is not None else None,
            "trend": trend,
        },
    }
