from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class StockPosition(BaseModel):
    ticker: str
    shares: float
    avg_cost: float  # average cost per share
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
    weight: float  # portfolio weight %


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
    risk_tolerance: str = "moderate"  # conservative, moderate, aggressive
