"""Tests for technical analysis indicators."""
from fesi.analysis.ta import sma, rsi, compute_indicators


def test_sma_basic():
    closes = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = sma(closes, 3)
    assert result[0] is None
    assert result[1] is None
    assert result[2] == 2.0  # (1+2+3)/3
    assert result[3] == 3.0  # (2+3+4)/3
    assert result[4] == 4.0  # (3+4+5)/3


def test_sma_period_exceeds_data():
    result = sma([1.0, 2.0], 5)
    assert all(v is None for v in result)


def test_sma_empty():
    assert sma([], 3) == []


def test_rsi_all_gains():
    # Steadily rising prices → RSI should be near 100
    closes = [float(i) for i in range(20)]
    result = rsi(closes, 14)
    assert result[14] is not None
    assert result[-1] is not None
    assert result[-1] > 95.0


def test_rsi_all_losses():
    # Steadily falling prices → RSI should be near 0
    closes = [float(20 - i) for i in range(20)]
    result = rsi(closes, 14)
    assert result[-1] is not None
    assert result[-1] < 5.0


def test_rsi_mixed():
    # Alternating gains and losses → RSI should be near 50
    closes = [10.0 + (i % 2) for i in range(20)]
    result = rsi(closes, 14)
    assert result[-1] is not None
    assert 40.0 < result[-1] < 60.0


def test_compute_indicators_full():
    # 250 data points — all indicators should be populated
    prices = [{"date": f"2026-01-{i:03d}", "close": 100.0 + i * 0.1} for i in range(250)]
    ind = compute_indicators(prices)
    assert ind["data_points"] == 250
    assert ind["latest"] is not None
    assert ind["latest"]["sma_20"] is not None
    assert ind["latest"]["sma_50"] is not None
    assert ind["latest"]["sma_200"] is not None
    assert ind["latest"]["rsi_14"] is not None
    assert ind["latest"]["trend"] is not None
    assert len(ind["sma_20"]) == 250


def test_compute_indicators_sparse():
    # Only 10 data points — SMA 50 and 200 should be None
    prices = [{"date": f"2026-01-{i:02d}", "close": 50.0 + i} for i in range(10)]
    ind = compute_indicators(prices)
    assert ind["data_points"] == 10
    assert ind["latest"]["sma_20"] is None
    assert ind["latest"]["sma_50"] is None
    assert ind["latest"]["sma_200"] is None
