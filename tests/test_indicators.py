"""Unit tests for indicators.py — pure math functions, no yfinance calls."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import numpy as np

# Import private helpers directly for unit testing
from indicators import (
    _compute_rsi,
    _compute_macd,
    _compute_bollinger,
    _compute_sma,
    _compute_ema,
    _compute_momentum,
    _derive_signals,
    _safe_float,
)


def _series(n: int = 100, start: float = 100.0, trend: float = 0.5) -> pd.Series:
    """Generate a simple trending price series."""
    prices = [start + i * trend + np.random.normal(0, 0.5) for i in range(n)]
    return pd.Series(prices, dtype=float)


def test_safe_float_normal():
    assert _safe_float(3.14) == 3.14


def test_safe_float_nan():
    assert _safe_float(float("nan")) is None


def test_safe_float_inf():
    assert _safe_float(float("inf")) is None


def test_safe_float_none():
    assert _safe_float(None) is None


def test_rsi_range():
    close = _series(100)
    rsi = _compute_rsi(close)
    assert rsi is not None
    assert 0.0 <= rsi <= 100.0


def test_rsi_insufficient_data():
    close = pd.Series([100.0, 101.0, 102.0])
    assert _compute_rsi(close, period=14) is None


def test_rsi_all_gains_is_100():
    # All gains → avg_loss = 0 → RSI should be 100
    close = pd.Series([100.0 + i for i in range(50)])
    rsi = _compute_rsi(close)
    assert rsi == 100.0


def test_rsi_all_losses_near_0():
    close = pd.Series([100.0 - i * 0.5 for i in range(50)])
    rsi = _compute_rsi(close)
    assert rsi is not None
    assert rsi < 10.0


def test_macd_returns_three_values():
    close = _series(100)
    macd_l, macd_s, macd_h = _compute_macd(close)
    assert all(v is not None for v in [macd_l, macd_s, macd_h])


def test_macd_histogram_is_line_minus_signal():
    close = _series(100)
    macd_l, macd_s, macd_h = _compute_macd(close)
    assert abs(macd_h - (macd_l - macd_s)) < 0.001


def test_macd_insufficient_data():
    close = pd.Series([100.0] * 10)
    macd_l, macd_s, macd_h = _compute_macd(close)
    assert macd_l is None


def test_bollinger_upper_above_lower():
    close = _series(50)
    upper, mid, lower, pct_b = _compute_bollinger(close)
    assert upper is not None and lower is not None and mid is not None
    assert upper > mid > lower


def test_bollinger_pct_b_range():
    close = _series(50)
    _, _, _, pct_b = _compute_bollinger(close)
    # pct_b can be outside 0-1 for breakouts, but for a normal series stays close
    assert pct_b is not None
    assert -1.0 <= pct_b <= 2.0


def test_bollinger_insufficient():
    close = pd.Series([100.0] * 5)
    upper, mid, lower, pct_b = _compute_bollinger(close, period=20)
    assert upper is None


def test_sma_correct():
    close = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    sma = _compute_sma(close, period=5)
    assert sma == 3.0


def test_sma_insufficient():
    close = pd.Series([1.0, 2.0])
    assert _compute_sma(close, period=5) is None


def test_ema_returns_float():
    close = _series(50)
    ema = _compute_ema(close, span=12)
    assert ema is not None
    assert isinstance(ema, float)


def test_momentum_positive():
    # Upward trend
    close = pd.Series([100.0] * 10 + [110.0])
    m = _compute_momentum(close, lookback=10)
    assert m is not None
    assert m > 0


def test_momentum_negative():
    close = pd.Series([110.0] * 10 + [100.0])
    m = _compute_momentum(close, lookback=10)
    assert m is not None
    assert m < 0


def test_momentum_insufficient():
    close = pd.Series([100.0])
    assert _compute_momentum(close, lookback=5) is None


def test_derive_signals_bullish():
    ta = {
        "rsi_14": 45.0,            # neutral
        "current_price": 110.0,
        "sma_200": 100.0,           # price above SMA200 → bullish vote
        "sma_20": 108.0,
        "sma_50": 105.0,            # sma20 > sma50 → bullish
        "macd_histogram": 0.5,      # positive → bullish
        "bb_pct_b": 0.5,
        "volume_ratio": 1.0,
    }
    signals, trend = _derive_signals(ta)
    assert trend == "bullish"
    assert len(signals) > 0


def test_derive_signals_bearish():
    ta = {
        "rsi_14": 55.0,
        "current_price": 90.0,
        "sma_200": 100.0,           # price below SMA200 → bearish
        "sma_20": 92.0,
        "sma_50": 95.0,             # sma20 < sma50 → bearish
        "macd_histogram": -0.5,     # negative → bearish
        "bb_pct_b": 0.5,
        "volume_ratio": 1.0,
    }
    signals, trend = _derive_signals(ta)
    assert trend == "bearish"


def test_derive_signals_rsi_oversold():
    ta = {
        "rsi_14": 25.0,
        "current_price": 100.0,
        "sma_200": None,
        "sma_20": None,
        "sma_50": None,
        "macd_histogram": None,
        "bb_pct_b": None,
        "volume_ratio": None,
    }
    signals, trend = _derive_signals(ta)
    assert any("oversold" in s.lower() for s in signals)


def test_derive_signals_volume_surge():
    ta = {
        "rsi_14": 50.0,
        "current_price": 100.0,
        "sma_200": None,
        "sma_20": None,
        "sma_50": None,
        "macd_histogram": None,
        "bb_pct_b": None,
        "volume_ratio": 3.0,
    }
    signals, _ = _derive_signals(ta)
    assert any("surge" in s.lower() or "volume" in s.lower() for s in signals)
