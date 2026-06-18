"""Fetch deep fundamental, analyst, and institutional data from yfinance."""

from typing import Optional
import yfinance as yf
import pandas as pd

import cache as _cache
from models import (
    FundamentalsData,
    FundamentalScore,
    AnalystData,
    InstitutionalData,
)
from validator import utcnow_iso


def _safe(val, cast=float) -> Optional[float]:
    try:
        if val is None or (isinstance(val, float) and (val != val)):
            return None
        return cast(val)
    except Exception:
        return None


def get_fundamentals(ticker: str) -> FundamentalsData:
    """
    Fetch comprehensive fundamental data from yfinance.info.
    Cached with FUNDAMENTALS_TTL.
    """
    ticker = ticker.upper().strip()
    cache_key = f"fundamentals:{ticker}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    now_iso = utcnow_iso()
    try:
        info = yf.Ticker(ticker).info
    except Exception:
        info = {}

    is_etf = info.get("quoteType", "").upper() in ("ETF", "MUTUALFUND", "INDEX")

    result = FundamentalsData(
        ticker=ticker,
        fetched_at=now_iso,
        name=info.get("longName") or info.get("shortName"),
        sector=info.get("sector"),
        industry=info.get("industry"),
        is_etf=is_etf,
        market_cap=_safe(info.get("marketCap")),
        pe_ratio=_safe(info.get("trailingPE")),
        forward_pe=_safe(info.get("forwardPE")),
        pb_ratio=_safe(info.get("priceToBook")),
        peg_ratio=_safe(info.get("pegRatio")),
        eps_trailing=_safe(info.get("trailingEps")),
        eps_forward=_safe(info.get("forwardEps")),
        revenue_growth=_safe(info.get("revenueGrowth")),
        earnings_growth=_safe(info.get("earningsGrowth")),
        roe=_safe(info.get("returnOnEquity")),
        roa=_safe(info.get("returnOnAssets")),
        debt_to_equity=_safe(info.get("debtToEquity")),
        current_ratio=_safe(info.get("currentRatio")),
        free_cashflow=_safe(info.get("freeCashflow")),
        profit_margin=_safe(info.get("profitMargins")),
        gross_margin=_safe(info.get("grossMargins")),
        operating_margin=_safe(info.get("operatingMargins")),
        total_revenue=_safe(info.get("totalRevenue")),
        net_income=_safe(info.get("netIncomeToCommon")),
        dividend_yield=_safe(info.get("dividendYield")),
        payout_ratio=_safe(info.get("payoutRatio")),
        beta=_safe(info.get("beta")),
        target_mean_price=_safe(info.get("targetMeanPrice")),
        recommendation=info.get("recommendationKey"),
        analyst_count=_safe(info.get("numberOfAnalystOpinions"), cast=int),
    )
    _cache.set(cache_key, result, _cache.FUNDAMENTALS_TTL)
    return result


def compute_fundamental_score(f: FundamentalsData) -> FundamentalScore:
    """
    Rule-based fundamental quality score (0–10).
    Uses only data already in the FundamentalsData object.
    """
    score = 0.0
    reasoning: list[str] = []

    if f.is_etf:
        reasoning.append("ETF — fundamental scoring not applicable")
        return FundamentalScore(
            ticker=f.ticker,
            name=f.name,
            sector=f.sector,
            score=0.0,
            fetched_at=f.fetched_at,
            reasoning=reasoning,
        )

    # ROE (max 2.0)
    if f.roe is not None:
        if f.roe >= 0.20:
            score += 2.0
            reasoning.append(f"ROE {f.roe*100:.1f}% — excellent (≥20%)")
        elif f.roe >= 0.15:
            score += 1.5
            reasoning.append(f"ROE {f.roe*100:.1f}% — good (≥15%)")
        elif f.roe >= 0.10:
            score += 1.0
            reasoning.append(f"ROE {f.roe*100:.1f}% — fair (≥10%)")
        else:
            reasoning.append(f"ROE {f.roe*100:.1f}% — weak (<10%)")
    else:
        reasoning.append("ROE — data unavailable")

    # Revenue growth (max 2.0)
    if f.revenue_growth is not None:
        if f.revenue_growth >= 0.20:
            score += 2.0
            reasoning.append(f"Revenue growth {f.revenue_growth*100:.1f}% — strong (≥20%)")
        elif f.revenue_growth >= 0.10:
            score += 1.5
            reasoning.append(f"Revenue growth {f.revenue_growth*100:.1f}% — good (≥10%)")
        elif f.revenue_growth >= 0.05:
            score += 0.75
            reasoning.append(f"Revenue growth {f.revenue_growth*100:.1f}% — moderate (≥5%)")
        elif f.revenue_growth >= 0:
            score += 0.25
            reasoning.append(f"Revenue growth {f.revenue_growth*100:.1f}% — low but positive")
        else:
            reasoning.append(f"Revenue growth {f.revenue_growth*100:.1f}% — declining")
    else:
        reasoning.append("Revenue growth — data unavailable")

    # Profit margin (max 1.5)
    if f.profit_margin is not None:
        if f.profit_margin >= 0.20:
            score += 1.5
            reasoning.append(f"Profit margin {f.profit_margin*100:.1f}% — strong (≥20%)")
        elif f.profit_margin >= 0.10:
            score += 1.0
            reasoning.append(f"Profit margin {f.profit_margin*100:.1f}% — good (≥10%)")
        elif f.profit_margin >= 0.05:
            score += 0.5
            reasoning.append(f"Profit margin {f.profit_margin*100:.1f}% — fair (≥5%)")
        else:
            reasoning.append(f"Profit margin {f.profit_margin*100:.1f}% — thin (<5%)")
    else:
        reasoning.append("Profit margin — data unavailable")

    # Debt/Equity (max 1.5, lower is better)
    # yfinance debtToEquity is percentage-scaled (e.g. 150 = 1.5x D/E), always divide by 100.
    if f.debt_to_equity is not None:
        de = f.debt_to_equity / 100
        if de <= 0.3:
            score += 1.5
            reasoning.append(f"D/E {de:.2f} — very low leverage")
        elif de <= 0.7:
            score += 1.2
            reasoning.append(f"D/E {de:.2f} — low leverage")
        elif de <= 1.2:
            score += 0.8
            reasoning.append(f"D/E {de:.2f} — moderate leverage")
        elif de <= 2.0:
            score += 0.3
            reasoning.append(f"D/E {de:.2f} — elevated leverage")
        else:
            reasoning.append(f"D/E {de:.2f} — high leverage")
    else:
        reasoning.append("Debt/Equity — data unavailable")

    # Free cash flow (max 1.5)
    if f.free_cashflow is not None:
        if f.free_cashflow > 0:
            score += 1.5
            reasoning.append(f"Positive FCF: ${f.free_cashflow/1e9:.1f}B")
        else:
            reasoning.append(f"Negative FCF: ${f.free_cashflow/1e9:.1f}B")
    else:
        reasoning.append("Free cash flow — data unavailable")

    # PEG ratio (max 1.0)
    if f.peg_ratio is not None and f.peg_ratio > 0:
        if f.peg_ratio <= 1.0:
            score += 1.0
            reasoning.append(f"PEG {f.peg_ratio:.2f} — undervalued by growth")
        elif f.peg_ratio <= 2.0:
            score += 0.6
            reasoning.append(f"PEG {f.peg_ratio:.2f} — fair value")
        elif f.peg_ratio <= 3.0:
            score += 0.2
            reasoning.append(f"PEG {f.peg_ratio:.2f} — slightly rich")
        else:
            reasoning.append(f"PEG {f.peg_ratio:.2f} — expensive by growth")
    else:
        reasoning.append("PEG ratio — data unavailable")

    # Analyst consensus (max 0.5)
    rec = (f.recommendation or "").lower()
    if "strong_buy" in rec or "strongbuy" in rec:
        score += 0.5
        reasoning.append("Analyst consensus: Strong Buy")
    elif rec in ("buy",):
        score += 0.3
        reasoning.append("Analyst consensus: Buy")
    elif rec in ("hold", "neutral"):
        reasoning.append("Analyst consensus: Hold/Neutral")
    elif rec in ("sell", "underperform", "strong_sell"):
        reasoning.append(f"Analyst consensus: {rec.replace('_', ' ').title()}")

    return FundamentalScore(
        ticker=f.ticker,
        name=f.name,
        sector=f.sector,
        score=round(min(score, 10.0), 2),
        fetched_at=f.fetched_at,
        reasoning=reasoning,
        pe_ratio=f.pe_ratio,
        roe=f.roe,
        revenue_growth=f.revenue_growth,
        debt_to_equity=f.debt_to_equity,
        free_cashflow=f.free_cashflow,
        profit_margin=f.profit_margin,
        peg_ratio=f.peg_ratio,
    )


def get_analyst_data(ticker: str) -> AnalystData:
    """
    Fetch analyst recommendations and earnings calendar from yfinance.
    Cached with ANALYST_TTL.
    """
    ticker = ticker.upper().strip()
    cache_key = f"analyst:{ticker}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    now_iso = utcnow_iso()
    buy_c = hold_c = sell_c = sbuy_c = ssell_c = 0
    recent_recs: list[dict] = []
    earnings_date: Optional[str] = None
    eps_est: Optional[float] = None
    rev_est: Optional[float] = None
    consensus: Optional[str] = None

    try:
        t = yf.Ticker(ticker)

        # Recommendations — newer yfinance returns a period-based summary
        recs = t.recommendations
        if recs is not None and not recs.empty:
            # Format 1: period summary {strongBuy, buy, hold, sell, strongSell}
            if "strongBuy" in recs.columns:
                last = recs.iloc[-1]
                sbuy_c = int(last.get("strongBuy", 0) or 0)
                buy_c = int(last.get("buy", 0) or 0)
                hold_c = int(last.get("hold", 0) or 0)
                sell_c = int(last.get("sell", 0) or 0)
                ssell_c = int(last.get("strongSell", 0) or 0)
                total = sbuy_c + buy_c + hold_c + sell_c + ssell_c
                if total > 0:
                    bull = sbuy_c + buy_c
                    if bull / total >= 0.6:
                        consensus = "Buy"
                    elif (sell_c + ssell_c) / total >= 0.4:
                        consensus = "Sell"
                    else:
                        consensus = "Hold"
            # Format 2: historical rows {Firm, To Grade, From Grade, Action}
            elif "To Grade" in recs.columns:
                recent = recs.sort_index(ascending=False).head(5)
                for idx, row in recent.iterrows():
                    recent_recs.append({
                        "date": str(idx)[:10],
                        "firm": str(row.get("Firm", "")),
                        "to_grade": str(row.get("To Grade", "")),
                        "from_grade": str(row.get("From Grade", "")),
                        "action": str(row.get("Action", "")),
                    })

        # Calendar
        cal = t.calendar
        if cal is not None:
            if isinstance(cal, dict):
                ed = cal.get("Earnings Date")
                if ed:
                    earnings_date = str(ed[0])[:10] if hasattr(ed, "__iter__") else str(ed)[:10]
                eps_est = _safe(cal.get("EPS Estimate"))
                rev_est = _safe(cal.get("Revenue Estimate"))
            elif isinstance(cal, pd.DataFrame) and not cal.empty:
                if "Earnings Date" in cal.index:
                    earnings_date = str(cal.loc["Earnings Date"].iloc[0])[:10]
    except Exception:
        pass

    result = AnalystData(
        ticker=ticker,
        fetched_at=now_iso,
        earnings_date=earnings_date,
        eps_estimate=eps_est,
        revenue_estimate=rev_est,
        recent_recommendations=recent_recs,
        buy_count=buy_c,
        hold_count=hold_c,
        sell_count=sell_c,
        strong_buy_count=sbuy_c,
        strong_sell_count=ssell_c,
        consensus=consensus,
    )
    _cache.set(cache_key, result, _cache.ANALYST_TTL)
    return result


def get_institutional_data(ticker: str) -> InstitutionalData:
    """
    Fetch institutional holders and insider ownership from yfinance.
    Cached with INSTITUTIONAL_TTL.
    """
    ticker = ticker.upper().strip()
    cache_key = f"institutional:{ticker}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    now_iso = utcnow_iso()
    pct_insiders: Optional[float] = None
    pct_institutions: Optional[float] = None
    top_holders: list[dict] = []

    try:
        t = yf.Ticker(ticker)

        # Major holders
        mh = t.major_holders
        if mh is not None and not mh.empty:
            for _, row in mh.iterrows():
                val_str = str(row.iloc[0]).replace("%", "").strip()
                label = str(row.iloc[1]).lower() if len(row) > 1 else ""
                try:
                    val = float(val_str) / 100
                    if "insider" in label:
                        pct_insiders = round(val, 4)
                    elif "institution" in label:
                        pct_institutions = round(val, 4)
                except ValueError:
                    pass

        # Institutional holders
        ih = t.institutional_holders
        if ih is not None and not ih.empty:
            ih = ih.head(10)
            for _, row in ih.iterrows():
                holder_name = str(row.get("Holder", row.iloc[0] if len(row) > 0 else "Unknown"))
                shares_val = row.get("Shares", row.iloc[1] if len(row) > 1 else None)
                value_val = row.get("Value", row.iloc[3] if len(row) > 3 else None)
                pct_val = row.get("% Out", row.iloc[2] if len(row) > 2 else None)
                top_holders.append({
                    "holder": holder_name,
                    "shares": int(float(shares_val)) if shares_val is not None else None,
                    "pct_held": round(float(pct_val), 4) if pct_val is not None else None,
                    "value": int(float(value_val)) if value_val is not None else None,
                })
    except Exception:
        pass

    result = InstitutionalData(
        ticker=ticker,
        fetched_at=now_iso,
        pct_insiders=pct_insiders,
        pct_institutions=pct_institutions,
        top_holders=top_holders,
    )
    _cache.set(cache_key, result, _cache.INSTITUTIONAL_TTL)
    return result
