"""Fetch live stock data and compute portfolio analytics."""

from typing import Optional
import yfinance as yf

import cache as _cache
from models import (
    Portfolio,
    PortfolioSummary,
    PositionSummary,
    StockQuote,
    DeepStockAnalysis,
    TickerValidation,
)
from validator import utcnow_iso


def validate_ticker(ticker: str) -> TickerValidation:
    """Validate a ticker symbol via yfinance. Cached."""
    from validator import validate_ticker as _vt
    ticker = ticker.upper().strip()
    is_valid, name, error = _vt(ticker)
    return TickerValidation(
        ticker=ticker,
        valid=is_valid,
        name=name,
        error=error,
        fetched_at=utcnow_iso(),
    )


def get_quote(ticker: str) -> StockQuote:
    """Get a real-time stock quote. Cached with QUOTE_TTL."""
    ticker = ticker.upper().strip()
    cache_key = f"quote:{ticker}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    info = yf.Ticker(ticker).info
    price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
    prev_close = info.get("previousClose") or price
    change = price - prev_close
    change_pct = (change / prev_close * 100) if prev_close else 0.0

    result = StockQuote(
        ticker=ticker,
        name=info.get("longName") or info.get("shortName"),
        price=price,
        change=change,
        change_pct=change_pct,
        volume=info.get("volume") or 0,
        market_cap=info.get("marketCap"),
        pe_ratio=info.get("trailingPE"),
        week_52_high=info.get("fiftyTwoWeekHigh"),
        week_52_low=info.get("fiftyTwoWeekLow"),
    )
    _cache.set(cache_key, result, _cache.QUOTE_TTL)
    return result


def get_quotes(tickers: list[str]) -> dict[str, StockQuote]:
    return {ticker: get_quote(ticker) for ticker in tickers}


def build_portfolio_summary(portfolio: Portfolio) -> PortfolioSummary:
    tickers = list(portfolio.positions.keys())
    quotes = get_quotes(tickers) if tickers else {}

    positions: list[PositionSummary] = []
    total_value = portfolio.cash
    total_cost = portfolio.cash
    raw_positions = []

    for ticker, pos in portfolio.positions.items():
        quote = quotes.get(ticker)
        current_price = quote.price if quote else pos.avg_cost
        current_value = pos.shares * current_price
        cost_basis = pos.shares * pos.avg_cost
        gain_loss = current_value - cost_basis
        gain_loss_pct = (gain_loss / cost_basis * 100) if cost_basis else 0.0
        total_value += current_value
        total_cost += cost_basis
        raw_positions.append((ticker, pos, current_price, current_value, cost_basis, gain_loss, gain_loss_pct))

    for ticker, pos, current_price, current_value, cost_basis, gain_loss, gain_loss_pct in raw_positions:
        weight = (current_value / total_value * 100) if total_value else 0.0
        positions.append(PositionSummary(
            ticker=ticker,
            shares=pos.shares,
            avg_cost=pos.avg_cost,
            current_price=current_price,
            current_value=current_value,
            cost_basis=cost_basis,
            gain_loss=gain_loss,
            gain_loss_pct=gain_loss_pct,
            weight=weight,
        ))

    positions.sort(key=lambda p: p.current_value, reverse=True)
    total_gain_loss = total_value - total_cost
    total_gain_loss_pct = (total_gain_loss / total_cost * 100) if total_cost else 0.0

    return PortfolioSummary(
        name=portfolio.name,
        total_value=total_value,
        total_cost=total_cost,
        total_gain_loss=total_gain_loss,
        total_gain_loss_pct=total_gain_loss_pct,
        cash=portfolio.cash,
        positions=positions,
    )


def get_historical_prices(ticker: str, period: str = "1y") -> dict:
    """Return historical OHLCV data as a dict of lists."""
    ticker = ticker.upper().strip()
    cache_key = f"history:{ticker}:{period}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    hist = yf.Ticker(ticker).history(period=period)
    if hist.empty:
        return {}
    result = {
        "dates": hist.index.strftime("%Y-%m-%d").tolist(),
        "open": hist["Open"].round(2).tolist(),
        "high": hist["High"].round(2).tolist(),
        "low": hist["Low"].round(2).tolist(),
        "close": hist["Close"].round(2).tolist(),
        "volume": hist["Volume"].tolist(),
    }
    _cache.set(cache_key, result, _cache.TECHNICALS_TTL)
    return result


def build_deep_analysis(ticker: str) -> DeepStockAnalysis:
    """
    Aggregate all data sources into a single DeepStockAnalysis object.
    Each sub-fetch is independently cached.
    """
    from fundamentals import get_fundamentals, compute_fundamental_score, get_analyst_data, get_institutional_data
    from indicators import get_technicals
    from news_fetcher import get_ticker_news

    ticker = ticker.upper().strip()
    now_iso = utcnow_iso()

    quote = get_quote(ticker)
    technicals = get_technicals(ticker)
    fundamentals = get_fundamentals(ticker)
    fundamental_score = compute_fundamental_score(fundamentals)
    analyst_data = get_analyst_data(ticker)
    institutional_data = get_institutional_data(ticker)
    news = get_ticker_news(ticker)

    return DeepStockAnalysis(
        ticker=ticker,
        name=quote.name,
        fetched_at=now_iso,
        data_sources=["yfinance.info", "yfinance.history", "yfinance.news",
                      "yfinance.recommendations", "yfinance.institutional_holders"],
        quote=quote,
        technicals=technicals,
        fundamentals=fundamentals,
        fundamental_score=fundamental_score,
        analyst_data=analyst_data,
        institutional_data=institutional_data,
        news=news,
    )
