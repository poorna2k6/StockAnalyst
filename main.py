"""FastAPI application for the Stock Portfolio Advisor."""

from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional

import analyzer
import portfolio as portfolio_store
import advisor as ai_advisor
import cache as _cache
from models import (
    AddPositionRequest,
    RemovePositionRequest,
    PortfolioSummary,
    StockQuote,
    AdviceRequest,
    TickerValidation,
    TechnicalAnalysis,
    FundamentalsData,
    FundamentalScore,
    AnalystData,
    InstitutionalData,
    NewsBundle,
    ScreenerResult,
    CorrelationResult,
    DeepStockAnalysis,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Stock Portfolio Advisor",
    description=(
        "Track your stock portfolio and get AI-powered investment advice. "
        "All AI analysis is grounded in real-time Yahoo Finance data — no hallucinations."
    ),
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/", tags=["health"])
def root():
    return {"status": "ok", "service": "Stock Portfolio Advisor", "version": "2.0.0"}


# ── Portfolio endpoints ────────────────────────────────────────────────────────

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


# ── Quote endpoints ────────────────────────────────────────────────────────────

@app.get("/quote/{ticker}", response_model=StockQuote, tags=["quotes"])
def get_quote(ticker: str):
    """Get a real-time stock quote."""
    try:
        return analyzer.get_quote(ticker.upper())
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Could not fetch quote for {ticker}: {e}")


@app.get("/history/{ticker}", tags=["quotes"])
def get_history(ticker: str, period: str = "1y"):
    """Get historical OHLCV data. Period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y."""
    try:
        data = analyzer.get_historical_prices(ticker.upper(), period)
        if not data:
            raise HTTPException(status_code=404, detail=f"No data for {ticker}")
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/validate/{ticker}", response_model=TickerValidation, tags=["quotes"])
def validate_ticker(ticker: str):
    """Validate a ticker symbol against Yahoo Finance."""
    return analyzer.validate_ticker(ticker.upper())


# ── Portfolio advisor ──────────────────────────────────────────────────────────

@app.get("/advice", tags=["advisor"])
def get_advice(risk_tolerance: str = "moderate", question: Optional[str] = None):
    """Get AI-powered portfolio advice from Claude (grounded in live portfolio data)."""
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


# ── Deep analysis ──────────────────────────────────────────────────────────────

@app.get("/analyze/{ticker}", tags=["analysis"])
def analyze_stock(ticker: str, question: Optional[str] = None):
    """
    Full in/out analysis: technicals + fundamentals + analyst + institutional +
    news + AI synthesis grounded in fetched data.
    """
    ticker = ticker.upper()
    validation = analyzer.validate_ticker(ticker)
    if not validation.valid:
        raise HTTPException(status_code=404, detail=validation.error or f"Invalid ticker: {ticker}")
    try:
        deep = analyzer.build_deep_analysis(ticker)
        deep.ai_analysis = ai_advisor.get_deep_analysis_advice(deep, question=question)
        return deep
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/technicals/{ticker}", response_model=TechnicalAnalysis, tags=["analysis"])
def get_technicals(ticker: str, period: str = "6mo"):
    """RSI, MACD, Bollinger Bands, moving averages, volume, and momentum."""
    ticker = ticker.upper()
    validation = analyzer.validate_ticker(ticker)
    if not validation.valid:
        raise HTTPException(status_code=404, detail=validation.error)
    try:
        from indicators import get_technicals as _get_technicals
        return _get_technicals(ticker, period)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/fundamentals/{ticker}", response_model=FundamentalsData, tags=["analysis"])
def get_fundamentals(ticker: str):
    """P/E, P/B, ROE, D/E, revenue growth, FCF, margins, analyst target."""
    ticker = ticker.upper()
    validation = analyzer.validate_ticker(ticker)
    if not validation.valid:
        raise HTTPException(status_code=404, detail=validation.error)
    try:
        from fundamentals import get_fundamentals as _get_fundamentals
        return _get_fundamentals(ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/fundamentals/{ticker}/score", response_model=FundamentalScore, tags=["analysis"])
def get_fundamental_score(ticker: str):
    """Rule-based fundamental quality score (0–10) with detailed reasoning."""
    ticker = ticker.upper()
    validation = analyzer.validate_ticker(ticker)
    if not validation.valid:
        raise HTTPException(status_code=404, detail=validation.error)
    try:
        from fundamentals import get_fundamentals as _gf, compute_fundamental_score
        return compute_fundamental_score(_gf(ticker))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analyst/{ticker}", response_model=AnalystData, tags=["analysis"])
def get_analyst_data(ticker: str):
    """Analyst recommendations, consensus, and upcoming earnings date."""
    ticker = ticker.upper()
    validation = analyzer.validate_ticker(ticker)
    if not validation.valid:
        raise HTTPException(status_code=404, detail=validation.error)
    try:
        from fundamentals import get_analyst_data as _get_analyst
        return _get_analyst(ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/institutions/{ticker}", response_model=InstitutionalData, tags=["analysis"])
def get_institutional_data(ticker: str):
    """Institutional holders, insider ownership %, and top 10 holders."""
    ticker = ticker.upper()
    validation = analyzer.validate_ticker(ticker)
    if not validation.valid:
        raise HTTPException(status_code=404, detail=validation.error)
    try:
        from fundamentals import get_institutional_data as _get_inst
        return _get_inst(ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── News endpoints ─────────────────────────────────────────────────────────────

@app.get("/news/{ticker}", response_model=NewsBundle, tags=["news"])
def get_ticker_news(ticker: str, max_items: int = 10):
    """Recent news articles for a specific ticker from Yahoo Finance."""
    ticker = ticker.upper()
    validation = analyzer.validate_ticker(ticker)
    if not validation.valid:
        raise HTTPException(status_code=404, detail=validation.error)
    try:
        from news_fetcher import get_ticker_news as _get_news
        return _get_news(ticker, max_items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/news", response_model=NewsBundle, tags=["news"])
def get_market_news(max_items: int = 15):
    """Broad market news via SPY/QQQ/IWM Yahoo Finance feeds."""
    try:
        from news_fetcher import get_market_news as _get_market_news
        return _get_market_news(max_items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Screener endpoints ─────────────────────────────────────────────────────────

@app.get("/screener/best-day", tags=["screener"])
def best_of_day(top_n: int = 10):
    """
    Top momentum picks for today ranked by real data
    (price momentum, volume surge, RSI, news catalysts).
    Grounded — scores curated 40-ticker universe only.
    """
    try:
        from screener import screen_best_of_day
        result = screen_best_of_day(top_n=top_n)
        narrative = ai_advisor.get_screener_advice(result)
        result.ai_narrative = narrative
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/screener/long-term", tags=["screener"])
def long_term_picks(top_n: int = 10, min_score: float = 5.0):
    """
    Top long-term quality picks ranked by fundamental score
    (ROE, revenue growth, FCF, margins, PEG, D/E).
    Grounded — no AI-invented picks.
    """
    try:
        from screener import screen_long_term
        result = screen_long_term(top_n=top_n, min_score=min_score)
        narrative = ai_advisor.get_screener_advice(result)
        result.ai_narrative = narrative
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/screener/correlated/{ticker}", response_model=CorrelationResult, tags=["screener"])
def correlated_stocks(ticker: str, top_n: int = 5):
    """
    Find most correlated stocks by Pearson correlation of 1-year daily returns.
    Real computation — not guessed from sector alone.
    """
    ticker = ticker.upper()
    validation = analyzer.validate_ticker(ticker)
    if not validation.valid:
        raise HTTPException(status_code=404, detail=validation.error)
    try:
        from screener import find_correlated_stocks
        return find_correlated_stocks(ticker, top_n=top_n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Cache management ───────────────────────────────────────────────────────────

@app.get("/cache/stats", tags=["admin"])
def cache_stats():
    """Return cache hit/miss statistics."""
    return _cache.stats()


@app.post("/cache/clear", tags=["admin"])
def clear_cache():
    """Clear all in-memory cached data."""
    _cache.clear()
    return {"message": "Cache cleared."}
