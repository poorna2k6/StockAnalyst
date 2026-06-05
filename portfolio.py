"""Portfolio management — Supabase-backed when configured, JSON fallback for dev."""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from models import Portfolio, StockPosition

PORTFOLIO_FILE = Path("portfolio.json")


def _use_db() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_KEY"))


# ── JSON-based (dev / single-user) ───────────────────────────────────────────

def _load() -> Portfolio:
    if PORTFOLIO_FILE.exists():
        return Portfolio.model_validate(json.loads(PORTFOLIO_FILE.read_text()))
    return Portfolio()


def _save(portfolio: Portfolio) -> None:
    PORTFOLIO_FILE.write_text(portfolio.model_dump_json(indent=2))


# ── Supabase → Portfolio model converter ─────────────────────────────────────

def _db_to_portfolio(port_row: dict, position_rows: list) -> Portfolio:
    positions = {}
    for row in position_rows:
        t = row["ticker"].upper()
        positions[t] = StockPosition(
            ticker=t,
            shares=float(row["shares"]),
            avg_cost=float(row["avg_cost"]),
            added_at=row.get("added_at", datetime.utcnow().isoformat()),
        )
    return Portfolio(
        name="My Portfolio",
        cash=float(port_row.get("cash", 0)),
        positions=positions,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def get_portfolio(user_id: Optional[str] = None) -> Portfolio:
    if _use_db() and user_id:
        import supabase_client as db
        port = db.get_or_create_portfolio(user_id)
        positions = db.get_positions(port["id"])
        return _db_to_portfolio(port, positions)
    return _load()


def add_position(
    ticker: str,
    shares: float,
    avg_cost: float,
    user_id: Optional[str] = None,
) -> Portfolio:
    ticker = ticker.upper()
    if _use_db() and user_id:
        import supabase_client as db
        port = db.get_or_create_portfolio(user_id)
        db.upsert_position(port["id"], ticker, shares, avg_cost)
        positions = db.get_positions(port["id"])
        return _db_to_portfolio(port, positions)
    # JSON fallback
    portfolio = _load()
    if ticker in portfolio.positions:
        existing = portfolio.positions[ticker]
        total = existing.shares + shares
        portfolio.positions[ticker] = StockPosition(
            ticker=ticker,
            shares=total,
            avg_cost=(existing.shares * existing.avg_cost + shares * avg_cost) / total,
            added_at=existing.added_at,
        )
    else:
        portfolio.positions[ticker] = StockPosition(ticker=ticker, shares=shares, avg_cost=avg_cost)
    _save(portfolio)
    return portfolio


def remove_position(ticker: str, user_id: Optional[str] = None) -> Portfolio:
    ticker = ticker.upper()
    if _use_db() and user_id:
        import supabase_client as db
        port = db.get_or_create_portfolio(user_id)
        db.delete_position(port["id"], ticker)
        positions = db.get_positions(port["id"])
        return _db_to_portfolio(port, positions)
    portfolio = _load()
    portfolio.positions.pop(ticker, None)
    _save(portfolio)
    return portfolio


def set_cash(amount: float, user_id: Optional[str] = None) -> Portfolio:
    if _use_db() and user_id:
        import supabase_client as db
        db.update_cash(user_id, amount)
        port = db.get_or_create_portfolio(user_id)
        positions = db.get_positions(port["id"])
        return _db_to_portfolio(port, positions)
    portfolio = _load()
    portfolio.cash = amount
    _save(portfolio)
    return portfolio


def reset_portfolio(name: str = "My Portfolio", user_id: Optional[str] = None) -> Portfolio:
    if _use_db() and user_id:
        import supabase_client as db
        db.reset_user_portfolio(user_id)
        return Portfolio(name=name)
    portfolio = Portfolio(name=name)
    _save(portfolio)
    return portfolio
