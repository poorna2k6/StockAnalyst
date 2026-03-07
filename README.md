# My Stock Analyst

A mobile-first web app for beginner investors — AI-powered stock analysis, portfolio tracking, and market intelligence. Runs entirely in the browser with no backend required.

**Live:** deploy `docs/index.html` to any static host (GitHub Pages, Netlify, etc.)

---

## Web App Features

### Market Brief
- **AI Market Intelligence** — daily 3-sentence brief powered by Claude or Gemini
- **Market Pulse** — SPY / QQQ / DIA / IWM live quotes with mood indicator (Bull/Bear/Flat)
- **Market Indexes** — live index quotes with % change pills
- **Today's Top Picks** — trending stocks with 52-week range bar and watchlist stars
- **Quick Search** — type any ticker in the search bar to instantly get AI analysis
- **Market Countdown** — header shows live countdown to market open/close (America/New_York)
- **Beginners Corner** — plain-English explainers on stocks, ETFs, and the golden rule

### AI Analyst Chat
- Streaming chat powered by Claude (`claude-sonnet-4-6`) or Google Gemini
- Fetches real-time price, fundamentals (P/E, margins, ROE, FCF, analyst targets), and news per ticker
- Structured analysis: Snapshot → Numbers → Price Context → Bull/Bear Case → Verdict → Entry Strategy
- Quick-ask pills: NVDA, AAPL, TSLA, ETF Pick, Side Income
- **Copy button** — copy any AI response to clipboard
- Watchlist star buttons injected after each response

### Investment Planner
- Budget + risk level (Beginner / Moderate / Aggressive) + horizon (Short / Medium / Long)
- AI builds a full plan: allocations, entry prices, profit targets, stop-losses, 90-day action plan
- Falls back to a rule-based plan when no API key is set

### Portfolio Tracker
- Add positions manually (ticker, shares, avg cost)
- **Screenshot import** — paste brokerage app screenshots (Robinhood, Fidelity, Stash, Acorns, Webull, Schwab); AI reads holdings via vision
- Live P&L, today's return (Robinhood-style), total value
- **Allocation Chart** — horizontal bar chart showing each position's % of total value
- **Sector Breakdown** — aggregated sector exposure (Tech, Finance, Healthcare, Energy, etc.)
- **CSV Export** — download portfolio as `portfolio-YYYY-MM-DD.csv`
- **AI Portfolio Analysis** — full AI review of all positions with hold/add/reduce recommendations
- Auto-refresh every 5 minutes when stale; "Updated X ago" timestamps

### Watchlist
- Star any stock from Brief, Analyst, or chat responses
- Shows live price, daily change, 52-week range bar
- **Price Alerts** — tap 🔔 on any watchlist item to set "above $X" or "below $X" alerts; fires a toast notification when triggered on next price refresh
- Refresh All button

### Earn Tab
- AI-generated income plans: Dividend, Swing Trading, Options (covered calls / CSPs), Growth, Momentum
- Aware of your current holdings — suggests actions on stocks you already own
- Static education cards: Covered Calls, Swing Trading, Cash-Secured Puts, T-Bills

### Settings
- AI provider: Auto / Claude (Anthropic) / Gemini (Google)
- API key storage (localStorage only — never leaves your browser)
- Your name for personalised greetings
- **Feature Highlights** — grid of all active features
- **Build version** — shows `v2.3 · YYYY-MM-DD` so you can confirm the latest code is deployed

### UX / Infrastructure
- **Dark Mode** — full dark theme, saved to `localStorage`
- **PWA** — installable to home screen (iOS + Android); canvas-generated icons
- Mobile-first responsive layout (Tailwind CSS)
- Dual CORS proxy fallback for Yahoo Finance data
- Toast notifications, metric tooltips, smooth animations

---

## Quick Start

1. Open `docs/index.html` in a browser — no server needed
2. Tap the **⚙ gear** icon → add a free Claude or Gemini API key
3. Browse the Brief tab for today's market snapshot
4. Use the Analyst tab to ask about any stock

### API Keys (both free tiers available)
| Provider | Where to get it | Format |
|----------|----------------|--------|
| Claude (Anthropic) | [console.anthropic.com](https://console.anthropic.com) | `sk-ant-api03-…` |
| Gemini (Google) | [aistudio.google.com](https://aistudio.google.com) | `AIza…` |

---

## Python Backend (optional)

A FastAPI + CLI backend is also included for programmatic portfolio management.

```bash
pip install -r requirements.txt
cp .env.example .env   # set ANTHROPIC_API_KEY

# CLI
python cli.py add AAPL 10 175.50
python cli.py show
python cli.py advise --risk moderate

# REST API  →  http://localhost:8000/docs
python cli.py serve
```

### Key API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/portfolio` | Live portfolio summary |
| POST | `/portfolio/position` | Add/update a position |
| DELETE | `/portfolio/position` | Remove a position |
| GET | `/quote/{ticker}` | Live stock quote |
| GET | `/advice` | AI portfolio advice |

### Architecture

```
docs/index.html  — full web app (single file, no build step)
main.py          — FastAPI app and routes
cli.py           — Typer CLI with Rich output
models.py        — Pydantic data models
portfolio.py     — JSON persistence
analyzer.py      — yfinance data fetching + analytics
advisor.py       — Claude AI integration
```

---

## Environment Variables (Python backend only)

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Required for AI advice via CLI/API |

> **Disclaimer:** Educational tool only. Not financial advice. Always do your own research.
