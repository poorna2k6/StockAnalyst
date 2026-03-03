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

app = typer.Typer(help="Stock Portfolio Advisor - track and analyze your investments.")
console = Console()


def _gain_loss_color(value: float) -> str:
    return "green" if value >= 0 else "red"


@app.command()
def show():
    """Show current portfolio summary."""
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
        table.add_row("CASH", "", "", "", f"${summary.cash:,.2f}", "", f"{summary.cash / summary.total_value * 100:.1f}%")

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
    console.print(f"[yellow]Portfolio reset.[/yellow]")


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
    question: Optional[str] = typer.Option(None, "--question", "-q", help="Specific question to ask"),
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


if __name__ == "__main__":
    app()
