"""AI advisor — Claude and Gemini, grounded in fetched data, with token tracking."""

import asyncio
import os
from typing import Optional

import anthropic

import json

from models import PortfolioSummary, DeepStockAnalysis, ScreenerResult, DayPick, LongTermPick, StockSignal, SignalScanResult
from news_fetcher import format_news_for_prompt

# ── Shared grounding system prompt ────────────────────────────────────────────

_GROUNDED_SYSTEM = (
    "You are a rigorous financial analyst assistant. "
    "You will be given a DATA BLOCK containing real-time market data fetched from Yahoo Finance. "
    "\n\nSTRICT RULES:\n"
    "1. Base ALL analysis EXCLUSIVELY on data in the DATA BLOCK. "
    "Do NOT use prices, statistics, or facts from your training data.\n"
    "2. If a field shows 'N/A' or is missing, say 'data unavailable' — never estimate.\n"
    "3. Cite the section name in brackets when referencing a data point, e.g. [Technicals] RSI 58.4.\n"
    "4. Do not provide price targets beyond what analyst data shows.\n"
    "5. End every response with: 'Data fetched: {fetched_at}. Educational analysis, not financial advice.'\n"
)

# ── Agent Council personas ────────────────────────────────────────────────────

_BULL_SYSTEM = (
    "You are an optimistic equity analyst making the STRONGEST POSSIBLE BULL CASE. "
    "Focus on: positive momentum, revenue/earnings growth, margin expansion, analyst upgrades, "
    "institutional accumulation, competitive moats, positive news catalysts. "
    "Cite specific numbers from the DATA BLOCK only. Keep it 200-250 words. No invented data."
)

_BEAR_SYSTEM = (
    "You are a skeptical risk analyst making the STRONGEST POSSIBLE BEAR CASE. "
    "Focus on: overvaluation, negative momentum, rising competition, debt load, "
    "insider selling, analyst downgrades, earnings disappointment risk, negative news. "
    "Cite specific numbers from the DATA BLOCK only. Keep it 200-250 words. No invented data."
)

_RISK_SYSTEM = (
    "You are a quantitative risk manager focused on downside risk. "
    "Focus on: beta/volatility, upcoming earnings dates, macro/sector risk, "
    "support/resistance levels from the technicals, position sizing caution. "
    "Cite specific numbers from the DATA BLOCK only. Keep it 200-250 words. No invented data."
)

_MODERATOR_SYSTEM = (
    "You are a senior investment committee chair synthesizing three analyst opinions. "
    "Structure your response EXACTLY as:\n"
    "## CONSENSUS\n(what all three analysts agree on)\n\n"
    "## KEY DEBATE\n(the main disagreement between bull and bear)\n\n"
    "## RISK FACTORS\n(top 2-3 risks from the risk analyst)\n\n"
    "## VERDICT\n**Buy / Hold / Sell** — Confidence: X/10\n\n"
    "## RATIONALE\n(2-3 sentences grounded in the data)\n\n"
    "Keep total response under 300 words."
)


# ── Compliance disclaimer ─────────────────────────────────────────────────────

_DISCLAIMER = (
    "\n\n---\n*Educational analysis only — not personalized investment advice under the "
    "Investment Advisers Act of 1940. Consult a licensed financial adviser before making "
    "investment decisions.*"
)


def _ensure_disclaimer(text: str) -> str:
    """Structural post-processor: appends disclaimer if AI omitted it."""
    if "not financial advice" not in text.lower() and "educational" not in text.lower():
        return text + _DISCLAIMER
    return text


# ── Model client helpers ──────────────────────────────────────────────────────

def _resolve_api_key(model: str, user_settings: Optional[dict]) -> str | None:
    """Return the API key to use: BYOK if configured, else server env key."""
    if user_settings and user_settings.get("use_byok"):
        if model == "gemini":
            return user_settings.get("byok_gemini_key") or os.getenv("GEMINI_API_KEY")
        return user_settings.get("byok_claude_key") or os.getenv("ANTHROPIC_API_KEY")
    return os.getenv("GEMINI_API_KEY") if model == "gemini" else os.getenv("ANTHROPIC_API_KEY")


def _is_byok(user_settings: Optional[dict]) -> bool:
    return bool(user_settings and user_settings.get("use_byok"))


def _claude_model(user_settings: Optional[dict]) -> str:
    return "claude-sonnet-4-6"


def _gemini_model(user_settings: Optional[dict]) -> str:
    return "gemini-1.5-flash"


# ── Sync AI call (Claude or Gemini) ──────────────────────────────────────────

def _call_ai(
    prompt: str,
    system: str,
    max_tokens: int,
    user_settings: Optional[dict] = None,
) -> tuple[str, str, int, int]:
    """
    Call Claude or Gemini based on user_settings.preferred_model.
    Returns: (text, model_name, input_tokens, output_tokens)
    """
    model_pref = (user_settings or {}).get("preferred_model", "claude")

    if model_pref == "gemini":
        return _call_gemini(prompt, system, max_tokens, user_settings)
    return _call_claude(prompt, system, max_tokens, user_settings)


def _call_claude(
    prompt: str,
    system: str,
    max_tokens: int,
    user_settings: Optional[dict] = None,
) -> tuple[str, str, int, int]:
    api_key = _resolve_api_key("claude", user_settings)
    if not api_key:
        return "ANTHROPIC_API_KEY not configured. Add it to .env or provide your own key in Settings.", "claude-sonnet-4-6", 0, 0
    model = _claude_model(user_settings)
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        system=system,
    )
    return msg.content[0].text, model, msg.usage.input_tokens, msg.usage.output_tokens


def _call_gemini(
    prompt: str,
    system: str,
    max_tokens: int,
    user_settings: Optional[dict] = None,
) -> tuple[str, str, int, int]:
    api_key = _resolve_api_key("gemini", user_settings)
    if not api_key:
        return "GEMINI_API_KEY not configured. Add it to .env or provide your own key in Settings.", "gemini-1.5-flash", 0, 0
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model_name = _gemini_model(user_settings)
        model_obj = genai.GenerativeModel(
            model_name,
            system_instruction=system,
            generation_config={"max_output_tokens": max_tokens},
        )
        response = model_obj.generate_content(prompt)
        text = response.text
        usage = response.usage_metadata
        in_t = getattr(usage, "prompt_token_count", 0) or 0
        out_t = getattr(usage, "candidates_token_count", 0) or 0
        return text, model_name, in_t, out_t
    except ImportError:
        return "google-generativeai package not installed. Run: pip install google-generativeai", "gemini-1.5-flash", 0, 0


# ── Async AI call (for agent council) ────────────────────────────────────────

async def _call_claude_async(
    prompt: str,
    system: str,
    max_tokens: int,
    api_key: str,
    model: str = "claude-haiku-4-5-20251001",
) -> tuple[str, int, int]:
    client = anthropic.AsyncAnthropic(api_key=api_key)
    msg = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        system=system,
    )
    return msg.content[0].text, msg.usage.input_tokens, msg.usage.output_tokens


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


# ── Data block builder ────────────────────────────────────────────────────────

def _build_deep_data_block(analysis: DeepStockAnalysis) -> str:
    lines = [
        f"=== DATA BLOCK FOR {analysis.ticker} ===",
        f"Company: {analysis.name or 'N/A'}",
        f"Data fetched: {analysis.fetched_at}",
        "",
    ]
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
    if analysis.technicals:
        t = analysis.technicals
        lines += [
            "[TECHNICALS — computed from split-adjusted OHLCV history]",
            # t.current_price is the last adj. close from the same fetch as the SMAs.
            # Show it explicitly so the AI compares SMAs against the correct price basis,
            # not the real-time quote above (which may diverge after a recent split).
            f"Adj. close basis (SMA reference price): ${t.current_price:.2f}" if t.current_price else "Adj. close basis: N/A",
            *(["⚠️  NOTE: real-time quote and adj. close diverge >10% — recent split or data lag likely; SMAs are relative to adj. close basis only"]
              if (analysis.quote and t.current_price and analysis.quote.price > 0
                  and abs(analysis.quote.price - t.current_price) / analysis.quote.price > 0.10)
              else []),
            f"RSI(14): {t.rsi_14 or 'N/A'} | Trend: {t.trend.upper()}",
            f"MACD Line: {t.macd_line or 'N/A'} | Signal: {t.macd_signal or 'N/A'} | Histogram: {t.macd_histogram or 'N/A'}",
            f"SMA20: {t.sma_20 or 'N/A'} | SMA50: {t.sma_50 or 'N/A'} | SMA200: {t.sma_200 or 'N/A'}",
            f"Bollinger: Upper {t.bb_upper or 'N/A'} / Middle {t.bb_middle or 'N/A'} / Lower {t.bb_lower or 'N/A'} | %B: {t.bb_pct_b or 'N/A'}",
            f"Volume vs 20d avg: {t.volume_ratio or 'N/A'}x",
            f"Momentum: 1d={t.momentum_1d or 'N/A'}% | 5d={t.momentum_5d or 'N/A'}% | 1mo={t.momentum_1mo or 'N/A'}%",
            f"Signals: {'; '.join(t.signals) if t.signals else 'None'}",
            "",
        ]
    if analysis.fundamentals:
        f = analysis.fundamentals
        _de_display = f"{f.debt_to_equity / 100:.2f}x" if f.debt_to_equity is not None else "N/A"
        lines += [
            "[FUNDAMENTALS — from Yahoo Finance .info]",
            f"Sector: {f.sector or 'N/A'} | Industry: {f.industry or 'N/A'}",
            f"P/E (trailing): {f.pe_ratio or 'N/A'} | P/E (forward): {f.forward_pe or 'N/A'}",
            f"P/B: {f.pb_ratio or 'N/A'} | PEG: {f.peg_ratio or 'N/A'}",
            f"EPS (trailing): {f.eps_trailing or 'N/A'} | EPS (forward): {f.eps_forward or 'N/A'}",
            f"ROE: {(f.roe*100):.1f}%" if f.roe is not None else "ROE: N/A",
            f"Debt/Equity: {_de_display}",
            f"Revenue Growth (YoY): {(f.revenue_growth*100):.1f}%" if f.revenue_growth is not None else "Revenue Growth: N/A",
            f"Profit Margin: {(f.profit_margin*100):.1f}%" if f.profit_margin is not None else "Profit Margin: N/A",
            f"Free Cash Flow: ${f.free_cashflow/1e9:.1f}B" if f.free_cashflow is not None else "Free Cash Flow: N/A",
            f"Beta: {f.beta or 'N/A'}",
            f"Analyst Target (mean): ${f.target_mean_price or 'N/A'} | Recommendation: {f.recommendation or 'N/A'}",
            "",
        ]
    if analysis.fundamental_score:
        fs = analysis.fundamental_score
        lines += [
            "[FUNDAMENTAL SCORE — rule-based]",
            f"Score: {fs.score}/10",
            f"Reasoning: {'; '.join(fs.reasoning)}",
            "",
        ]
    if analysis.analyst_data:
        ad = analysis.analyst_data
        lines += [
            "[ANALYST DATA]",
            f"Consensus: {ad.consensus or 'N/A'} | Strong Buy: {ad.strong_buy_count} | Buy: {ad.buy_count} | Hold: {ad.hold_count} | Sell: {ad.sell_count}",
            f"Next Earnings: {ad.earnings_date or 'N/A'} | EPS Estimate: {ad.eps_estimate or 'N/A'}",
        ]
        if ad.recent_recommendations:
            for rec in ad.recent_recommendations[:5]:
                lines.append(f"  {rec.get('date','')} | {rec.get('firm','')} | {rec.get('to_grade','')} | {rec.get('action','')}")
        lines.append("")
    if analysis.institutional_data:
        inst = analysis.institutional_data
        lines += [
            "[INSTITUTIONAL]",
            f"% Insiders: {(inst.pct_insiders*100):.1f}%" if inst.pct_insiders is not None else "% Insiders: N/A",
            f"% Institutions: {(inst.pct_institutions*100):.1f}%" if inst.pct_institutions is not None else "% Institutions: N/A",
        ]
        if inst.top_holders:
            for h in inst.top_holders[:5]:
                pct = f"{h.get('pct_held',0)*100:.2f}%" if h.get('pct_held') is not None else "N/A"
                lines.append(f"  {h.get('holder','?')} — {pct}")
        lines.append("")
    if analysis.news and analysis.news.articles:
        lines += ["[RECENT NEWS]", format_news_for_prompt(analysis.news), ""]
    lines.append("=== END DATA BLOCK ===")
    return "\n".join(lines)


# ── Public advisor functions ──────────────────────────────────────────────────

def get_advice(
    summary: PortfolioSummary,
    question: Optional[str] = None,
    risk_tolerance: str = "moderate",
    user_settings: Optional[dict] = None,
    user_id: Optional[str] = None,
) -> str:
    risk_desc = {
        "conservative": "prefers capital preservation, low volatility, dividend-paying stocks",
        "moderate": "seeks balanced growth with manageable risk",
        "aggressive": "seeks maximum growth, comfortable with high volatility",
    }.get(risk_tolerance, "seeks balanced growth with manageable risk")

    system = (
        "You are an experienced portfolio advisor. Analyze only the portfolio data provided. "
        "Be specific about tickers and numbers. This is educational analysis, not financial advice."
    )
    user_msg = (
        f"Risk tolerance: {risk_tolerance} ({risk_desc}).\n\n"
        f"=== PORTFOLIO DATA ===\n{_build_portfolio_context(summary)}\n\n"
    )
    user_msg += question if question else (
        "Please analyze this portfolio:\n"
        "1. Overall assessment (diversification, concentration risk)\n"
        "2. Top performing and underperforming positions\n"
        "3. Key risks\n"
        "4. Actionable recommendations\n"
        "5. Rebalancing suggestions"
    )

    text, model, in_t, out_t = _call_ai(user_msg, system, 3000, user_settings)
    if user_id:
        import token_tracker
        token_tracker.track_usage(user_id, "portfolio_advice", model, in_t, out_t, _is_byok(user_settings))
    return _ensure_disclaimer(text)


def get_deep_analysis_advice(
    analysis: DeepStockAnalysis,
    question: Optional[str] = None,
    user_settings: Optional[dict] = None,
    user_id: Optional[str] = None,
) -> str:
    data_block = _build_deep_data_block(analysis)
    system = _GROUNDED_SYSTEM.replace("{fetched_at}", analysis.fetched_at)
    task = (
        f"Answer this specific question about {analysis.ticker}: {question}"
        if question else
        f"Provide a comprehensive analysis of {analysis.ticker}:\n"
        "1. **Technical Picture** — trend, momentum signals, support/resistance context\n"
        "2. **Fundamental Assessment** — valuation, quality (ROE, margins, FCF), growth\n"
        "3. **Analyst & Institutional Sentiment** — consensus, holder changes\n"
        "4. **News-Driven Catalysts or Risks** — cite specific headlines\n"
        "5. **Bull Case vs Bear Case** — data points only\n"
        "6. **Verdict** — short-term trade / long-term hold / avoid with explicit data rationale"
    )

    text, model, in_t, out_t = _call_ai(f"{data_block}\n\n{task}", system, 4096, user_settings)
    if user_id:
        import token_tracker
        token_tracker.track_usage(user_id, "deep_analysis", model, in_t, out_t, _is_byok(user_settings))
    return _ensure_disclaimer(text)


def get_screener_advice(
    result: ScreenerResult,
    user_settings: Optional[dict] = None,
    user_id: Optional[str] = None,
) -> str:
    mode = result.screener_type
    picks = result.picks
    if not picks:
        return "No picks found in screener results."

    lines = [
        f"=== SCREENER DATA BLOCK ({mode.upper()}) ===",
        f"Universe: {result.universe_size} tickers | Fetched: {result.fetched_at}",
        "",
    ]
    for i, pick in enumerate(picks, 1):
        if isinstance(pick, DayPick):
            lines += [
                f"{i}. {pick.ticker} — Score: {pick.composite_score:.2f}/10",
                f"   ${pick.price or 'N/A'} | 1d: {pick.momentum_1d or 'N/A'}% | 5d: {pick.momentum_5d or 'N/A'}%",
                f"   Volume: {pick.volume_ratio or 'N/A'}x | RSI: {pick.rsi_14 or 'N/A'} | News: {pick.news_count}",
                f"   Reasoning: {'; '.join(pick.reasoning)}",
            ]
        elif isinstance(pick, LongTermPick):
            lines += [
                f"{i}. {pick.ticker} ({pick.sector or '?'}) — Score: {pick.composite_score:.2f}/10",
                f"   ROE: {(pick.roe*100):.1f}%" if pick.roe else "   ROE: N/A",
                f"   D/E: {pick.debt_to_equity or 'N/A'} | Margin: {(pick.profit_margin*100):.1f}%" if pick.profit_margin else f"   D/E: {pick.debt_to_equity or 'N/A'}",
                f"   Reasoning: {'; '.join(pick.reasoning)}",
            ]
        lines.append("")

    lines.append("=== END SCREENER DATA BLOCK ===")
    data_block = "\n".join(lines)
    system = _GROUNDED_SYSTEM.replace("{fetched_at}", result.fetched_at)
    task = (
        "Explain why these stocks scored highest today based ONLY on the screener data above."
        if mode == "best_of_day" else
        "Explain why these stocks scored highest for long-term quality based ONLY on the screener data above."
    )

    text, model, in_t, out_t = _call_ai(f"{data_block}\n\n{task}", system, 2048, user_settings)
    if user_id:
        import token_tracker
        token_tracker.track_usage(user_id, "screener", model, in_t, out_t, _is_byok(user_settings))
    return _ensure_disclaimer(text)


def get_chat_response(
    message: str,
    context_data: str,
    user_settings: Optional[dict] = None,
    user_id: Optional[str] = None,
) -> str:
    """General investment chat with injected live market data context."""
    system = (
        "You are an expert investment analyst with access to real-time market data. "
        "RULES: Only cite numbers from the LIVE MARKET DATA block. Never invent prices or ratios. "
        "For ranking questions score by: momentum + fundamentals + analyst sentiment. "
        "Always mention live price and 1-day change when discussing a specific stock. "
        "End responses with '⚠️ Not financial advice.' Keep responses under 500 words."
    )
    prompt = f"{context_data}\n\nUser question: {message}"

    # Wrap user message in delimiter to resist prompt injection
    safe_prompt = f"{context_data}\n\n<user_question>\n{message}\n</user_question>\n\nAnswer only the investment question inside <user_question> tags."
    text, model, in_t, out_t = _call_ai(safe_prompt, system, 2000, user_settings)
    if user_id:
        import token_tracker
        token_tracker.track_usage(user_id, "chat", model, in_t, out_t, _is_byok(user_settings))
    return _ensure_disclaimer(text)


# ── Agent Council (async, 3 agents + moderator) ───────────────────────────────

async def get_agent_council(
    analysis: DeepStockAnalysis,
    user_settings: Optional[dict] = None,
    user_id: Optional[str] = None,
) -> dict:
    """Run Bull / Bear / Risk agents in parallel, then synthesize with Moderator."""
    api_key = _resolve_api_key("claude", user_settings)
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not configured"}

    data_block = _build_deep_data_block(analysis)
    haiku = "claude-haiku-4-5-20251001"
    sonnet = "claude-sonnet-4-6"

    bull_t, bear_t, risk_t = await asyncio.gather(
        _call_claude_async(data_block, _BULL_SYSTEM, 500, api_key, haiku),
        _call_claude_async(data_block, _BEAR_SYSTEM, 500, api_key, haiku),
        _call_claude_async(data_block, _RISK_SYSTEM, 500, api_key, haiku),
    )
    bull_text, bull_in, bull_out = bull_t
    bear_text, bear_in, bear_out = bear_t
    risk_text, risk_in, risk_out = risk_t

    moderator_input = (
        f"{data_block}\n\n"
        f"=== BULL CASE ===\n{bull_text}\n\n"
        f"=== BEAR CASE ===\n{bear_text}\n\n"
        f"=== RISK ASSESSMENT ===\n{risk_text}\n\n"
        "Now synthesize these three perspectives."
    )
    mod_text, mod_in, mod_out = await _call_claude_async(moderator_input, _MODERATOR_SYSTEM, 600, api_key, sonnet)

    if user_id:
        import token_tracker
        byok = _is_byok(user_settings)
        token_tracker.track_usage(user_id, "council", haiku, bull_in + bear_in + risk_in, bull_out + bear_out + risk_out, byok)
        token_tracker.track_usage(user_id, "council", sonnet, mod_in, mod_out, byok)

    return {
        "ticker": analysis.ticker,
        "name": analysis.name,
        "bull": bull_text,
        "bear": bear_text,
        "risk": risk_text,
        "verdict": mod_text,
        "fetched_at": analysis.fetched_at,
    }


# ── Signal Scanner ────────────────────────────────────────────────────────────

_SIGNAL_SYSTEM = (
    "You are a market signal analyst. You synthesize news flow and technical momentum data "
    "to identify stocks with the strongest near-term setups. You do NOT predict prices. "
    "You identify setups and explain the conditions. "
    "RULES: Never give price targets. Use 'high/medium/low' confidence only. "
    "lean must be exactly 'bullish', 'bearish', or 'neutral'. "
    "signal_type must be exactly one of: 'momentum_burst', 'news_catalyst', 'oversold_bounce', 'sector_rotation'. "
    "ai_rationale must be 1-2 sentences, grounded only in the data provided. "
    "Return ONLY a valid JSON object — no markdown, no explanation, no extra text."
)

_SIGNAL_PROMPT_TEMPLATE = """\
NEWS HEADLINES (recent market news):
{news_block}

TOP MOMENTUM STOCKS (from screener):
{screener_block}

Based on the data above, identify up to 5 stocks with the strongest setups right now.
Return ONLY this JSON (no markdown fences, no extra keys):
{{
  "market_summary": "<one sentence on overall market mood based on the news>",
  "signals": [
    {{
      "ticker": "AAPL",
      "signal_type": "momentum_burst",
      "lean": "bullish",
      "confidence": "high",
      "ai_rationale": "Volume is 2.8x the 20-day average with RSI still below 70, suggesting momentum has room to continue. Recent news catalyst aligns with the technical breakout."
    }}
  ]
}}
"""


def get_signal_scan(
    news_text: str,
    screener_picks: list[DayPick],
    user_settings: Optional[dict] = None,
    user_id: Optional[str] = None,
) -> SignalScanResult:
    """
    Synthesize news flow + screener momentum data into ranked signal cards.
    Returns SignalScanResult with up to 5 StockSignal objects.
    No price targets. Framed as setup analysis, not prediction.
    """
    from validator import utcnow_iso
    import token_tracker

    now_iso = utcnow_iso()

    screener_block = "\n".join(
        f"{p.ticker}: momentum_1d={p.momentum_1d:+.1f}% | rsi={p.rsi_14 or 'N/A'} | "
        f"volume_ratio={p.volume_ratio or 'N/A'}x | score={p.composite_score:.1f} | "
        f"news={p.news_count} article(s)"
        for p in screener_picks[:15]
    ) or "No screener data available."

    prompt = _SIGNAL_PROMPT_TEMPLATE.format(
        news_block=news_text or "No recent news available.",
        screener_block=screener_block,
    )

    try:
        raw_text, model_name, in_tok, out_tok = _call_ai(
            prompt=prompt,
            system=_SIGNAL_SYSTEM,
            max_tokens=1200,
            user_settings=user_settings,
        )
        if user_id:
            token_tracker.log_usage(user_id, "signal_scan", model_name, in_tok, out_tok,
                                    was_byok=_is_byok(user_settings))
    except Exception as e:
        return SignalScanResult(
            signals=[],
            market_summary="Signal scan unavailable.",
            scan_basis=f"Based on {len(screener_picks)} screener picks",
            fetched_at=now_iso,
        )

    # Parse JSON response
    try:
        # Strip accidental markdown fences
        clean = raw_text.strip()
        if clean.startswith("```"):
            clean = "\n".join(clean.split("\n")[1:])
        if clean.endswith("```"):
            clean = "\n".join(clean.split("\n")[:-1])
        data = json.loads(clean)
    except (json.JSONDecodeError, ValueError):
        # Fallback: return empty result rather than crashing
        return SignalScanResult(
            signals=[],
            market_summary=raw_text[:200] if raw_text else "Parse error.",
            scan_basis=f"Based on {len(screener_picks)} screener picks",
            fetched_at=now_iso,
        )

    signals: list[StockSignal] = []
    for item in data.get("signals", [])[:5]:
        ticker = str(item.get("ticker", "")).upper().strip()
        if not ticker:
            continue
        # Find matching screener pick to attach live data
        pick = next((p for p in screener_picks if p.ticker == ticker), None)
        signals.append(StockSignal(
            ticker=ticker,
            name=pick.name if pick else None,
            signal_type=item.get("signal_type", "momentum_burst"),
            lean=item.get("lean", "neutral"),
            confidence=item.get("confidence", "medium"),
            ai_rationale=_ensure_disclaimer(item.get("ai_rationale", "")),
            momentum_1d=pick.momentum_1d if pick else None,
            rsi_14=pick.rsi_14 if pick else None,
            volume_ratio=pick.volume_ratio if pick else None,
            current_price=pick.price if pick else None,
            change_pct=pick.change_pct if pick else None,
        ))

    return SignalScanResult(
        signals=signals,
        market_summary=data.get("market_summary", ""),
        scan_basis=f"Based on {len(news_text.splitlines())} news headlines + {len(screener_picks)} screener picks",
        fetched_at=now_iso,
    )
