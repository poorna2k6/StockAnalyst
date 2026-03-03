"""AI-powered portfolio advisor using Claude."""

import os
import anthropic

from models import PortfolioSummary


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


def get_advice(
    summary: PortfolioSummary,
    question: str | None = None,
    risk_tolerance: str = "moderate",
) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return (
            "ANTHROPIC_API_KEY not set. Set it in your environment or .env file "
            "to receive AI-powered advice."
        )

    client = anthropic.Anthropic(api_key=api_key)
    portfolio_context = _build_portfolio_context(summary)
    risk_desc = {
        "conservative": "prefers capital preservation, low volatility, dividend-paying stocks and bonds",
        "moderate": "seeks balanced growth with manageable risk, mix of growth and value stocks",
        "aggressive": "seeks maximum growth, comfortable with high volatility and concentrated positions",
    }.get(risk_tolerance, "seeks balanced growth with manageable risk")

    system_prompt = (
        "You are an experienced financial analyst and portfolio advisor. "
        "Analyze the user's stock portfolio and provide clear, actionable insights. "
        "Be specific about tickers and numbers. Always note that this is not official financial advice. "
        "Keep responses concise and structured."
    )

    user_message = (
        f"My risk tolerance: {risk_tolerance} ({risk_desc}).\n\n"
        f"Current portfolio:\n{portfolio_context}\n\n"
    )
    if question:
        user_message += f"My question: {question}"
    else:
        user_message += (
            "Please analyze my portfolio and provide:\n"
            "1. Overall assessment (diversification, risk concentration)\n"
            "2. Top performing and underperforming positions\n"
            "3. Key risks I should be aware of\n"
            "4. Actionable recommendations (what to consider buying, trimming, or selling)\n"
            "5. Any rebalancing suggestions"
        )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": user_message}],
        system=system_prompt,
    )
    return message.content[0].text
