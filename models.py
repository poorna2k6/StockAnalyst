from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date


# ── Existing models (unchanged) ───────────────────────────────────────────────

class StockPosition(BaseModel):
    ticker: str
    shares: float
    avg_cost: float
    added_at: datetime = Field(default_factory=datetime.utcnow)


class Portfolio(BaseModel):
    name: str = "My Portfolio"
    positions: dict[str, StockPosition] = {}
    cash: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StockQuote(BaseModel):
    ticker: str
    price: float
    change: float
    change_pct: float
    volume: int
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None
    name: Optional[str] = None


class PositionSummary(BaseModel):
    ticker: str
    shares: float
    avg_cost: float
    current_price: float
    current_value: float
    cost_basis: float
    gain_loss: float
    gain_loss_pct: float
    weight: float


class PortfolioSummary(BaseModel):
    name: str
    total_value: float
    total_cost: float
    total_gain_loss: float
    total_gain_loss_pct: float
    cash: float
    positions: list[PositionSummary]


class AddPositionRequest(BaseModel):
    ticker: str
    shares: float = Field(gt=0)
    avg_cost: float = Field(gt=0)


class RemovePositionRequest(BaseModel):
    ticker: str


class AdviceRequest(BaseModel):
    portfolio_summary: PortfolioSummary
    question: Optional[str] = None
    risk_tolerance: str = "moderate"


# ── Validation ────────────────────────────────────────────────────────────────

class TickerValidation(BaseModel):
    ticker: str
    valid: bool
    name: Optional[str] = None
    error: Optional[str] = None
    fetched_at: Optional[str] = None


# ── Technical Analysis ────────────────────────────────────────────────────────

class TechnicalAnalysis(BaseModel):
    ticker: str
    period: str
    fetched_at: str
    data_source: str = "yfinance"
    current_price: Optional[float] = None

    # Moving averages
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None

    # RSI
    rsi_14: Optional[float] = None

    # MACD
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None

    # Bollinger Bands
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_pct_b: Optional[float] = None   # 0=at lower band, 1=at upper band

    # Volume
    volume_sma_20: Optional[float] = None
    volume_ratio: Optional[float] = None   # current / 20d avg

    # Price momentum (% change)
    momentum_1d: Optional[float] = None
    momentum_5d: Optional[float] = None
    momentum_1mo: Optional[float] = None
    momentum_3mo: Optional[float] = None

    # Derived signals
    signals: list[str] = []
    trend: str = "neutral"   # "bullish" | "bearish" | "neutral"


# ── Fundamentals ──────────────────────────────────────────────────────────────

class FundamentalsData(BaseModel):
    ticker: str
    fetched_at: str
    data_source: str = "yfinance"

    name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    is_etf: bool = False

    # Valuation
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    pb_ratio: Optional[float] = None
    peg_ratio: Optional[float] = None
    eps_trailing: Optional[float] = None
    eps_forward: Optional[float] = None

    # Growth
    revenue_growth: Optional[float] = None
    earnings_growth: Optional[float] = None

    # Quality
    roe: Optional[float] = None
    roa: Optional[float] = None
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    free_cashflow: Optional[float] = None
    profit_margin: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None

    # Income
    total_revenue: Optional[float] = None
    net_income: Optional[float] = None

    # Dividends & risk
    dividend_yield: Optional[float] = None
    payout_ratio: Optional[float] = None
    beta: Optional[float] = None

    # Analyst
    target_mean_price: Optional[float] = None
    recommendation: Optional[str] = None
    analyst_count: Optional[int] = None


class FundamentalScore(BaseModel):
    ticker: str
    name: Optional[str] = None
    sector: Optional[str] = None
    score: float           # 0.0 – 10.0
    fetched_at: str
    reasoning: list[str] = []

    # Key raw data for transparency
    pe_ratio: Optional[float] = None
    roe: Optional[float] = None
    revenue_growth: Optional[float] = None
    debt_to_equity: Optional[float] = None
    free_cashflow: Optional[float] = None
    profit_margin: Optional[float] = None
    peg_ratio: Optional[float] = None


class AnalystData(BaseModel):
    ticker: str
    fetched_at: str
    data_source: str = "yfinance"
    earnings_date: Optional[str] = None
    eps_estimate: Optional[float] = None
    revenue_estimate: Optional[float] = None
    recent_recommendations: list[dict] = []   # {date, firm, to_grade, action}
    buy_count: int = 0
    hold_count: int = 0
    sell_count: int = 0
    strong_buy_count: int = 0
    strong_sell_count: int = 0
    consensus: Optional[str] = None


class InstitutionalData(BaseModel):
    ticker: str
    fetched_at: str
    data_source: str = "yfinance"
    pct_insiders: Optional[float] = None
    pct_institutions: Optional[float] = None
    top_holders: list[dict] = []   # {holder, shares, pct_held, value}


# ── News ──────────────────────────────────────────────────────────────────────

class NewsItem(BaseModel):
    title: str
    url: str
    publisher: str
    published_at: Optional[str] = None
    related_tickers: list[str] = []


class NewsSentiment(BaseModel):
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    overall: str = "neutral"   # "bullish" | "bearish" | "neutral"


class NewsBundle(BaseModel):
    ticker: Optional[str] = None
    fetched_at: str
    data_source: str = "yfinance"
    articles: list[NewsItem] = []
    sentiment: Optional[NewsSentiment] = None


# ── Screener ──────────────────────────────────────────────────────────────────

class DayPick(BaseModel):
    ticker: str
    name: Optional[str] = None
    price: Optional[float] = None
    change_pct: Optional[float] = None
    volume_ratio: Optional[float] = None
    momentum_1d: Optional[float] = None
    momentum_5d: Optional[float] = None
    rsi_14: Optional[float] = None
    news_count: int = 0
    composite_score: float = 0.0
    reasoning: list[str] = []
    fetched_at: str = ""


class LongTermPick(BaseModel):
    ticker: str
    name: Optional[str] = None
    sector: Optional[str] = None
    composite_score: float = 0.0
    reasoning: list[str] = []
    pe_ratio: Optional[float] = None
    roe: Optional[float] = None
    revenue_growth: Optional[float] = None
    debt_to_equity: Optional[float] = None
    free_cashflow: Optional[float] = None
    profit_margin: Optional[float] = None
    fetched_at: str = ""


class CorrelatedStock(BaseModel):
    ticker: str
    name: Optional[str] = None
    correlation: float
    sector: Optional[str] = None


class CorrelationResult(BaseModel):
    ticker: str
    fetched_at: str
    data_source: str = "yfinance"
    period: str
    correlated_stocks: list[CorrelatedStock] = []


class ScreenerResult(BaseModel):
    screener_type: str   # "best_of_day" | "long_term"
    fetched_at: str
    universe_size: int
    picks: list[DayPick] | list[LongTermPick] = []
    ai_narrative: Optional[str] = None


# ── Deep Analysis (aggregates all) ───────────────────────────────────────────

class DeepStockAnalysis(BaseModel):
    ticker: str
    name: Optional[str] = None
    fetched_at: str
    data_sources: list[str] = ["yfinance"]

    quote: Optional[StockQuote] = None
    technicals: Optional[TechnicalAnalysis] = None
    fundamentals: Optional[FundamentalsData] = None
    fundamental_score: Optional[FundamentalScore] = None
    analyst_data: Optional[AnalystData] = None
    institutional_data: Optional[InstitutionalData] = None
    news: Optional[NewsBundle] = None
    ai_analysis: Optional[str] = None
