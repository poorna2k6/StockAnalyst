"""FastAPI application — AI Stock Analyst (production-ready with Supabase auth)."""

from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

import os
import re
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import analyzer
import portfolio as portfolio_store
import advisor as ai_advisor
import cache as _cache
from auth_middleware import get_current_user, require_user
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

# ── Known ETF and index tickers for chat intent detection ─────────────────────
_ETF_TICKERS = ["SPY", "QQQ", "VTI", "SCHD", "IWM", "GLD", "TLT", "XLK", "XLF", "VNQ", "ARKK", "DIA"]
_INDEX_TICKERS = ["SPY", "QQQ", "IWM", "DIA"]
_PICKS_POOL = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "JPM", "V", "MA",
    "UNH", "JNJ", "XOM", "PG", "HD", "BAC", "ABBV", "MRK", "COST", "AVGO",
    "AMD", "CRM", "NFLX", "ADBE", "ORCL", "WMT", "DIS", "NKE", "INTC", "PYPL",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def _get_rate_limit_key(request: Request) -> str:
    """Rate-limit by user_id when authenticated, fall back to IP."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            from auth_middleware import _decode
            payload = _decode(auth[7:])
            return f"user:{payload['sub']}"
        except Exception:
            pass
    return get_remote_address(request)


limiter = Limiter(key_func=_get_rate_limit_key)

app = FastAPI(
    title="AI Stock Analyst",
    description="Real-time AI-powered stock analysis. All AI grounded in live Yahoo Finance data.",
    version="3.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS — explicit allowed origins only ──────────────────────────────────────
_allowed_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
]
if os.getenv("FRONTEND_URL"):
    _allowed_origins.append(os.getenv("FRONTEND_URL"))

# In dev without FRONTEND_URL set, allow Vercel previews; in production lock to exact domain.
_origin_regex = None if os.getenv("ENVIRONMENT") == "production" else r"https://.*\.vercel\.app"

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/", tags=["health"])
def root():
    return {
        "status": "ok",
        "service": "AI Stock Analyst",
        "version": "3.0.0",
        "supabase": bool(os.getenv("SUPABASE_URL")),
        "claude": bool(os.getenv("ANTHROPIC_API_KEY")),
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
    }


# ── User settings ─────────────────────────────────────────────────────────────

@app.get("/settings", tags=["user"])
def get_settings(user_id: str = Depends(require_user)):
    try:
        import supabase_client as db
        settings = db.get_user_settings(user_id) if db.is_configured() else {}
        # Never expose raw API keys
        safe = {k: v for k, v in settings.items() if not k.endswith("_key")}
        safe["has_claude_key"] = bool(settings.get("byok_claude_key"))
        safe["has_gemini_key"] = bool(settings.get("byok_gemini_key"))
        return safe
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/settings", tags=["user"])
def update_settings(updates: dict, user_id: str = Depends(require_user)):
    try:
        import supabase_client as db
        allowed = {"preferred_model", "use_byok", "byok_claude_key", "byok_gemini_key"}
        filtered = {k: v for k, v in updates.items() if k in allowed}
        if not db.is_configured():
            return {"message": "Supabase not configured — settings not persisted"}
        saved = db.upsert_user_settings(user_id, filtered)
        safe = {k: v for k, v in saved.items() if not k.endswith("_key")}
        safe["has_claude_key"] = bool(saved.get("byok_claude_key"))
        safe["has_gemini_key"] = bool(saved.get("byok_gemini_key"))
        return safe
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Portfolio endpoints ────────────────────────────────────────────────────────

@app.get("/portfolio", response_model=PortfolioSummary, tags=["portfolio"])
def get_portfolio(user_id: str = Depends(require_user)):
    try:
        port = portfolio_store.get_portfolio(user_id)
        return analyzer.build_portfolio_summary(port)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/portfolio/position", response_model=PortfolioSummary, tags=["portfolio"])
def add_position(req: AddPositionRequest, user_id: str = Depends(require_user)):
    try:
        port = portfolio_store.add_position(req.ticker, req.shares, req.avg_cost, user_id)
        return analyzer.build_portfolio_summary(port)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/portfolio/position", response_model=PortfolioSummary, tags=["portfolio"])
def remove_position(req: RemovePositionRequest, user_id: str = Depends(require_user)):
    port = portfolio_store.remove_position(req.ticker, user_id)
    return analyzer.build_portfolio_summary(port)


@app.post("/portfolio/cash", tags=["portfolio"])
def set_cash(amount: float, user_id: str = Depends(require_user)):
    port = portfolio_store.set_cash(amount, user_id)
    return {"cash": port.cash}


@app.post("/portfolio/reset", tags=["portfolio"])
def reset_portfolio(name: str = "My Portfolio", user_id: str = Depends(require_user)):
    portfolio_store.reset_portfolio(name, user_id)
    return {"message": f"Portfolio '{name}' reset."}


# ── Watchlist ──────────────────────────────────────────────────────────────────

@app.get("/watchlist", tags=["watchlist"])
def get_watchlist(user_id: str = Depends(require_user)):
    try:
        import supabase_client as db
        if not db.is_configured():
            return []
        tickers = db.get_watchlist(user_id)
        # Enrich with live quotes
        result = []
        for row in tickers:
            try:
                quote = analyzer.get_quote(row["ticker"])
                result.append({**row, "quote": quote.model_dump()})
            except Exception:
                result.append(row)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/watchlist/{ticker}", tags=["watchlist"])
def add_watchlist(ticker: str, user_id: str = Depends(require_user)):
    try:
        import supabase_client as db
        if not db.is_configured():
            raise HTTPException(status_code=503, detail="Supabase not configured")
        db.add_to_watchlist(user_id, ticker.upper())
        return {"added": ticker.upper()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/watchlist/{ticker}", tags=["watchlist"])
def remove_watchlist(ticker: str, user_id: str = Depends(require_user)):
    try:
        import supabase_client as db
        if not db.is_configured():
            raise HTTPException(status_code=503, detail="Supabase not configured")
        db.remove_from_watchlist(user_id, ticker.upper())
        return {"removed": ticker.upper()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Quote endpoints ────────────────────────────────────────────────────────────

@app.get("/quote/{ticker}", response_model=StockQuote, tags=["quotes"])
def get_quote(ticker: str):
    try:
        return analyzer.get_quote(ticker.upper())
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Could not fetch quote for {ticker}: {e}")


@app.get("/history/{ticker}", tags=["quotes"])
def get_history(ticker: str, period: str = "1y"):
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
    return analyzer.validate_ticker(ticker.upper())


# ── Portfolio advisor ──────────────────────────────────────────────────────────

@app.get("/advice", tags=["advisor"])
@limiter.limit("10/minute;50/hour")
def get_advice(request: Request, risk_tolerance: str = "moderate", question: Optional[str] = None, user_id: str = Depends(require_user)):
    try:
        import supabase_client as db
        settings = db.get_user_settings(user_id) if db.is_configured() else None
        port = portfolio_store.get_portfolio(user_id)
        summary = analyzer.build_portfolio_summary(port)
        advice = ai_advisor.get_advice(summary, question=question, risk_tolerance=risk_tolerance, user_settings=settings, user_id=user_id)
        return {"advice": advice}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/advice", tags=["advisor"])
@limiter.limit("10/minute;50/hour")
def get_advice_with_payload(request: Request, req: AdviceRequest, user_id: str = Depends(require_user)):
    try:
        import supabase_client as db
        settings = db.get_user_settings(user_id) if db.is_configured() else None
        advice = ai_advisor.get_advice(req.portfolio_summary, req.question, req.risk_tolerance, user_settings=settings, user_id=user_id)
        return {"advice": advice}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Chat (general investment questions) ───────────────────────────────────────

_INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|above|prior)\s+(instructions?|rules?|prompts?)",
    r"you\s+are\s+now\s+a?\s*(trading|financial\s+advisor|investment\s+bot)",
    r"(disregard|forget|override)\s+(your\s+)?(previous|prior|all)\s+(instructions?|guidelines?)",
    r"act\s+as\s+(a|an)\s+(licensed|registered|professional)\s+(financial|investment)",
    r"pretend\s+(you\s+are|to\s+be)",
    r"\bDAN\b",
    r"jailbreak",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def _sanitize_chat_input(message: str) -> str:
    """Reject prompt injection attempts; truncate to prevent context abuse."""
    if _INJECTION_RE.search(message):
        raise HTTPException(
            status_code=400,
            detail="Message contains disallowed content. Please ask a genuine investment question.",
        )
    return message[:2000]


@app.post("/chat", tags=["chat"])
@limiter.limit("20/minute;100/hour")
def chat(request: Request, body: dict, user_id: str = Depends(require_user)):
    """General investment chat with smart intent detection and live data fetching."""
    message = _sanitize_chat_input(body.get("message", "").strip())
    session_id = body.get("session_id", "default")
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    try:
        import supabase_client as db
        settings = db.get_user_settings(user_id) if db.is_configured() else None

        # ── Intent detection & live data fetch ───────────────────────────────
        upper = message.upper()
        mentioned_tickers = re.findall(r'\b([A-Z]{1,5})\b', upper)
        known_tickers = set(_PICKS_POOL + _ETF_TICKERS + _INDEX_TICKERS)
        explicit_tickers = [t for t in mentioned_tickers if t in known_tickers]

        etf_keywords = {"ETF", "INDEX", "FUND", "PASSIVE", "VANGUARD", "BLACKROCK"}
        market_keywords = {"MARKET", "OVERVIEW", "TODAY", "MACRO", "ECONOMY", "SECTOR"}
        longterm_keywords = {"LONG", "YEAR", "DECADE", "HOLD", "RETIREMENT", "GROWTH"}
        top_keywords = {"TOP", "BEST", "BUY", "INVEST", "PICK", "RECOMMEND"}

        fetch_tickers: list[str] = []
        if explicit_tickers:
            fetch_tickers = explicit_tickers[:5]
        elif etf_keywords & set(upper.split()):
            fetch_tickers = _ETF_TICKERS[:8]
        elif market_keywords & set(upper.split()):
            fetch_tickers = _INDEX_TICKERS
        elif longterm_keywords & set(upper.split()) or top_keywords & set(upper.split()):
            fetch_tickers = _PICKS_POOL[:15]

        # Build live data context block
        context_lines = ["=== LIVE MARKET DATA (fetched now from Yahoo Finance) ==="]
        for t in fetch_tickers:
            try:
                q = analyzer.get_quote(t)
                context_lines.append(
                    f"{t}: ${q.price:.2f} | 1d: {q.change_pct:+.2f}% | Vol: {q.volume:,}"
                    + (f" | Mkt Cap: ${q.market_cap/1e9:.1f}B" if q.market_cap else "")
                )
            except Exception:
                pass
        context_lines.append("=== END LIVE MARKET DATA ===\n")
        context_data = "\n".join(context_lines)

        response_text = ai_advisor.get_chat_response(message, context_data, settings, user_id)

        # Persist to chat history
        if db.is_configured():
            db.save_chat_message(user_id, session_id, "user", message)
            db.save_chat_message(user_id, session_id, "assistant", response_text, settings.get("preferred_model") if settings else "claude")

        return {"response": response_text, "tickers_fetched": fetch_tickers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/history", tags=["chat"])
def get_chat_history(session_id: str = "default", user_id: str = Depends(require_user)):
    try:
        import supabase_client as db
        if not db.is_configured():
            return []
        return db.get_chat_history(user_id, session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Agent Council ──────────────────────────────────────────────────────────────

@app.post("/council/{ticker}", tags=["council"])
@limiter.limit("5/minute;20/hour")
async def agent_council(request: Request, ticker: str, user_id: str = Depends(require_user)):
    """
    3-agent debate (Bull / Bear / Risk) in parallel via Haiku,
    then Sonnet moderator synthesizes the final verdict.
    """
    ticker = ticker.upper()
    validation = analyzer.validate_ticker(ticker)
    if not validation.valid:
        raise HTTPException(status_code=404, detail=validation.error or f"Invalid ticker: {ticker}")
    try:
        import supabase_client as db
        settings = db.get_user_settings(user_id) if db.is_configured() else None
        deep = analyzer.build_deep_analysis(ticker)
        result = await ai_advisor.get_agent_council(deep, settings, user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Deep analysis ──────────────────────────────────────────────────────────────

@app.get("/analyze/{ticker}", tags=["analysis"])
def analyze_stock(ticker: str, question: Optional[str] = None, user_id: str = Depends(require_user)):
    ticker = ticker.upper()
    validation = analyzer.validate_ticker(ticker)
    if not validation.valid:
        raise HTTPException(status_code=404, detail=validation.error or f"Invalid ticker: {ticker}")
    try:
        import supabase_client as db
        settings = db.get_user_settings(user_id) if db.is_configured() else None
        deep = analyzer.build_deep_analysis(ticker)
        deep.ai_analysis = ai_advisor.get_deep_analysis_advice(deep, question=question, user_settings=settings, user_id=user_id)
        return deep
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/technicals/{ticker}", response_model=TechnicalAnalysis, tags=["analysis"])
def get_technicals(ticker: str, period: str = "6mo"):
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
    ticker = ticker.upper()
    validation = analyzer.validate_ticker(ticker)
    if not validation.valid:
        raise HTTPException(status_code=404, detail=validation.error)
    try:
        from fundamentals import get_fundamentals as _gf
        return _gf(ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/fundamentals/{ticker}/score", response_model=FundamentalScore, tags=["analysis"])
def get_fundamental_score(ticker: str):
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
    ticker = ticker.upper()
    validation = analyzer.validate_ticker(ticker)
    if not validation.valid:
        raise HTTPException(status_code=404, detail=validation.error)
    try:
        from fundamentals import get_institutional_data as _get_inst
        return _get_inst(ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── News ───────────────────────────────────────────────────────────────────────

@app.get("/news/{ticker}", response_model=NewsBundle, tags=["news"])
def get_ticker_news(ticker: str, max_items: int = 10):
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
    try:
        from news_fetcher import get_market_news as _gmn
        return _gmn(max_items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/news/tagged", tags=["news"])
def get_tagged_news(max_items: int = 20):
    """Market news enriched with per-article ticker tags and sentiment scores."""
    from news_fetcher import get_market_news as _gmn, get_ticker_news as _gtn
    from models import TaggedNewsItem, TaggedNewsBundle
    import re as _re
    from validator import utcnow_iso

    _POSITIVE = {
        "beat", "beats", "upgrade", "upgraded", "growth", "strong", "record",
        "surge", "rally", "gains", "profit", "bullish", "buy", "outperform",
        "raised", "boost", "soar", "positive", "higher", "upside",
    }
    _NEGATIVE = {
        "miss", "misses", "downgrade", "downgraded", "loss", "weak", "layoff",
        "fraud", "investigation", "warning", "decline", "drop", "fall",
        "bearish", "sell", "underperform", "cut", "concern", "risk", "recall",
    }

    try:
        bundle = _gmn(max_items)
        tagged: list[TaggedNewsItem] = []
        overall_pos = overall_neg = 0

        for article in bundle.articles:
            words = set(article.title.lower().split())
            p = len(words & _POSITIVE)
            n = len(words & _NEGATIVE)
            score = p - n
            sentiment = "bullish" if score > 0 else ("bearish" if score < 0 else "neutral")
            overall_pos += (1 if score > 0 else 0)
            overall_neg += (1 if score < 0 else 0)

            # Tickers from yfinance related_tickers field (stored in NewsItem if present)
            tickers = getattr(article, "related_tickers", []) or []
            # Also scan title for known ticker patterns
            found = _re.findall(r'\b([A-Z]{1,5})\b', article.title)
            from screener import SCREENER_UNIVERSE
            tickers = list({t for t in (tickers + found) if t in SCREENER_UNIVERSE})[:5]

            tagged.append(TaggedNewsItem(
                title=article.title,
                url=article.url,
                publisher=article.publisher,
                published_at=article.published_at,
                tickers=tickers,
                sentiment=sentiment,
                sentiment_score=score,
            ))

        total = overall_pos + overall_neg + (len(tagged) - overall_pos - overall_neg)
        overall = "bullish" if overall_pos / max(total, 1) >= 0.5 else (
            "bearish" if overall_neg / max(total, 1) >= 0.5 else "neutral"
        )
        return TaggedNewsBundle(articles=tagged, fetched_at=utcnow_iso(), overall_sentiment=overall)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Screener ───────────────────────────────────────────────────────────────────

@app.get("/screener/best-day", tags=["screener"])
def best_of_day(top_n: int = 10, user_id: str = Depends(require_user)):
    try:
        import supabase_client as db
        settings = db.get_user_settings(user_id) if db.is_configured() else None
        from screener import screen_best_of_day
        result = screen_best_of_day(top_n=top_n)
        result.ai_narrative = ai_advisor.get_screener_advice(result, settings, user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/screener/long-term", tags=["screener"])
def long_term_picks(top_n: int = 10, min_score: float = 5.0, user_id: str = Depends(require_user)):
    try:
        import supabase_client as db
        settings = db.get_user_settings(user_id) if db.is_configured() else None
        from screener import screen_long_term
        result = screen_long_term(top_n=top_n, min_score=min_score)
        result.ai_narrative = ai_advisor.get_screener_advice(result, settings, user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/screener/correlated/{ticker}", response_model=CorrelationResult, tags=["screener"])
def correlated_stocks(ticker: str, top_n: int = 5):
    ticker = ticker.upper()
    validation = analyzer.validate_ticker(ticker)
    if not validation.valid:
        raise HTTPException(status_code=404, detail=validation.error)
    try:
        from screener import find_correlated_stocks
        return find_correlated_stocks(ticker, top_n=top_n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Signal Scanner ────────────────────────────────────────────────────────────

@app.get("/signals", tags=["signals"])
@limiter.limit("10/minute;30/hour")
def get_signals(request: Request, user_id: str = Depends(require_user)):
    """
    AI signal scan: synthesizes recent news + momentum screener into top-5 stock setups.
    Results cached for 5 minutes. Not price prediction — setup analysis only.
    """
    import cache as _cache
    from validator import utcnow_iso
    from models import SignalScanResult

    cache_key = "signals:latest"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        import supabase_client as db
        settings = db.get_user_settings(user_id) if db.is_configured() else None

        from news_fetcher import get_market_news as _gmn, format_news_for_prompt
        from screener import screen_best_of_day

        news_bundle = _gmn(max_items=20)
        news_text = format_news_for_prompt(news_bundle, max_items=18)

        screener_result = screen_best_of_day(top_n=20)
        picks = [p for p in screener_result.picks if hasattr(p, "momentum_1d")]

        result = ai_advisor.get_signal_scan(
            news_text=news_text,
            screener_picks=picks,
            user_settings=settings,
            user_id=user_id,
        )
        _cache.set(cache_key, result, 300)  # 5-minute cache
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Usage / spend tracking ────────────────────────────────────────────────────

@app.get("/usage", tags=["user"])
def get_usage(user_id: str = Depends(require_user)):
    import token_tracker
    return token_tracker.get_usage_summary(user_id)


# ── Cache management ───────────────────────────────────────────────────────────

def _require_admin(user_id: str = Depends(require_user)) -> str:
    admin_ids = set(filter(None, os.getenv("ADMIN_USER_IDS", "").split(",")))
    if admin_ids and user_id not in admin_ids:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_id


@app.get("/cache/stats", tags=["admin"])
def cache_stats(user_id: str = Depends(_require_admin)):
    return _cache.stats()


@app.post("/cache/clear", tags=["admin"])
def clear_cache(user_id: str = Depends(_require_admin)):
    _cache.clear()
    return {"message": "Cache cleared."}
