# Stock Portfolio Advisor

A Python application to track your stock portfolio and get AI-powered investment advice using Claude.

## Features

- **Portfolio Management** — add, update, and remove stock positions and cash
- **Live Quotes** — real-time stock prices via `yfinance`
- **Portfolio Analytics** — gain/loss, portfolio weights, cost basis
- **AI Advice** — personalized portfolio analysis powered by Claude (`claude-sonnet-4-6`)
- **REST API** — FastAPI backend with full OpenAPI docs
- **CLI** — interactive command-line interface with rich output

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure Claude API key
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY
```

## CLI Usage

```bash
# Add positions
python cli.py add AAPL 10 175.50
python cli.py add MSFT 5 380.00
python cli.py cash 5000

# View portfolio with live prices
python cli.py show

# Get a live stock quote
python cli.py quote NVDA

# Get AI-powered advice
python cli.py advise --risk moderate
python cli.py advise --question "Should I add more tech exposure?"

# Remove a position
python cli.py remove AAPL

# Reset portfolio
python cli.py reset --yes

# Start the REST API server
python cli.py serve
```

## REST API

Start the server and visit `http://localhost:8000/docs` for interactive API docs.

```bash
python cli.py serve
# or
uvicorn main:app --reload
```

### Key endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/portfolio` | Live portfolio summary |
| POST | `/portfolio/position` | Add/update a position |
| DELETE | `/portfolio/position` | Remove a position |
| POST | `/portfolio/cash` | Set cash balance |
| GET | `/quote/{ticker}` | Live stock quote |
| GET | `/history/{ticker}` | Historical OHLCV data |
| GET | `/advice` | AI portfolio advice |

## Architecture

```
main.py      — FastAPI app and route definitions
cli.py       — Typer CLI interface with Rich output
models.py    — Pydantic data models
portfolio.py — Portfolio persistence (JSON file)
analyzer.py  — Stock data fetching and portfolio analytics
advisor.py   — Claude AI integration for advice
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Required for AI advice feature |
