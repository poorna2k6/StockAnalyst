"""Portfolio Health Score — pure rule-based computation, zero AI calls, zero network I/O."""

from dataclasses import dataclass, field
from typing import Optional
from models import PortfolioSummary


@dataclass
class HealthDimension:
    name: str
    score: float          # 0–25
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class PortfolioHealthScore:
    overall: float        # 0–100
    grade: str            # A / B / C / D / F
    diversification: HealthDimension
    risk_alignment: HealthDimension
    goal_alignment: HealthDimension
    quality: HealthDimension
    alerts: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


def _letter_grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _score_diversification(
    summary: PortfolioSummary,
    max_single_position_pct: float,
) -> HealthDimension:
    dim = HealthDimension(name="Diversification")
    positions = summary.positions
    score = 25.0
    issues: list[str] = []
    recs: list[str] = []

    if not positions:
        dim.score = 0.0
        dim.issues = ["No positions in portfolio"]
        dim.recommendations = ["Add diversified positions across sectors"]
        return dim

    n = len(positions)
    # Position count penalty
    if n < 3:
        score -= 10
        issues.append(f"Only {n} position(s) — low diversification")
        recs.append("Aim for at least 5–10 positions across different sectors")
    elif n < 5:
        score -= 5
        issues.append(f"{n} positions — consider adding more")

    # Concentration check
    heavy = [p for p in positions if p.weight > max_single_position_pct]
    for p in heavy:
        penalty = min(8.0, (p.weight - max_single_position_pct) * 0.3)
        score -= penalty
        issues.append(f"{p.ticker} is {p.weight:.1f}% of portfolio (limit: {max_single_position_pct:.0f}%)")
        recs.append(f"Consider trimming {p.ticker} below {max_single_position_pct:.0f}%")

    # Cash drag check
    total = summary.total_value + summary.cash
    if total > 0:
        cash_pct = (summary.cash / total) * 100
        if cash_pct > 30:
            score -= 5
            issues.append(f"High cash allocation: {cash_pct:.1f}% idle")
            recs.append("Deploy excess cash or use money-market ETF")

    dim.score = max(0.0, min(25.0, score))
    dim.issues = issues
    dim.recommendations = recs
    return dim


def _score_risk_alignment(
    summary: PortfolioSummary,
    risk_tolerance: str,
) -> HealthDimension:
    dim = HealthDimension(name="Risk Alignment")
    positions = summary.positions
    score = 25.0
    issues: list[str] = []
    recs: list[str] = []

    if not positions:
        dim.score = 12.5
        return dim

    # Use gain/loss volatility as a risk proxy
    gains = [p.gain_loss_pct for p in positions]
    avg_gl = sum(gains) / len(gains) if gains else 0.0
    losers_pct = len([g for g in gains if g < -15]) / len(gains) * 100

    target_map = {"conservative": 0, "moderate": 1, "aggressive": 2}
    target = target_map.get(risk_tolerance, 1)

    # Heavy losers are concerning for conservative
    if target == 0 and losers_pct > 20:
        score -= 8
        issues.append(f"{losers_pct:.0f}% of positions down >15% — high for conservative risk profile")
        recs.append("Review underperforming positions; consider stop-loss discipline")
    elif target == 1 and losers_pct > 40:
        score -= 5
        issues.append(f"{losers_pct:.0f}% of positions down >15%")

    # Large unrealized losses
    deeply_underwater = [p for p in positions if p.gain_loss_pct < -25]
    if deeply_underwater:
        score -= min(10, len(deeply_underwater) * 3)
        tickers = ", ".join(p.ticker for p in deeply_underwater[:3])
        issues.append(f"Deep losses (>25%) in: {tickers}")
        recs.append("Evaluate tax-loss harvesting or position exit for deeply underwater positions")

    # Aggressive user with no upside
    if target == 2 and avg_gl < -10:
        score -= 5
        issues.append("Aggressive profile but portfolio is significantly underwater")

    dim.score = max(0.0, min(25.0, score))
    dim.issues = issues
    dim.recommendations = recs
    return dim


def _score_goal_alignment(
    summary: PortfolioSummary,
    primary_goal: str,
    tax_sensitive: bool,
) -> HealthDimension:
    dim = HealthDimension(name="Goal Alignment")
    positions = summary.positions
    score = 25.0
    issues: list[str] = []
    recs: list[str] = []

    if not positions:
        dim.score = 12.5
        return dim

    total_value = summary.total_value
    cash_ratio = summary.cash / (total_value + summary.cash) if (total_value + summary.cash) > 0 else 0

    if primary_goal == "income":
        # Income seekers need yield — we can't check dividends without extra data, so flag cash drag
        if cash_ratio < 0.05:
            recs.append("Income goal: ensure holdings include dividend-paying stocks or bond ETFs")
        if len(positions) < 5:
            score -= 5
            issues.append("Income portfolio needs broader diversification for yield stability")

    elif primary_goal == "capital_preservation":
        # Flag any position with large loss
        big_losses = [p for p in positions if p.gain_loss_pct < -10]
        if big_losses:
            score -= min(12, len(big_losses) * 4)
            tickers = ", ".join(p.ticker for p in big_losses[:3])
            issues.append(f"Capital preservation goal but losses in: {tickers}")
            recs.append("Review high-risk positions misaligned with capital preservation goal")

    elif primary_goal == "retirement":
        # Long horizon — concentration in single stock is the main risk
        heavy = [p for p in positions if p.weight > 25]
        if heavy:
            score -= 6
            issues.append("Retirement portfolio: single-stock concentration risk")
            recs.append("Consider index ETFs for core retirement holdings")

    elif primary_goal == "speculation":
        # Acceptable to have losers; just flag if EVERYTHING is losing
        all_losing = all(p.gain_loss_pct < 0 for p in positions)
        if all_losing and len(positions) >= 3:
            score -= 8
            issues.append("All speculative positions are in the red")
            recs.append("Review speculation thesis; consider position sizing discipline")

    # Tax sensitivity flag
    if tax_sensitive:
        big_gains = [p for p in positions if p.gain_loss_pct > 20]
        if big_gains:
            tickers = ", ".join(p.ticker for p in big_gains[:3])
            issues.append(f"Tax-sensitive: large unrealized gains in {tickers} may trigger taxes if sold")
            recs.append("Consult a tax professional before realizing gains in these positions")

    dim.score = max(0.0, min(25.0, score))
    dim.issues = issues
    dim.recommendations = recs
    return dim


def _score_quality(summary: PortfolioSummary) -> HealthDimension:
    # "Portfolio Performance" — reflects realized P&L, NOT business quality.
    # P&L% depends entirely on entry price, not company fundamentals.
    dim = HealthDimension(name="Portfolio Performance")
    positions = summary.positions
    score = 25.0
    issues: list[str] = []
    recs: list[str] = []

    if not positions:
        dim.score = 12.5
        return dim

    total_weighted_gl = sum(p.gain_loss_pct * (p.weight / 100) for p in positions)

    if total_weighted_gl < -20:
        score -= 12
        issues.append(f"Portfolio weighted P&L: {total_weighted_gl:.1f}% — weak quality signal")
        recs.append("Review fundamental quality of underperforming holdings")
    elif total_weighted_gl < -10:
        score -= 6
        issues.append(f"Portfolio weighted P&L: {total_weighted_gl:.1f}%")
    elif total_weighted_gl < 0:
        score -= 2

    # Positive signal for strong performers
    strong = [p for p in positions if p.gain_loss_pct > 30]
    if strong and len(strong) / len(positions) >= 0.4:
        score = min(25.0, score + 3)

    dim.score = max(0.0, min(25.0, score))
    dim.issues = issues
    dim.recommendations = recs
    return dim


def compute_health_score(
    summary: PortfolioSummary,
    risk_tolerance: str = "moderate",
    primary_goal: str = "wealth_accumulation",
    max_single_position_pct: float = 20.0,
    tax_sensitive: bool = False,
) -> PortfolioHealthScore:
    """Compute 0–100 portfolio health score. Pure Python — no network calls."""
    div = _score_diversification(summary, max_single_position_pct)
    risk = _score_risk_alignment(summary, risk_tolerance)
    goal = _score_goal_alignment(summary, primary_goal, tax_sensitive)
    qual = _score_quality(summary)

    overall = div.score + risk.score + goal.score + qual.score

    # Aggregate top recommendations
    all_recs: list[str] = []
    for d in [div, risk, goal, qual]:
        all_recs.extend(d.recommendations)

    # Surface critical alerts (issues that need immediate attention)
    alerts: list[str] = []
    for d in [div, risk, goal, qual]:
        for issue in d.issues:
            if any(kw in issue.lower() for kw in ["deep loss", "capital preservation", ">25%", ">15%"]):
                alerts.append(issue)

    return PortfolioHealthScore(
        overall=round(overall, 1),
        grade=_letter_grade(overall),
        diversification=div,
        risk_alignment=risk,
        goal_alignment=goal,
        quality=qual,
        alerts=alerts[:5],
        recommendations=all_recs[:5],
    )
