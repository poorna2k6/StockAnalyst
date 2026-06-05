# My Stock Analyst

A mobile-first, single-file web app for beginner investors — AI-powered stock analysis, portfolio tracking, price charts, watchlist alerts, and market intelligence. Runs entirely in the browser with **no backend, no build step, and no server required**.

**Live demo:** deploy `docs/index.html` to any static host (GitHub Pages, Netlify, Vercel, etc.)

> ⚠️ **Educational tool only. Not financial advice.** All AI outputs are estimates. Always do your own research and consult a licensed financial advisor before investing real money.

---

## Features

### 📰 Market Brief (Tab 1)
- **AI Market Intelligence** — daily briefing powered by Claude or Gemini; summarizes market mood, top movers, and key signals
- **Market Pulse** — live SPY / QQQ / DIA / IWM quotes with Bull/Bear/Flat mood indicator based on real-time index moves
- **Sector spread** — QQQ vs IWM divergence signals risk appetite
- **Today's Top Picks** — 9 curated stocks with 52-week range bar, "Near High / Near Low" pills, and watchlist stars
- **📈 1-Year Price Chart** — tap the chart icon on any stock to view a 1-year weekly SVG line chart with 52W range, gradient fill, and 1Y % return
- **Quick Search** — type any ticker to instantly launch an AI analysis in the Analyst tab
- **Market Countdown** — header shows live countdown to market open / close (America/New_York, NYSE holiday-aware through 2027)
- **Beginner's Corner** — plain-English tip cards: what is a stock, ETF vs stock, the golden rule, etc.

### 💡 Investment Planner (Tab 2)
- Enter a budget, risk level (Beginner / Moderate / Aggressive), and time horizon (Short / Medium / Long)
- AI builds a full personalised plan: allocations (always normalised to 100%), entry prices, profit targets, stop-losses, and a 90-day action plan
- Falls back to a rule-based plan when no API key is present (always gives output)
- Sector diversification caps applied for beginner/moderate profiles (max 2–3 picks per sector)

### 🤖 AI Analyst Chat (Tab 3)
- Streaming chat powered by Claude (`claude-sonnet-4-6`) or Google Gemini (`gemini-2.5-flash`)
- Fetches live price, fundamentals (P/E, forward P/E, margins, ROE, FCF, beta, analyst targets, recommendation), and recent news per ticker
- Structured analysis format: Snapshot → Numbers → Price Context → Bull/Bear Case → Verdict → Entry Strategy
- Quick-ask pills: NVDA, AAPL, TSLA, ETF Pick, Side Income
- **Copy button** on every response
- Inline watchlist star buttons injected after each AI answer
- Chat history: last 20 messages retained in session

### 💼 Portfolio Tracker (Tab 4)
- Add positions: ticker, number of shares, average cost basis
- **Screenshot import** — paste a brokerage screenshot (Robinhood, Fidelity, Webull, Schwab, Stash, Acorns); Gemini vision reads the holdings automatically
- Live P&L, today's return (Robinhood-style green/red), total portfolio value
- **Fundamental score badge** (1–10) on each holding, derived from P/E, margins, ROE, FCF yield, beta, debt/equity, and analyst consensus
- **📈 1-Year chart** on every holding — chart icon in each holding card
- **Allocation Chart** — horizontal stacked bar chart showing each position as % of total value
- **Sector Breakdown** — aggregated exposure across Tech, Finance, Healthcare, Energy, Consumer, etc.
- **CSV Export** — one-tap download as `portfolio-YYYY-MM-DD.csv`
- **AI Portfolio Analysis** — full AI review of all positions with hold/add/reduce verdicts, weighted portfolio P/E, beta, sector concentration warnings
- Auto-refresh every 5 minutes; "Updated X ago" timestamps

### 👁 Watchlist (Tab 5)
- Star any stock from Brief, Analyst, or chat responses
- Live price, daily change %, 52-week range bar
- **📈 1-Year chart** on every watchlist item
- **Price Alerts** — tap 🔔 to set "above $X" or "below $X" alert; fires a toast when triggered on next refresh
- Refresh All button

### 💰 Earn Tab (Tab 6)
- AI-generated income strategy: Dividend, Swing Trading, Options (covered calls / cash-secured puts), Growth, Momentum
- Portfolio-aware — suggests actions on stocks you already own
- Static education cards: Covered Calls, Swing Trading, Cash-Secured Puts, T-Bills

### ⚙️ Settings
- AI provider selector: Auto / Claude (Anthropic) / Gemini (Google)
- API key entry — keys stored in `sessionStorage` only (cleared when the browser tab closes; never written to `localStorage`)
- Your name for personalised greetings
- Feature highlights grid
- Build version indicator

### UX / Infrastructure
- **Dark Mode** — full dark theme, persisted to `localStorage`
- **PWA** — installable to home screen on iOS and Android; icons generated via canvas (no static PNG files needed)
- Mobile-first responsive layout (Tailwind CSS Play CDN)
- Dual CORS proxy fallback for Yahoo Finance data (`corsproxy.io` → `api.allorigins.win`)
- Toast notifications, metric tooltip popovers, smooth animations
- ESC key and backdrop tap close any modal
- Multi-tab sync via `storage` event
- Service Worker for offline support

---

## Quick Start

```
# No installation required
open docs/index.html
```

1. Open `docs/index.html` in any modern browser (no server needed)
2. Tap the **⚙ gear** icon → enter a free Claude or Gemini API key
3. Browse the **Brief** tab for today's market snapshot
4. Tap 📈 on any stock to view the 1-year price chart
5. Use the **Analyst** tab to chat about any stock

### API Keys (both free tiers available)

| Provider | Where to get it | Format |
|----------|----------------|--------|
| Claude (Anthropic) | [console.anthropic.com](https://console.anthropic.com) | `sk-ant-api03-…` |
| Gemini (Google) | [aistudio.google.com](https://aistudio.google.com) | `AIza…` |

You can use either or both. When both are set, the app defaults to Claude (configurable in Settings).

The AI features require an API key. All other features (portfolio tracking, watchlist, price data, charts) work without one.

---

## Deployment

### GitHub Pages (recommended)
1. Fork this repo
2. Go to **Settings → Pages → Source: Deploy from branch → `/docs`**
3. Your app will be live at `https://<username>.github.io/<repo>/`

### Netlify / Vercel
Drag and drop the `docs/` folder, or point the deploy directory to `docs/`.

### Self-hosted
Copy `docs/index.html`, `docs/manifest.json`, and `docs/sw.js` to any static file server.

---

## Security Notes

- **API keys** are stored in `sessionStorage` (cleared when the tab closes). They are never sent to any server other than the official Anthropic and Google APIs.
- **Content Security Policy** is set via a `<meta>` tag. The `connect-src` directive restricts which hosts JavaScript can contact, limiting data exfiltration even if XSS were exploited.
- All user-supplied data (tickers, names) is HTML-escaped via `esc()` before insertion into the DOM.
- Error messages are escaped before display; never rendered as raw HTML.
- Gemini API key is sent via `Authorization: Bearer` header — not as a URL query parameter.
- Market data is fetched through Yahoo Finance. Two fallback CORS proxies (`corsproxy.io`, `api.allorigins.win`) are used when direct fetch is blocked. These are third-party services; they may log request URLs.

---

## Architecture

### Web App (single file)

```
docs/
├── index.html     — complete web app (~3000 lines, no build step)
├── manifest.json  — PWA manifest
└── sw.js          — service worker (offline caching)
```

**Key sections inside `index.html`:**

| Section | Description |
|---------|-------------|
| `<head>` | CSP meta tag, PWA meta tags, Tailwind CDN, canvas icon generation |
| HTML tabs | 6 tab panels (Brief, Invest, Analyst, Portfolio, Watchlist, Earn) + 4 modals |
| Utilities | `esc()`, `fmt()`, `fmtN()`, `toast()`, `openModal()`, `closeModal()` |
| Storage | `savePortfolio()`, `saveWatchlist()`, `saveAlerts()` — all use `localStorage` except API keys |
| Data fetching | `tryFetch()` with 3-proxy fallback, `fetchQuote()`, `fetchFundamentals()`, `fetchNews()` |
| Charts | `showChart()` — 1Y weekly SVG line chart from Yahoo Finance v8 chart API |
| AI / streaming | `streamAI()`, `getActiveAI()`, `sendChat()`, `analyzePortfolio()`, `loadAIBrief()` |
| Portfolio | `renderPortfolio()`, `addPosition()`, `removePosition()`, `scorePosition()` |
| Watchlist | `renderWatchlist()`, `toggleWatchlist()`, `checkAllAlerts()` |
| Settings | `openSettings()`, `saveSettings()`, `closeSettings()` |
| PWA | `ServiceWorker` registration, Web Push stub |

### Python Backend (optional)

A FastAPI + Typer CLI backend is also included for programmatic portfolio management.

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

#### Key API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/portfolio` | Live portfolio summary |
| POST | `/portfolio/position` | Add or update a position |
| DELETE | `/portfolio/position` | Remove a position |
| GET | `/quote/{ticker}` | Live stock quote |
| GET | `/advice` | AI portfolio advice |

#### Python module layout

```
main.py       — FastAPI app and routes
cli.py        — Typer CLI with Rich output
models.py     — Pydantic data models
portfolio.py  — JSON file persistence
analyzer.py   — yfinance data fetching and analytics
advisor.py    — Claude AI integration
```

---

## Environment Variables (Python backend only)

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Required for AI advice via CLI/API |

---

## Changelog

### v2.8 — 2026-03-10
- **NEW: 1-Year Price Chart** — tap 📈 on any stock in Brief top picks, Watchlist, or Portfolio to view an interactive 1-year weekly SVG chart with gradient fill, 52W range, and 1Y % return
- **SECURITY: API keys moved to sessionStorage** — keys are cleared when the browser tab closes; migrated automatically from localStorage on first load
- **SECURITY: Content Security Policy meta tag** — restricts `connect-src` to approved hosts; blocks `object-src` entirely
- **SECURITY: Gemini key in Authorization header** — previously the Gemini API key was sent as a `?key=` URL query parameter (logged in browser history); now sent as `Authorization: Bearer` header
- **SECURITY: XSS fix — watchlist onclick** — ticker symbol in watchlist row onclick attribute was not HTML-escaped
- **LEGAL: Prominent disclaimers** — amber warning banners added to Investment Planner and Portfolio AI Analysis, not just buried in Settings
- **BUG: Investment planner weight normalization** — when fewer than 5 picks are returned, weights now sum to 100% (previously left up to 20% unallocated)

### v2.7 — 2026-03-10
- **SECURITY: XSS fixes** — escaped ticker symbols in Brief top-picks onclick handlers; escaped `err.message` before innerHTML insertion
- **SECURITY: Gemini API key** — moved from URL to Authorization header (streaming endpoint)
- **AI: Daily Brief token budget** raised from 250 → 400 to prevent mid-sentence truncation
- **AI: console.warn removed** — AI OCR response was being logged to browser DevTools
- **UX: analyzePortfolio() network failure** — fetchQuote/fetchFundamentals now wrapped in try-catch; Analyze button correctly re-enables on all error paths
- **UX: watchlist Promise.all** — added `.catch()` handler so watchlist renders even if some quote fetches fail
- **BUG: Investment planner weight normalization** — initial fix for <5 picks

### v2.6 and earlier
- Core portfolio tracking, AI chat, watchlist with price alerts, investment planner, screenshot import, dark mode, PWA, Earn tab, sector scoring

---

## Browser Compatibility

| Browser | Support |
|---------|---------|
| Chrome 80+ | ✅ Full |
| Firefox 75+ | ✅ Full |
| Safari 14+ (iOS 14+) | ✅ Full |
| Edge 80+ | ✅ Full |
| Internet Explorer | ❌ Not supported (ES2020 template literals required) |

---

## Disclaimer

This app is for **educational and informational purposes only**. It is **not financial advice**. The AI-generated analysis, stock picks, price targets, and recommendations are computer-generated estimates based on publicly available data and may be inaccurate, incomplete, or out of date.

**Never invest money based solely on AI output.** Always conduct your own research and consult a qualified, licensed financial advisor before making investment decisions. Past performance is not indicative of future results.
