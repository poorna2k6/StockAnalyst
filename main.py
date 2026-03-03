"""FastAPI application for the Stock Portfolio Advisor."""

from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

import analyzer
import portfolio as portfolio_store
import advisor as ai_advisor
from models import (
    AddPositionRequest,
    RemovePositionRequest,
    PortfolioSummary,
    StockQuote,
    AdviceRequest,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Stock Portfolio Advisor",
    description="Track your stock portfolio and get AI-powered investment advice.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/", tags=["health"])
def root():
    return {"status": "ok", "service": "Stock Portfolio Advisor"}


# --- Portfolio endpoints ---

@app.get("/portfolio", response_model=PortfolioSummary, tags=["portfolio"])
def get_portfolio():
    """Return live portfolio summary with current prices."""
    try:
        port = portfolio_store.get_portfolio()
        return analyzer.build_portfolio_summary(port)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/portfolio/position", response_model=PortfolioSummary, tags=["portfolio"])
def add_position(req: AddPositionRequest):
    """Add or update a stock position."""
    try:
        port = portfolio_store.add_position(req.ticker, req.shares, req.avg_cost)
        return analyzer.build_portfolio_summary(port)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/portfolio/position", response_model=PortfolioSummary, tags=["portfolio"])
def remove_position(req: RemovePositionRequest):
    """Remove a stock position."""
    port = portfolio_store.remove_position(req.ticker)
    return analyzer.build_portfolio_summary(port)


@app.post("/portfolio/cash", tags=["portfolio"])
def set_cash(amount: float):
    """Set cash balance."""
    port = portfolio_store.set_cash(amount)
    return {"cash": port.cash}


@app.post("/portfolio/reset", tags=["portfolio"])
def reset_portfolio(name: str = "My Portfolio"):
    """Reset portfolio to empty."""
    portfolio_store.reset_portfolio(name)
    return {"message": f"Portfolio '{name}' reset successfully."}


# --- Stock quote endpoints ---

@app.get("/quote/{ticker}", response_model=StockQuote, tags=["quotes"])
def get_quote(ticker: str):
    """Get a real-time stock quote."""
    try:
        return analyzer.get_quote(ticker.upper())
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Could not fetch quote for {ticker}: {e}")


@app.get("/history/{ticker}", tags=["quotes"])
def get_history(ticker: str, period: str = "1y"):
    """Get historical OHLCV data. Period examples: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y."""
    try:
        data = analyzer.get_historical_prices(ticker.upper(), period)
        if not data:
            raise HTTPException(status_code=404, detail=f"No data for {ticker}")
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Advisor endpoints ---

@app.get("/advice", tags=["advisor"])
def get_advice(risk_tolerance: str = "moderate", question: str | None = None):
    """Get AI-powered portfolio advice from Claude."""
    try:
        port = portfolio_store.get_portfolio()
        summary = analyzer.build_portfolio_summary(port)
        advice = ai_advisor.get_advice(summary, question=question, risk_tolerance=risk_tolerance)
        return {"advice": advice}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/advice", tags=["advisor"])
def get_advice_with_payload(req: AdviceRequest):
    """Get AI advice for a given portfolio summary payload."""
    advice = ai_advisor.get_advice(req.portfolio_summary, req.question, req.risk_tolerance)
    return {"advice": advice}
