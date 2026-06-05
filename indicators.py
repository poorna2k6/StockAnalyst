"""Technical indicator calculations from yfinance OHLCV history."""

from datetime import timezone, datetime
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

import cache as _cache
from models import TechnicalAnalysis
from validator import utcnow_iso


def _safe_float(val) -> Optional[float]:
    try:
        f = float(val)
        return None if (np.isnan(f) or np.isinf(f)) else round(f, 4)
    except Exception:
        return None


def _compute_rsi(close: pd.Series, period: int = 14) -> Optional[float]:
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    last_loss = avg_loss.iloc[-1]
    if last_loss == 0:
        return 100.0
    rs = avg_gain.iloc[-1] / last_loss
    return _safe_float(100.0 - (100.0 / (1.0 + rs)))


def _compute_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Returns (macd_line, signal_line, histogram)."""
    if len(close) < slow + signal_period:
        return None, None, None
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line
    return (
        _safe_float(macd_line.iloc[-1]),
        _safe_float(signal_line.iloc[-1]),
        _safe_float(histogram.iloc[-1]),
    )


def _compute_bollinger(
    close: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """Returns (upper, middle, lower, pct_b)."""
    if len(close) < period:
        return None, None, None, None
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = sma + num_std * std
    lower = sma - num_std * std
    last_upper = upper.iloc[-1]
    last_lower = lower.iloc[-1]
    last_close = close.iloc[-1]
    band_width = last_upper - last_lower
    pct_b = ((last_close - last_lower) / band_width) if band_width != 0 else None
    return (
        _safe_float(last_upper),
        _safe_float(sma.iloc[-1]),
        _safe_float(last_lower),
        _safe_float(pct_b),
    )


def _compute_sma(close: pd.Series, period: int) -> Optional[float]:
    if len(close) < period:
        return None
    return _safe_float(close.rolling(period).mean().iloc[-1])


def _compute_ema(close: pd.Series, span: int) -> Optional[float]:
    if len(close) < span:
        return None
    return _safe_float(close.ewm(span=span, adjust=False).mean().iloc[-1])


def _compute_momentum(close: pd.Series, lookback: int) -> Optional[float]:
    if len(close) <= lookback:
        return None
    past = close.iloc[-(lookback + 1)]
    current = close.iloc[-1]
    if past == 0:
        return None
    return _safe_float((current - past) / past * 100)


def _derive_signals(ta: dict) -> tuple[list[str], str]:
    signals: list[str] = []
    bull_votes = 0
    bear_votes = 0

    rsi = ta.get("rsi_14")
    if rsi is not None:
        if rsi < 30:
            signals.append(f"RSI {rsi:.1f} — oversold (potential reversal)")
            bull_votes += 1
        elif rsi > 70:
            signals.append(f"RSI {rsi:.1f} — overbought (caution)")
            bear_votes += 1
        elif 40 <= rsi <= 60:
            signals.append(f"RSI {rsi:.1f} — neutral momentum")

    sma_20 = ta.get("sma_20")
    sma_50 = ta.get("sma_50")
    sma_200 = ta.get("sma_200")
    price = ta.get("current_price")
    if price and sma_200:
        if price > sma_200:
            signals.append("Price above 200-day SMA (long-term uptrend)")
            bull_votes += 1
        else:
            signals.append("Price below 200-day SMA (long-term downtrend)")
            bear_votes += 1
    if sma_20 and sma_50:
        if sma_20 > sma_50:
            signals.append("SMA20 > SMA50 (short-term bullish)")
            bull_votes += 1
        else:
            signals.append("SMA20 < SMA50 (short-term bearish)")
            bear_votes += 1

    macd_hist = ta.get("macd_histogram")
    macd_line = ta.get("macd_line")
    if macd_hist is not None and macd_line is not None:
        if macd_hist > 0:
            signals.append("MACD histogram positive (bullish momentum)")
            bull_votes += 1
        else:
            signals.append("MACD histogram negative (bearish momentum)")
            bear_votes += 1

    pct_b = ta.get("bb_pct_b")
    if pct_b is not None:
        if pct_b < 0.1:
            signals.append("Price near Bollinger lower band (oversold zone)")
            bull_votes += 1
        elif pct_b > 0.9:
            signals.append("Price near Bollinger upper band (overbought zone)")
            bear_votes += 1

    vol_ratio = ta.get("volume_ratio")
    if vol_ratio is not None and vol_ratio > 2.0:
        signals.append(f"Volume surge: {vol_ratio:.1f}x 20-day average")

    if bull_votes > bear_votes:
        trend = "bullish"
    elif bear_votes > bull_votes:
        trend = "bearish"
    else:
        trend = "neutral"

    return signals, trend


def get_technicals(ticker: str, period: str = "6mo") -> TechnicalAnalysis:
    """
    Fetch OHLCV history and compute all technical indicators.
    Returns TechnicalAnalysis model with fetched_at timestamp.
    Cached with TECHNICALS_TTL.
    """
    ticker = ticker.upper().strip()
    cache_key = f"technicals:{ticker}:{period}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    now_iso = utcnow_iso()
    hist = yf.Ticker(ticker).history(period=period)

    if hist.empty or len(hist) < 5:
        result = TechnicalAnalysis(
            ticker=ticker,
            period=period,
            fetched_at=now_iso,
            signals=["Insufficient historical data"],
        )
        _cache.set(cache_key, result, 60)
        return result

    close = hist["Close"].dropna()
    volume = hist["Volume"].dropna()

    macd_l, macd_s, macd_h = _compute_macd(close)
    bb_u, bb_m, bb_l, bb_pct = _compute_bollinger(close)

    vol_sma20: Optional[float] = None
    vol_ratio: Optional[float] = None
    if len(volume) >= 20:
        vol_sma20 = _safe_float(volume.rolling(20).mean().iloc[-1])
        last_vol = float(volume.iloc[-1])
        if vol_sma20 and vol_sma20 > 0:
            vol_ratio = _safe_float(last_vol / vol_sma20)

    ta_dict = {
        "ticker": ticker,
        "period": period,
        "fetched_at": now_iso,
        "current_price": _safe_float(close.iloc[-1]),
        "sma_20": _compute_sma(close, 20),
        "sma_50": _compute_sma(close, 50),
        "sma_200": _compute_sma(close, 200),
        "ema_12": _compute_ema(close, 12),
        "ema_26": _compute_ema(close, 26),
        "rsi_14": _compute_rsi(close),
        "macd_line": macd_l,
        "macd_signal": macd_s,
        "macd_histogram": macd_h,
        "bb_upper": bb_u,
        "bb_middle": bb_m,
        "bb_lower": bb_l,
        "bb_pct_b": bb_pct,
        "volume_sma_20": vol_sma20,
        "volume_ratio": vol_ratio,
        "momentum_1d": _compute_momentum(close, 1),
        "momentum_5d": _compute_momentum(close, 5),
        "momentum_1mo": _compute_momentum(close, 21),
        "momentum_3mo": _compute_momentum(close, 63),
    }

    signals, trend = _derive_signals(ta_dict)
    ta_dict["signals"] = signals
    ta_dict["trend"] = trend

    result = TechnicalAnalysis(**ta_dict)
    _cache.set(cache_key, result, _cache.TECHNICALS_TTL)
    return result
