"""CLI interface for the Stock Portfolio Advisor."""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from rich.panel import Panel

import portfolio as portfolio_store
import analyzer
import advisor as ai_advisor

app = typer.Typer(help="Stock Portfolio Advisor — smart, grounded, zero-hallucination analysis.")
console = Console()


def _gain_loss_color(value: float) -> str:
    return "green" if value >= 0 else "red"


def _score_color(score: float) -> str:
    if score >= 7.0:
        return "green"
    elif score >= 5.0:
        return "yellow"
    return "red"


def _fmt_pct(val: Optional[float], decimals: int = 1) -> str:
    if val is None:
        return "[dim]N/A[/dim]"
    color = "green" if val >= 0 else "red"
    sign = "+" if val >= 0 else ""
    return f"[{color}]{sign}{val:.{decimals}f}%[/{color}]"


def _fmt_float(val: Optional[float], decimals: int = 2, prefix: str = "") -> str:
    if val is None:
        return "[dim]N/A[/dim]"
    return f"{prefix}{val:.{decimals}f}"


# ── Existing commands ─────────────────────────────────────────────────────────

@app.command()
def show():
    """Show current portfolio summary with live prices."""
    port = portfolio_store.get_portfolio()
    if not port.positions and port.cash == 0:
        console.print("[yellow]Portfolio is empty. Use 'add' to add positions.[/yellow]")
        return

    with console.status("Fetching live prices..."):
        summary = analyzer.build_portfolio_summary(port)

    table = Table(title=f"[bold]{summary.name}[/bold]", show_lines=True)
    table.add_column("Ticker", style="cyan", no_wrap=True)
    table.add_column("Shares", justify="right")
    table.add_column("Avg Cost", justify="right")
    table.add_column("Price", justify="right")
    table.add_column("Value", justify="right")
    table.add_column("Gain/Loss", justify="right")
    table.add_column("Weight", justify="right")

    for pos in summary.positions:
        gl = pos.gain_loss
        color = _gain_loss_color(gl)
        sign = "+" if gl >= 0 else ""
        table.add_row(
            pos.ticker,
            f"{pos.shares:.2f}",
            f"${pos.avg_cost:.2f}",
            f"${pos.current_price:.2f}",
            f"${pos.current_value:,.2f}",
            f"[{color}]{sign}${gl:,.2f} ({sign}{pos.gain_loss_pct:.1f}%)[/{color}]",
            f"{pos.weight:.1f}%",
        )

    if summary.cash:
        table.add_row(
            "CASH", "", "", "",
            f"${summary.cash:,.2f}", "",
            f"{summary.cash / summary.total_value * 100:.1f}%",
        )

    console.print(table)
    gl = summary.total_gain_loss
    color = _gain_loss_color(gl)
    sign = "+" if gl >= 0 else ""
    console.print(Panel(
        f"Total Value: [bold]${summary.total_value:,.2f}[/bold]  |  "
        f"Cost Basis: ${summary.total_cost:,.2f}  |  "
        f"P&L: [{color}]{sign}${gl:,.2f} ({sign}{summary.total_gain_loss_pct:.2f}%)[/{color}]",
        title="Portfolio Summary",
    ))


@app.command()
def add(
    ticker: str = typer.Argument(..., help="Stock ticker symbol (e.g. AAPL)"),
    shares: float = typer.Argument(..., help="Number of shares"),
    avg_cost: float = typer.Argument(..., help="Average cost per share"),
):
    """Add or update a stock position."""
    portfolio_store.add_position(ticker, shares, avg_cost)
    console.print(f"[green]Added {shares} shares of {ticker.upper()} @ ${avg_cost:.2f}[/green]")


@app.command()
def remove(
    ticker: str = typer.Argument(..., help="Stock ticker symbol to remove"),
):
    """Remove a stock position from the portfolio."""
    portfolio_store.remove_position(ticker)
    console.print(f"[yellow]Removed {ticker.upper()} from portfolio.[/yellow]")


@app.command()
def cash(
    amount: float = typer.Argument(..., help="Cash balance amount"),
):
    """Set the cash balance in the portfolio."""
    portfolio_store.set_cash(amount)
    console.print(f"[green]Cash set to ${amount:,.2f}[/green]")


@app.command()
def reset(
    name: str = typer.Option("My Portfolio", help="Portfolio name"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Reset portfolio to empty."""
    if not confirm:
        typer.confirm("This will clear all positions. Continue?", abort=True)
    portfolio_store.reset_portfolio(name)
    console.print("[yellow]Portfolio reset.[/yellow]")


@app.command()
def quote(
    ticker: str = typer.Argument(..., help="Stock ticker symbol"),
):
    """Get a live stock quote."""
    with console.status(f"Fetching quote for {ticker.upper()}..."):
        q = analyzer.get_quote(ticker.upper())

    color = _gain_loss_color(q.change)
    sign = "+" if q.change >= 0 else ""
    console.print(Panel(
        f"[bold]{q.name or q.ticker}[/bold] ({q.ticker})\n"
        f"Price: [bold]${q.price:.2f}[/bold]  [{color}]{sign}${q.change:.2f} ({sign}{q.change_pct:.2f}%)[/{color}]\n"
        f"Volume: {q.volume:,}\n"
        + (f"Market Cap: ${q.market_cap / 1e9:.2f}B\n" if q.market_cap else "")
        + (f"P/E Ratio: {q.pe_ratio:.1f}\n" if q.pe_ratio else "")
        + (f"52-Week: ${q.week_52_low:.2f} — ${q.week_52_high:.2f}" if q.week_52_low else ""),
        title="Live Quote",
    ))


@app.command()
def advise(
    risk: str = typer.Option("moderate", help="Risk tolerance: conservative, moderate, aggressive"),
    question: Optional[str] = typer.Option(None, "--question", "-q", help="Specific question"),
):
    """Get AI-powered portfolio advice from Claude."""
    port = portfolio_store.get_portfolio()
    if not port.positions:
        console.print("[yellow]Portfolio is empty. Add positions first.[/yellow]")
        return

    with console.status("Fetching prices and generating advice..."):
        summary = analyzer.build_portfolio_summary(port)
        advice = ai_advisor.get_advice(summary, question=question, risk_tolerance=risk)

    console.print(Panel(advice, title="[bold blue]AI Portfolio Advice[/bold blue]", expand=False))


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host to bind"),
    port: int = typer.Option(8000, help="Port to listen on"),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
):
    """Start the REST API server."""
    import uvicorn
    uvicorn.run("main:app", host=host, port=port, reload=reload)


# ── New commands ──────────────────────────────────────────────────────────────

@app.command()
def analyze(
    ticker: str = typer.Argument(..., help="Stock ticker to analyze deeply"),
    question: Optional[str] = typer.Option(None, "--question", "-q", help="Specific question"),
):
    """
    Deep in/out analysis: technicals, fundamentals, news, institutional, AI synthesis.
    All data fetched from Yahoo Finance — zero hallucination.
    """
    ticker = ticker.upper()
    with console.status(f"Validating {ticker}..."):
        v = analyzer.validate_ticker(ticker)
    if not v.valid:
        console.print(f"[red]Invalid ticker: {v.error}[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Fetching deep analysis for {ticker} ({v.name})...[/cyan]")
    with console.status("Fetching technicals, fundamentals, news, institutional data..."):
        deep = analyzer.build_deep_analysis(ticker)

    # Technicals table
    if deep.technicals:
        t = deep.technicals
        tech_table = Table(title="[bold cyan]Technical Indicators[/bold cyan]", show_lines=False)
        tech_table.add_column("Indicator", style="cyan")
        tech_table.add_column("Value", justify="right")
        tech_table.add_column("Signal")

        rsi_signal = "Oversold" if (t.rsi_14 or 50) < 30 else ("Overbought" if (t.rsi_14 or 50) > 70 else "Neutral")
        tech_table.add_row("RSI(14)", _fmt_float(t.rsi_14), rsi_signal)
        tech_table.add_row("MACD", f"{_fmt_float(t.macd_line)} / {_fmt_float(t.macd_signal)}", "Bullish" if (t.macd_histogram or 0) > 0 else "Bearish")
        tech_table.add_row("SMA 20/50/200", f"{_fmt_float(t.sma_20)} / {_fmt_float(t.sma_50)} / {_fmt_float(t.sma_200)}", t.trend.upper())
        tech_table.add_row("Bollinger %B", _fmt_float(t.bb_pct_b), "Near Lower" if (t.bb_pct_b or 0.5) < 0.2 else ("Near Upper" if (t.bb_pct_b or 0.5) > 0.8 else "Mid-range"))
        tech_table.add_row("Volume Ratio", f"{_fmt_float(t.volume_ratio)}x", "Surge" if (t.volume_ratio or 1) >= 2 else "Normal")
        tech_table.add_row("Momentum 1d/5d/1mo", f"{_fmt_pct(t.momentum_1d)}/{_fmt_pct(t.momentum_5d)}/{_fmt_pct(t.momentum_1mo)}", "")
        console.print(tech_table)

    # Fundamentals table
    if deep.fundamentals:
        f = deep.fundamentals
        fund_table = Table(title="[bold green]Fundamentals[/bold green]", show_lines=False)
        fund_table.add_column("Metric", style="cyan")
        fund_table.add_column("Value", justify="right")
        fund_table.add_column("Metric", style="cyan")
        fund_table.add_column("Value", justify="right")

        fund_table.add_row("P/E (trailing)", _fmt_float(f.pe_ratio), "P/E (forward)", _fmt_float(f.forward_pe))
        fund_table.add_row("P/B", _fmt_float(f.pb_ratio), "PEG", _fmt_float(f.peg_ratio))
        fund_table.add_row("ROE", _fmt_pct(f.roe * 100 if f.roe else None), "ROA", _fmt_pct(f.roa * 100 if f.roa else None))
        fund_table.add_row("Rev Growth", _fmt_pct(f.revenue_growth * 100 if f.revenue_growth else None), "EPS Growth", _fmt_pct(f.earnings_growth * 100 if f.earnings_growth else None))
        fund_table.add_row("Profit Margin", _fmt_pct(f.profit_margin * 100 if f.profit_margin else None), "Gross Margin", _fmt_pct(f.gross_margin * 100 if f.gross_margin else None))
        fund_table.add_row("Debt/Equity", _fmt_float(f.debt_to_equity), "Current Ratio", _fmt_float(f.current_ratio))
        fund_table.add_row("Free Cash Flow", f"${f.free_cashflow/1e9:.1f}B" if f.free_cashflow else "[dim]N/A[/dim]", "Beta", _fmt_float(f.beta))
        fund_table.add_row("Analyst Target", f"${f.target_mean_price:.2f}" if f.target_mean_price else "[dim]N/A[/dim]", "Recommendation", f.recommendation or "[dim]N/A[/dim]")
        console.print(fund_table)

    # Fundamental score
    if deep.fundamental_score:
        fs = deep.fundamental_score
        color = _score_color(fs.score)
        console.print(Panel(
            f"Score: [{color}]{fs.score}/10[/{color}]\n" +
            "\n".join(f"  • {r}" for r in fs.reasoning),
            title="[bold]Fundamental Quality Score[/bold]",
        ))

    # Analyst + Institutional
    if deep.analyst_data:
        ad = deep.analyst_data
        console.print(Panel(
            f"Consensus: [bold]{ad.consensus or 'N/A'}[/bold]  |  "
            f"Strong Buy: {ad.strong_buy_count}  Buy: {ad.buy_count}  Hold: {ad.hold_count}  Sell: {ad.sell_count}\n"
            f"Next Earnings: {ad.earnings_date or 'N/A'}  |  EPS Estimate: {ad.eps_estimate or 'N/A'}",
            title="Analyst Data",
        ))

    if deep.institutional_data:
        inst = deep.institutional_data
        insider_str = f"{inst.pct_insiders*100:.1f}%" if inst.pct_insiders else "N/A"
        inst_str = f"{inst.pct_institutions*100:.1f}%" if inst.pct_institutions else "N/A"
        holder_lines = [f"  {h.get('holder','?')} — {h.get('pct_held',0)*100:.2f}%" for h in inst.top_holders[:5]]
        console.print(Panel(
            f"Insiders: {insider_str}  |  Institutions: {inst_str}\n" +
            "\n".join(holder_lines),
            title="Institutional Ownership",
        ))

    # News
    if deep.news and deep.news.articles:
        news_table = Table(title="[bold]Recent News[/bold]", show_lines=False)
        news_table.add_column("Date", style="dim", no_wrap=True)
        news_table.add_column("Publisher", style="cyan", no_wrap=True)
        news_table.add_column("Headline")

        for item in deep.news.articles[:8]:
            date_str = (item.published_at or "")[:10]
            news_table.add_row(date_str, item.publisher[:20], item.title[:80])

        console.print(news_table)
        if deep.news.sentiment:
            s = deep.news.sentiment
            console.print(f"[dim]News sentiment: {s.overall.upper()} ({s.positive_count}+ / {s.negative_count}- / {s.neutral_count}~)[/dim]")

    # AI analysis
    with console.status("Generating AI analysis (grounded in above data)..."):
        ai_text = ai_advisor.get_deep_analysis_advice(deep, question=question)

    console.print(Panel(ai_text, title="[bold blue]AI Analysis (Data-Grounded)[/bold blue]", expand=False))


@app.command()
def best_day(
    top_n: int = typer.Option(10, "--top", "-n", help="Number of top picks"),
):
    """
    Best stocks of today ranked by momentum, volume surge, RSI, and news catalysts.
    Scored from real data — no guessing. Curated 40-ticker universe.
    """
    with console.status(f"Screening best-of-day picks (universe: ~{len(__import__('screener').SCREENER_UNIVERSE)} tickers)..."):
        from screener import screen_best_of_day
        result = screen_best_of_day(top_n=top_n)

    if not result.picks:
        console.print("[yellow]No picks found.[/yellow]")
        return

    table = Table(title=f"[bold]Best Stocks Today — Top {top_n}[/bold]", show_lines=True)
    table.add_column("Rank", justify="center")
    table.add_column("Ticker", style="cyan", no_wrap=True)
    table.add_column("Price", justify="right")
    table.add_column("1d Chg", justify="right")
    table.add_column("5d Chg", justify="right")
    table.add_column("Vol Ratio", justify="right")
    table.add_column("RSI", justify="right")
    table.add_column("News", justify="center")
    table.add_column("Score", justify="right")

    for i, pick in enumerate(result.picks, 1):
        from models import DayPick
        if isinstance(pick, DayPick):
            score_color = _score_color(pick.composite_score)
            table.add_row(
                str(i),
                pick.ticker,
                f"${pick.price:.2f}" if pick.price else "N/A",
                _fmt_pct(pick.momentum_1d),
                _fmt_pct(pick.momentum_5d),
                f"{pick.volume_ratio:.1f}x" if pick.volume_ratio else "N/A",
                f"{pick.rsi_14:.1f}" if pick.rsi_14 else "N/A",
                str(pick.news_count),
                f"[{score_color}]{pick.composite_score:.1f}[/{score_color}]",
            )

    console.print(table)
    console.print(f"[dim]Universe: {result.universe_size} tickers | Fetched: {result.fetched_at[:19]}[/dim]")

    with console.status("Generating AI narrative..."):
        narrative = ai_advisor.get_screener_advice(result)
    console.print(Panel(narrative, title="[bold blue]AI Narrative (Data-Grounded)[/bold blue]", expand=False))


@app.command()
def best_longterm(
    top_n: int = typer.Option(10, "--top", "-n", help="Number of top picks"),
    min_score: float = typer.Option(5.0, help="Minimum fundamental score (0-10)"),
):
    """
    Best long-term stocks ranked by fundamental quality score.
    Based on ROE, revenue growth, FCF, margins, debt, PEG — real data only.
    """
    with console.status(f"Screening long-term picks (universe: ~{len(__import__('screener').SCREENER_UNIVERSE)} tickers)..."):
        from screener import screen_long_term
        result = screen_long_term(top_n=top_n, min_score=min_score)

    if not result.picks:
        console.print("[yellow]No picks found above minimum score.[/yellow]")
        return

    table = Table(title=f"[bold]Best Long-Term Stocks — Top {top_n}[/bold]", show_lines=True)
    table.add_column("Rank", justify="center")
    table.add_column("Ticker", style="cyan", no_wrap=True)
    table.add_column("Sector")
    table.add_column("ROE", justify="right")
    table.add_column("Rev Growth", justify="right")
    table.add_column("Margin", justify="right")
    table.add_column("D/E", justify="right")
    table.add_column("FCF", justify="right")
    table.add_column("Score", justify="right")

    for i, pick in enumerate(result.picks, 1):
        from models import LongTermPick
        if isinstance(pick, LongTermPick):
            score_color = _score_color(pick.composite_score)
            table.add_row(
                str(i),
                pick.ticker,
                (pick.sector or "Unknown")[:18],
                _fmt_pct(pick.roe * 100 if pick.roe else None),
                _fmt_pct(pick.revenue_growth * 100 if pick.revenue_growth else None),
                _fmt_pct(pick.profit_margin * 100 if pick.profit_margin else None),
                f"{pick.debt_to_equity:.2f}" if pick.debt_to_equity else "N/A",
                f"${pick.free_cashflow/1e9:.1f}B" if pick.free_cashflow else "N/A",
                f"[{score_color}]{pick.composite_score:.1f}[/{score_color}]",
            )

    console.print(table)
    console.print(f"[dim]Universe: {result.universe_size} tickers | Fetched: {result.fetched_at[:19]}[/dim]")

    with console.status("Generating AI narrative..."):
        narrative = ai_advisor.get_screener_advice(result)
    console.print(Panel(narrative, title="[bold blue]AI Narrative (Data-Grounded)[/bold blue]", expand=False))


@app.command()
def correlated(
    ticker: str = typer.Argument(..., help="Ticker to find correlated stocks for"),
    top_n: int = typer.Option(5, "--top", "-n", help="Number of correlated stocks"),
):
    """
    Find most correlated stocks by Pearson correlation of 1-year daily returns.
    Real computation — not sector guessing.
    """
    ticker = ticker.upper()
    with console.status(f"Validating {ticker}..."):
        v = analyzer.validate_ticker(ticker)
    if not v.valid:
        console.print(f"[red]{v.error}[/red]")
        raise typer.Exit(1)

    with console.status(f"Computing correlations for {ticker} (downloading 1yr history for ~40 tickers)..."):
        from screener import find_correlated_stocks
        result = find_correlated_stocks(ticker, top_n=top_n)

    if not result.correlated_stocks:
        console.print("[yellow]No correlated stocks found.[/yellow]")
        return

    table = Table(title=f"[bold]Stocks Correlated with {ticker}[/bold]", show_lines=False)
    table.add_column("Rank", justify="center")
    table.add_column("Ticker", style="cyan")
    table.add_column("Correlation", justify="right")
    table.add_column("Relationship")

    for i, cs in enumerate(result.correlated_stocks, 1):
        corr = cs.correlation
        color = "green" if corr >= 0.7 else ("yellow" if corr >= 0.4 else "red")
        strength = "Strong" if abs(corr) >= 0.7 else ("Moderate" if abs(corr) >= 0.4 else "Weak")
        direction = "Positive" if corr >= 0 else "Negative"
        table.add_row(str(i), cs.ticker, f"[{color}]{corr:.4f}[/{color}]", f"{strength} {direction}")

    console.print(table)
    console.print(f"[dim]Period: {result.period} | Fetched: {result.fetched_at[:19]}[/dim]")


@app.command()
def news(
    ticker: Optional[str] = typer.Argument(None, help="Ticker (omit for market news)"),
    max_items: int = typer.Option(10, "--max", "-n", help="Max articles"),
):
    """
    Show recent financial news. Pass a ticker for stock-specific news,
    omit for broad market news. Raw fetched data — no AI.
    """
    from news_fetcher import get_ticker_news, get_market_news

    if ticker:
        ticker = ticker.upper()
        with console.status(f"Validating {ticker}..."):
            v = analyzer.validate_ticker(ticker)
        if not v.valid:
            console.print(f"[red]{v.error}[/red]")
            raise typer.Exit(1)
        with console.status(f"Fetching news for {ticker}..."):
            bundle = get_ticker_news(ticker, max_items)
        title = f"News: {ticker}"
    else:
        with console.status("Fetching market news..."):
            bundle = get_market_news(max_items)
        title = "Market News"

    if not bundle.articles:
        console.print("[yellow]No recent news found.[/yellow]")
        return

    table = Table(title=f"[bold]{title}[/bold]", show_lines=False)
    table.add_column("Date", style="dim", no_wrap=True)
    table.add_column("Publisher", style="cyan", no_wrap=True)
    table.add_column("Headline")

    for item in bundle.articles:
        date_str = (item.published_at or "")[:10]
        table.add_row(date_str, item.publisher[:22], item.title)

    console.print(table)

    if bundle.sentiment:
        s = bundle.sentiment
        console.print(
            f"[dim]Sentiment: {s.overall.upper()} | "
            f"+{s.positive_count} positive / -{s.negative_count} negative / ~{s.neutral_count} neutral "
            f"(keyword-based, not AI)[/dim]"
        )
    console.print(f"[dim]Fetched: {bundle.fetched_at[:19]}[/dim]")


@app.command()
def institutions(
    ticker: str = typer.Argument(..., help="Stock ticker"),
):
    """
    Show institutional holders, insider ownership %, and analyst recommendations.
    Raw Yahoo Finance data — no AI interpretation.
    """
    ticker = ticker.upper()
    with console.status(f"Validating {ticker}..."):
        v = analyzer.validate_ticker(ticker)
    if not v.valid:
        console.print(f"[red]{v.error}[/red]")
        raise typer.Exit(1)

    with console.status(f"Fetching institutional data for {ticker}..."):
        from fundamentals import get_institutional_data, get_analyst_data
        inst = get_institutional_data(ticker)
        analyst = get_analyst_data(ticker)

    insider_str = f"{inst.pct_insiders*100:.2f}%" if inst.pct_insiders is not None else "N/A"
    inst_str = f"{inst.pct_institutions*100:.2f}%" if inst.pct_institutions is not None else "N/A"
    console.print(Panel(
        f"Insider Ownership: [bold]{insider_str}[/bold]  |  Institutional Ownership: [bold]{inst_str}[/bold]",
        title=f"Ownership Summary — {ticker}",
    ))

    if inst.top_holders:
        holder_table = Table(title="Top Institutional Holders", show_lines=False)
        holder_table.add_column("Holder", style="cyan")
        holder_table.add_column("Shares", justify="right")
        holder_table.add_column("% Outstanding", justify="right")
        holder_table.add_column("Est. Value", justify="right")

        for h in inst.top_holders:
            pct = f"{h.get('pct_held',0)*100:.2f}%" if h.get('pct_held') is not None else "N/A"
            shares = f"{h.get('shares',0):,}" if h.get('shares') else "N/A"
            val = f"${h.get('value',0)/1e9:.1f}B" if h.get('value') else "N/A"
            holder_table.add_row(h.get('holder','?'), shares, pct, val)
        console.print(holder_table)

    if analyst.consensus or analyst.buy_count or analyst.earnings_date:
        console.print(Panel(
            f"Consensus: [bold]{analyst.consensus or 'N/A'}[/bold]  |  "
            f"Strong Buy: {analyst.strong_buy_count}  Buy: {analyst.buy_count}  Hold: {analyst.hold_count}  "
            f"Sell: {analyst.sell_count}  Strong Sell: {analyst.strong_sell_count}\n"
            f"Next Earnings: {analyst.earnings_date or 'N/A'}",
            title="Analyst Summary",
        ))

    console.print(f"[dim]Fetched: {inst.fetched_at[:19]}[/dim]")


@app.command()
def validate(
    ticker: str = typer.Argument(..., help="Ticker symbol to validate"),
):
    """Check if a ticker symbol is valid against Yahoo Finance."""
    v = analyzer.validate_ticker(ticker.upper())
    if v.valid:
        console.print(f"[green]✓ {v.ticker} is valid — {v.name}[/green]")
    else:
        console.print(f"[red]✗ {v.ticker} — {v.error}[/red]")


@app.command()
def cache_stats():
    """Show in-memory cache statistics."""
    import cache as _cache
    stats = _cache.stats()
    console.print(Panel(
        "\n".join(f"  {k}: {v}" for k, v in stats.items()),
        title="Cache Statistics",
    ))


@app.command()
def cache_clear():
    """Clear all in-memory cached data."""
    import cache as _cache
    _cache.clear()
    console.print("[yellow]Cache cleared.[/yellow]")


if __name__ == "__main__":
    app()
