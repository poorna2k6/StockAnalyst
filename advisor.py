"""AI-powered advisor using Claude — all responses grounded in fetched data."""

import os
import anthropic

from models import PortfolioSummary, DeepStockAnalysis, ScreenerResult, DayPick, LongTermPick
from news_fetcher import format_news_for_prompt

# ── Shared system prompt ──────────────────────────────────────────────────────

_GROUNDED_SYSTEM = (
    "You are a rigorous financial analyst assistant. "
    "You will be given a DATA BLOCK containing real-time market data fetched from Yahoo Finance. "
    "\n\nSTRICT RULES — read carefully before responding:\n"
    "1. Base ALL your analysis EXCLUSIVELY on data in the DATA BLOCK. "
    "Do NOT use statistics, prices, or facts from your training data.\n"
    "2. If a field shows 'N/A' or is missing, state 'data unavailable' — never estimate or fill gaps.\n"
    "3. Cite the section name in brackets when referencing a data point, e.g. [Technicals] RSI 58.4.\n"
    "4. Do not provide specific price targets beyond what analyst data already shows.\n"
    "5. End every response with: 'Data fetched: {fetched_at}. This is educational analysis, not financial advice.'\n"
)


def _get_client() -> anthropic.Anthropic | None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


def _no_key_msg() -> str:
    return "ANTHROPIC_API_KEY not set. Set it in your .env file to receive AI-powered analysis."


# ── Portfolio context builder ─────────────────────────────────────────────────

def _build_portfolio_context(summary: PortfolioSummary) -> str:
    lines = [
        f"Portfolio: {summary.name}",
        f"Total Value: ${summary.total_value:,.2f}",
        f"Total Cost Basis: ${summary.total_cost:,.2f}",
        f"Total Gain/Loss: ${summary.total_gain_loss:,.2f} ({summary.total_gain_loss_pct:.2f}%)",
        f"Cash: ${summary.cash:,.2f}",
        "",
        "Holdings:",
    ]
    for pos in summary.positions:
        sign = "+" if pos.gain_loss >= 0 else ""
        lines.append(
            f"  {pos.ticker}: {pos.shares:.2f} shares @ ${pos.avg_cost:.2f} avg cost"
            f" | Current: ${pos.current_price:.2f}"
            f" | Value: ${pos.current_value:,.2f}"
            f" | P&L: {sign}${pos.gain_loss:,.2f} ({sign}{pos.gain_loss_pct:.2f}%)"
            f" | Weight: {pos.weight:.1f}%"
        )
    return "\n".join(lines)


# ── Original get_advice (backward compatible, upgraded tokens + grounding) ────

def get_advice(
    summary: PortfolioSummary,
    question: str | None = None,
    risk_tolerance: str = "moderate",
) -> str:
    client = _get_client()
    if client is None:
        return _no_key_msg()

    portfolio_context = _build_portfolio_context(summary)
    risk_desc = {
        "conservative": "prefers capital preservation, low volatility, dividend-paying stocks and bonds",
        "moderate": "seeks balanced growth with manageable risk, mix of growth and value stocks",
        "aggressive": "seeks maximum growth, comfortable with high volatility and concentrated positions",
    }.get(risk_tolerance, "seeks balanced growth with manageable risk")

    system_prompt = (
        "You are an experienced financial analyst and portfolio advisor. "
        "Analyze the portfolio data provided. Be specific about tickers and numbers. "
        "Only reference the portfolio data given — do not add external market opinions from training data. "
        "Always note that this is educational analysis, not official financial advice. "
        "Keep responses structured and actionable."
    )

    user_message = (
        f"Risk tolerance: {risk_tolerance} ({risk_desc}).\n\n"
        f"=== PORTFOLIO DATA (fetched live) ===\n{portfolio_context}\n\n"
    )
    if question:
        user_message += f"Question: {question}"
    else:
        user_message += (
            "Please analyze this portfolio and provide:\n"
            "1. Overall assessment (diversification, concentration risk)\n"
            "2. Top performing and underperforming positions\n"
            "3. Key risks to be aware of\n"
            "4. Actionable recommendations (trim, hold, or consider adding)\n"
            "5. Rebalancing suggestions if needed"
        )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": user_message}],
        system=system_prompt,
    )
    return message.content[0].text


# ── Deep stock analysis ───────────────────────────────────────────────────────

def _build_deep_data_block(analysis: DeepStockAnalysis) -> str:
    """Serialize DeepStockAnalysis into a structured text block for Claude."""
    lines = [
        f"=== DATA BLOCK FOR {analysis.ticker} ===",
        f"Company: {analysis.name or 'N/A'}",
        f"Data fetched: {analysis.fetched_at}",
        "",
    ]

    # Quote
    if analysis.quote:
        q = analysis.quote
        lines += [
            "[QUOTE]",
            f"Price: ${q.price:.2f} | Change: {q.change:+.2f} ({q.change_pct:+.2f}%)",
            f"Volume: {q.volume:,}",
            f"52-Week: ${q.week_52_low or 'N/A'} — ${q.week_52_high or 'N/A'}",
            f"Market Cap: ${(q.market_cap/1e9):.1f}B" if q.market_cap else "Market Cap: N/A",
            "",
        ]

    # Technicals
    if analysis.technicals:
        t = analysis.technicals
        lines += [
            "[TECHNICALS — computed from yfinance OHLCV history]",
            f"RSI(14): {t.rsi_14 or 'N/A'} | Trend: {t.trend.upper()}",
            f"MACD Line: {t.macd_line or 'N/A'} | Signal: {t.macd_signal or 'N/A'} | Histogram: {t.macd_histogram or 'N/A'}",
            f"SMA20: {t.sma_20 or 'N/A'} | SMA50: {t.sma_50 or 'N/A'} | SMA200: {t.sma_200 or 'N/A'}",
            f"Bollinger: Upper {t.bb_upper or 'N/A'} / Middle {t.bb_middle or 'N/A'} / Lower {t.bb_lower or 'N/A'} | %B: {t.bb_pct_b or 'N/A'}",
            f"Volume vs 20d avg: {t.volume_ratio or 'N/A'}x",
            f"Momentum: 1d={t.momentum_1d or 'N/A'}% | 5d={t.momentum_5d or 'N/A'}% | 1mo={t.momentum_1mo or 'N/A'}%",
            f"Signals: {'; '.join(t.signals) if t.signals else 'None'}",
            "",
        ]

    # Fundamentals
    if analysis.fundamentals:
        f = analysis.fundamentals
        lines += [
            "[FUNDAMENTALS — from Yahoo Finance .info]",
            f"Sector: {f.sector or 'N/A'} | Industry: {f.industry or 'N/A'}",
            f"P/E (trailing): {f.pe_ratio or 'N/A'} | P/E (forward): {f.forward_pe or 'N/A'}",
            f"P/B: {f.pb_ratio or 'N/A'} | PEG: {f.peg_ratio or 'N/A'}",
            f"EPS (trailing): {f.eps_trailing or 'N/A'} | EPS (forward): {f.eps_forward or 'N/A'}",
            f"ROE: {(f.roe*100):.1f}%" if f.roe is not None else "ROE: N/A",
            f"ROA: {(f.roa*100):.1f}%" if f.roa is not None else "ROA: N/A",
            f"Debt/Equity: {f.debt_to_equity or 'N/A'}",
            f"Revenue Growth (YoY): {(f.revenue_growth*100):.1f}%" if f.revenue_growth is not None else "Revenue Growth: N/A",
            f"Earnings Growth: {(f.earnings_growth*100):.1f}%" if f.earnings_growth is not None else "Earnings Growth: N/A",
            f"Profit Margin: {(f.profit_margin*100):.1f}%" if f.profit_margin is not None else "Profit Margin: N/A",
            f"Free Cash Flow: ${f.free_cashflow/1e9:.1f}B" if f.free_cashflow is not None else "Free Cash Flow: N/A",
            f"Dividend Yield: {(f.dividend_yield*100):.2f}%" if f.dividend_yield else "Dividend Yield: N/A",
            f"Beta: {f.beta or 'N/A'}",
            f"Analyst Target (mean): ${f.target_mean_price or 'N/A'} | Recommendation: {f.recommendation or 'N/A'}",
            "",
        ]

    # Fundamental score
    if analysis.fundamental_score:
        fs = analysis.fundamental_score
        lines += [
            "[FUNDAMENTAL SCORE — rule-based, not AI-generated]",
            f"Score: {fs.score}/10",
            f"Reasoning: {'; '.join(fs.reasoning)}",
            "",
        ]

    # Analyst data
    if analysis.analyst_data:
        ad = analysis.analyst_data
        lines += [
            "[ANALYST DATA — from Yahoo Finance .recommendations]",
            f"Consensus: {ad.consensus or 'N/A'} | Strong Buy: {ad.strong_buy_count} | Buy: {ad.buy_count} | Hold: {ad.hold_count} | Sell: {ad.sell_count}",
            f"Next Earnings Date: {ad.earnings_date or 'N/A'} | EPS Estimate: {ad.eps_estimate or 'N/A'}",
        ]
        if ad.recent_recommendations:
            lines.append("Recent Analyst Actions:")
            for rec in ad.recent_recommendations[:5]:
                lines.append(f"  {rec.get('date','')} | {rec.get('firm','')} | {rec.get('to_grade','')} | {rec.get('action','')}")
        lines.append("")

    # Institutional
    if analysis.institutional_data:
        inst = analysis.institutional_data
        lines += [
            "[INSTITUTIONAL — from Yahoo Finance .institutional_holders]",
            f"% Held by Insiders: {(inst.pct_insiders*100):.1f}%" if inst.pct_insiders is not None else "% Insiders: N/A",
            f"% Held by Institutions: {(inst.pct_institutions*100):.1f}%" if inst.pct_institutions is not None else "% Institutions: N/A",
        ]
        if inst.top_holders:
            lines.append("Top Institutional Holders:")
            for h in inst.top_holders[:5]:
                pct = f"{h.get('pct_held',0)*100:.2f}%" if h.get('pct_held') is not None else "N/A"
                lines.append(f"  {h.get('holder','?')} — {pct}")
        lines.append("")

    # News
    if analysis.news and analysis.news.articles:
        lines += [
            "[RECENT NEWS — from Yahoo Finance .news (last 7 days)]",
            format_news_for_prompt(analysis.news),
            "",
        ]

    lines.append("=== END DATA BLOCK ===")
    return "\n".join(lines)


def get_deep_analysis_advice(analysis: DeepStockAnalysis, question: str | None = None) -> str:
    """
    Generate a comprehensive stock analysis grounded in pre-fetched data.
    Claude is only allowed to reference data in the DATA BLOCK.
    """
    client = _get_client()
    if client is None:
        return _no_key_msg()

    data_block = _build_deep_data_block(analysis)
    system = _GROUNDED_SYSTEM.replace("{fetched_at}", analysis.fetched_at)

    if question:
        task = f"Answer this specific question about {analysis.ticker}: {question}"
    else:
        task = (
            f"Based solely on the DATA BLOCK above, provide a comprehensive analysis of {analysis.ticker}:\n"
            "1. **Technical Picture** — current trend, key momentum signals, support/resistance context\n"
            "2. **Fundamental Assessment** — valuation (P/E, PEG), quality (ROE, margins, FCF), growth\n"
            "3. **Analyst & Institutional Sentiment** — consensus, major holder changes\n"
            "4. **News-Driven Catalysts or Risks** — cite specific headlines from the data\n"
            "5. **Bull Case vs Bear Case** — supported by data points only\n"
            "6. **Verdict** — short-term trade / long-term hold / avoid — with explicit data rationale\n"
        )

    user_message = f"{data_block}\n\n{task}"
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": user_message}],
        system=system,
    )
    return message.content[0].text


# ── Screener narrative ────────────────────────────────────────────────────────

def get_screener_advice(result: ScreenerResult) -> str:
    """
    Claude explains WHY the screener's top picks ranked highly.
    Claude does not pick stocks — it synthesizes the scoring data.
    """
    client = _get_client()
    if client is None:
        return _no_key_msg()

    mode = result.screener_type
    picks = result.picks

    if not picks:
        return "No picks found in screener results."

    lines = [
        f"=== SCREENER DATA BLOCK ({mode.upper()}) ===",
        f"Screener type: {mode}",
        f"Universe evaluated: {result.universe_size} tickers",
        f"Fetched at: {result.fetched_at}",
        f"Top {len(picks)} picks ranked by algorithm:",
        "",
    ]

    for i, pick in enumerate(picks, 1):
        if isinstance(pick, DayPick):
            lines.append(f"{i}. {pick.ticker} — Score: {pick.composite_score:.2f}/10")
            lines.append(f"   Price: ${pick.price or 'N/A'} | 1d: {pick.momentum_1d or 'N/A'}% | 5d: {pick.momentum_5d or 'N/A'}%")
            lines.append(f"   Volume ratio: {pick.volume_ratio or 'N/A'}x | RSI: {pick.rsi_14 or 'N/A'} | News: {pick.news_count} articles")
            lines.append(f"   Score reasoning: {'; '.join(pick.reasoning)}")
        elif isinstance(pick, LongTermPick):
            lines.append(f"{i}. {pick.ticker} ({pick.sector or 'Unknown sector'}) — Score: {pick.composite_score:.2f}/10")
            lines.append(f"   ROE: {(pick.roe*100):.1f}%" if pick.roe else "   ROE: N/A")
            lines.append(f"   Revenue Growth: {(pick.revenue_growth*100):.1f}%" if pick.revenue_growth else "   Revenue Growth: N/A")
            lines.append(f"   D/E: {pick.debt_to_equity or 'N/A'} | Profit Margin: {(pick.profit_margin*100):.1f}%" if pick.profit_margin else f"   D/E: {pick.debt_to_equity or 'N/A'} | Profit Margin: N/A")
            lines.append(f"   Score reasoning: {'; '.join(pick.reasoning)}")
        lines.append("")

    lines.append("=== END SCREENER DATA BLOCK ===")
    data_block = "\n".join(lines)

    system = _GROUNDED_SYSTEM.replace("{fetched_at}", result.fetched_at)
    if mode == "best_of_day":
        task = (
            "Based solely on the SCREENER DATA BLOCK above, explain why these stocks scored highest today. "
            "For each pick, describe the specific momentum signals and volume patterns that drove its ranking. "
            "Note any risks visible in the data. Do not fabricate information not in the data block. "
            "Keep the narrative concise and actionable."
        )
    else:
        task = (
            "Based solely on the SCREENER DATA BLOCK above, explain why these stocks scored highest for long-term quality. "
            "For each pick, highlight the specific fundamental strengths (ROE, growth, FCF, debt) that drove its score. "
            "Note any weaknesses visible in the data. Do not fabricate information not in the data block."
        )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": f"{data_block}\n\n{task}"}],
        system=system,
    )
    return message.content[0].text
