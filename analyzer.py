"""Fetch live stock data and compute portfolio analytics."""

from typing import Optional
import yfinance as yf

from models import (
    Portfolio,
    PortfolioSummary,
    PositionSummary,
    StockQuote,
)


def get_quote(ticker: str) -> StockQuote:
    info = yf.Ticker(ticker).info
    price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
    prev_close = info.get("previousClose") or price
    change = price - prev_close
    change_pct = (change / prev_close * 100) if prev_close else 0.0
    return StockQuote(
        ticker=ticker.upper(),
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


def get_quotes(tickers: list[str]) -> dict[str, StockQuote]:
    return {ticker: get_quote(ticker) for ticker in tickers}


def build_portfolio_summary(portfolio: Portfolio) -> PortfolioSummary:
    tickers = list(portfolio.positions.keys())
    quotes = get_quotes(tickers) if tickers else {}

    positions: list[PositionSummary] = []
    total_value = portfolio.cash
    total_cost = portfolio.cash

    # First pass: compute values
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

    # Second pass: compute weights
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
    hist = yf.Ticker(ticker).history(period=period)
    if hist.empty:
        return {}
    return {
        "dates": hist.index.strftime("%Y-%m-%d").tolist(),
        "open": hist["Open"].round(2).tolist(),
        "high": hist["High"].round(2).tolist(),
        "low": hist["Low"].round(2).tolist(),
        "close": hist["Close"].round(2).tolist(),
        "volume": hist["Volume"].tolist(),
    }
