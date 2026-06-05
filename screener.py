"""Stock screener: best-of-day (momentum) and long-term (fundamental) picks."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Optional

import numpy as np
import yfinance as yf

import cache as _cache
from models import DayPick, LongTermPick, CorrelatedStock, CorrelationResult, ScreenerResult
from fundamentals import get_fundamentals, compute_fundamental_score
from indicators import get_technicals
from news_fetcher import get_ticker_news
from validator import utcnow_iso

# Curated universe: large/mid-cap liquid US stocks + major ETFs
SCREENER_UNIVERSE: list[str] = [
    # Mega-cap tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO",
    # Tech/Software
    "ORCL", "CRM", "ADBE", "AMD", "INTC", "QCOM", "TXN", "NOW",
    # Financials
    "JPM", "BAC", "V", "MA", "GS", "MS", "BRK-B", "WFC",
    # Healthcare
    "UNH", "JNJ", "PFE", "ABBV", "MRK", "LLY", "TMO",
    # Consumer
    "WMT", "COST", "HD", "PG", "KO", "PEP", "MCD",
    # Energy
    "XOM", "CVX",
    # Industrials
    "CAT", "GE", "BA", "HON",
    # Communication/Media
    "NFLX", "DIS",
    # ETFs (for correlation reference only, excluded from fundamental screening)
    "SPY", "QQQ", "IWM",
]


def _score_day_pick(ticker: str) -> Optional[DayPick]:
    """Compute momentum score for one ticker. Returns None on failure."""
    try:
        ta = get_technicals(ticker, period="3mo")
        news = get_ticker_news(ticker, max_items=5)
        score = 0.0
        reasoning: list[str] = []

        # Momentum 1d (max 3.0)
        m1d = ta.momentum_1d or 0.0
        if m1d >= 3.0:
            score += 3.0
            reasoning.append(f"1d gain {m1d:.1f}% — strong momentum")
        elif m1d >= 1.5:
            score += 2.0
            reasoning.append(f"1d gain {m1d:.1f}% — solid momentum")
        elif m1d >= 0.5:
            score += 1.0
            reasoning.append(f"1d gain {m1d:.1f}% — mild positive")
        elif m1d < -2.0:
            score -= 1.0
            reasoning.append(f"1d drop {m1d:.1f}% — negative day")

        # 5d momentum (max 2.0)
        m5d = ta.momentum_5d or 0.0
        if m5d >= 5.0:
            score += 2.0
            reasoning.append(f"5d gain {m5d:.1f}% — strong week")
        elif m5d >= 2.0:
            score += 1.0
            reasoning.append(f"5d gain {m5d:.1f}% — positive week")

        # Volume surge (max 2.0)
        vol_ratio = ta.volume_ratio or 1.0
        if vol_ratio >= 3.0:
            score += 2.0
            reasoning.append(f"Volume {vol_ratio:.1f}x average — major surge")
        elif vol_ratio >= 2.0:
            score += 1.5
            reasoning.append(f"Volume {vol_ratio:.1f}x average — surge")
        elif vol_ratio >= 1.5:
            score += 0.75
            reasoning.append(f"Volume {vol_ratio:.1f}x average — elevated")

        # RSI not overbought (max 1.0)
        rsi = ta.rsi_14
        if rsi is not None:
            if rsi < 70:
                score += 1.0
                reasoning.append(f"RSI {rsi:.1f} — not overbought")
            else:
                reasoning.append(f"RSI {rsi:.1f} — overbought (risk)")

        # News catalyst (max 2.0)
        news_count = len(news.articles)
        if news_count >= 5:
            score += 2.0
            reasoning.append(f"{news_count} news articles — active catalyst")
        elif news_count >= 3:
            score += 1.0
            reasoning.append(f"{news_count} news articles — some coverage")

        return DayPick(
            ticker=ticker,
            name=None,
            price=ta.current_price,
            change_pct=ta.momentum_1d,
            volume_ratio=ta.volume_ratio,
            momentum_1d=ta.momentum_1d,
            momentum_5d=ta.momentum_5d,
            rsi_14=ta.rsi_14,
            news_count=news_count,
            composite_score=round(max(score, 0.0), 2),
            reasoning=reasoning,
            fetched_at=ta.fetched_at,
        )
    except Exception:
        return None


def _score_long_term_pick(ticker: str) -> Optional[LongTermPick]:
    """Compute fundamental score for one ticker. Returns None on failure or ETF."""
    try:
        f = get_fundamentals(ticker)
        if f.is_etf:
            return None
        fs = compute_fundamental_score(f)
        return LongTermPick(
            ticker=ticker,
            name=f.name,
            sector=f.sector,
            composite_score=fs.score,
            reasoning=fs.reasoning,
            pe_ratio=f.pe_ratio,
            roe=f.roe,
            revenue_growth=f.revenue_growth,
            debt_to_equity=f.debt_to_equity,
            free_cashflow=f.free_cashflow,
            profit_margin=f.profit_margin,
            fetched_at=f.fetched_at,
        )
    except Exception:
        return None


def screen_best_of_day(top_n: int = 10, universe: list[str] | None = None) -> ScreenerResult:
    """
    Score every ticker in universe by momentum, volume, RSI, news.
    Returns top_n sorted by composite_score descending.
    Cached with SCREENER_TTL.
    """
    if universe is None:
        universe = SCREENER_UNIVERSE
    today = date.today().isoformat()
    cache_key = f"screener:day:{today}:{top_n}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    picks: list[DayPick] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_score_day_pick, t): t for t in universe}
        for fut in as_completed(futures):
            result = fut.result()
            if result is not None:
                picks.append(result)

    picks.sort(key=lambda p: p.composite_score, reverse=True)
    picks = picks[:top_n]

    result = ScreenerResult(
        screener_type="best_of_day",
        fetched_at=utcnow_iso(),
        universe_size=len(universe),
        picks=picks,
    )
    _cache.set(cache_key, result, _cache.SCREENER_TTL)
    return result


def screen_long_term(top_n: int = 10, min_score: float = 5.0, universe: list[str] | None = None) -> ScreenerResult:
    """
    Score every non-ETF ticker by fundamental quality.
    Returns top_n with score >= min_score sorted descending.
    Cached with SCREENER_TTL.
    """
    if universe is None:
        universe = SCREENER_UNIVERSE
    cache_key = f"screener:longterm:{top_n}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    picks: list[LongTermPick] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_score_long_term_pick, t): t for t in universe}
        for fut in as_completed(futures):
            result = fut.result()
            if result is not None and result.composite_score >= min_score:
                picks.append(result)

    picks.sort(key=lambda p: p.composite_score, reverse=True)
    picks = picks[:top_n]

    result = ScreenerResult(
        screener_type="long_term",
        fetched_at=utcnow_iso(),
        universe_size=len(universe),
        picks=picks,
    )
    _cache.set(cache_key, result, _cache.SCREENER_TTL)
    return result


def find_correlated_stocks(
    ticker: str,
    top_n: int = 5,
    universe: list[str] | None = None,
    period: str = "1y",
) -> CorrelationResult:
    """
    Compute Pearson correlation of daily returns between ticker and each
    member of universe using 1-year history. Returns top_n most correlated.
    Cached with CORRELATION_TTL.
    """
    ticker = ticker.upper().strip()
    if universe is None:
        universe = [t for t in SCREENER_UNIVERSE if t != ticker]
    cache_key = f"correlation:{ticker}:{period}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    now_iso = utcnow_iso()

    # Batch download — one API call for all tickers
    all_tickers = [ticker] + [t for t in universe if t != ticker]
    try:
        hist = yf.download(
            " ".join(all_tickers),
            period=period,
            progress=False,
            auto_adjust=True,
            threads=True,
        )
        if hist.empty:
            return CorrelationResult(ticker=ticker, fetched_at=now_iso, period=period)

        # Handle both single and multi-ticker response formats
        if isinstance(hist.columns, pd.MultiIndex if hasattr(hist.columns, 'levels') else type(None)):
            try:
                close = hist["Close"]
            except (KeyError, TypeError):
                close = hist
        else:
            close = hist

        returns = close.pct_change().dropna()
        if ticker not in returns.columns:
            return CorrelationResult(ticker=ticker, fetched_at=now_iso, period=period)

        target_returns = returns[ticker].dropna()
        correlated: list[CorrelatedStock] = []

        for other in universe:
            if other == ticker or other not in returns.columns:
                continue
            other_returns = returns[other].dropna()
            common = target_returns.index.intersection(other_returns.index)
            if len(common) < 30:
                continue
            try:
                corr = float(np.corrcoef(
                    target_returns.loc[common].values,
                    other_returns.loc[common].values,
                )[0, 1])
                if not np.isnan(corr):
                    correlated.append(CorrelatedStock(
                        ticker=other,
                        name=None,
                        correlation=round(corr, 4),
                        sector=None,
                    ))
            except Exception:
                continue

        correlated.sort(key=lambda x: abs(x.correlation), reverse=True)
        correlated = correlated[:top_n]

    except Exception:
        correlated = []

    result = CorrelationResult(
        ticker=ticker,
        fetched_at=now_iso,
        period=period,
        correlated_stocks=correlated,
    )
    _cache.set(cache_key, result, _cache.CORRELATION_TTL)
    return result


# pandas needed for MultiIndex check
import pandas as pd  # noqa: E402
