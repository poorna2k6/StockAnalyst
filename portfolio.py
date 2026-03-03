"""Portfolio management: persist and mutate portfolio positions."""

import json
from pathlib import Path
from datetime import datetime

from models import Portfolio, StockPosition

PORTFOLIO_FILE = Path("portfolio.json")


def _load() -> Portfolio:
    if PORTFOLIO_FILE.exists():
        data = json.loads(PORTFOLIO_FILE.read_text())
        return Portfolio.model_validate(data)
    return Portfolio()


def _save(portfolio: Portfolio) -> None:
    PORTFOLIO_FILE.write_text(portfolio.model_dump_json(indent=2))


def get_portfolio() -> Portfolio:
    return _load()


def add_position(ticker: str, shares: float, avg_cost: float) -> Portfolio:
    portfolio = _load()
    ticker = ticker.upper()
    if ticker in portfolio.positions:
        existing = portfolio.positions[ticker]
        total_shares = existing.shares + shares
        total_cost = existing.shares * existing.avg_cost + shares * avg_cost
        portfolio.positions[ticker] = StockPosition(
            ticker=ticker,
            shares=total_shares,
            avg_cost=total_cost / total_shares,
            added_at=existing.added_at,
        )
    else:
        portfolio.positions[ticker] = StockPosition(
            ticker=ticker,
            shares=shares,
            avg_cost=avg_cost,
        )
    _save(portfolio)
    return portfolio


def remove_position(ticker: str) -> Portfolio:
    portfolio = _load()
    ticker = ticker.upper()
    portfolio.positions.pop(ticker, None)
    _save(portfolio)
    return portfolio


def set_cash(amount: float) -> Portfolio:
    portfolio = _load()
    portfolio.cash = amount
    _save(portfolio)
    return portfolio


def reset_portfolio(name: str = "My Portfolio") -> Portfolio:
    portfolio = Portfolio(name=name)
    _save(portfolio)
    return portfolio
