import { supabase } from './supabase'
import type {
  Quote, PortfolioSummary, NewsBundle,
  ScreenerResult, AgentCouncilResult, UserSettings, UsageSummary,
} from './types'

const API_URL = (import.meta.env.VITE_API_URL as string | undefined) || 'http://localhost:8000'

async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  let token: string | undefined
  if (supabase) {
    const { data } = await supabase.auth.getSession()
    token = data.session?.access_token
  }
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  })
  return res
}

export async function getQuote(ticker: string): Promise<Quote> {
  const res = await apiFetch(`/quote/${ticker}`)
  if (!res.ok) throw new Error(`Quote fetch failed for ${ticker}`)
  return res.json()
}

export async function getPortfolio(): Promise<PortfolioSummary> {
  const res = await apiFetch('/portfolio')
  if (!res.ok) throw new Error('Failed to fetch portfolio')
  return res.json()
}

export async function addPosition(ticker: string, shares: number, avg_cost: number): Promise<PortfolioSummary> {
  const res = await apiFetch('/portfolio/position', {
    method: 'POST',
    body: JSON.stringify({ ticker, shares, avg_cost }),
  })
  if (!res.ok) throw new Error('Failed to add position')
  return res.json()
}

export async function removePosition(ticker: string): Promise<PortfolioSummary> {
  const res = await apiFetch('/portfolio/position', {
    method: 'DELETE',
    body: JSON.stringify({ ticker }),
  })
  if (!res.ok) throw new Error('Failed to remove position')
  return res.json()
}

export async function setCash(amount: number): Promise<void> {
  const res = await apiFetch(`/portfolio/cash?amount=${amount}`, { method: 'POST' })
  if (!res.ok) throw new Error('Failed to set cash')
}

export async function resetPortfolio(): Promise<void> {
  const res = await apiFetch('/portfolio/reset', { method: 'POST' })
  if (!res.ok) throw new Error('Failed to reset portfolio')
}

export async function getWatchlist(): Promise<Array<{ ticker: string; added_at: string; quote?: Quote }>> {
  const res = await apiFetch('/watchlist')
  if (!res.ok) throw new Error('Failed to fetch watchlist')
  return res.json()
}

export async function addToWatchlist(ticker: string): Promise<void> {
  const res = await apiFetch(`/watchlist/${ticker}`, { method: 'POST' })
  if (!res.ok) throw new Error('Failed to add to watchlist')
}

export async function removeFromWatchlist(ticker: string): Promise<void> {
  const res = await apiFetch(`/watchlist/${ticker}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to remove from watchlist')
}

export async function getMarketNews(): Promise<NewsBundle> {
  const res = await apiFetch('/news')
  if (!res.ok) throw new Error('Failed to fetch news')
  return res.json()
}

export async function getScreenerBestDay(topN = 8): Promise<ScreenerResult> {
  const res = await apiFetch(`/screener/best-day?top_n=${topN}`)
  if (!res.ok) throw new Error('Screener failed')
  return res.json()
}

export async function getScreenerLongTerm(topN = 6): Promise<ScreenerResult> {
  const res = await apiFetch(`/screener/long-term?top_n=${topN}`)
  if (!res.ok) throw new Error('Screener failed')
  return res.json()
}

export async function sendChat(
  message: string,
  sessionId = 'main',
): Promise<{ response: string; tickers_fetched: string[] }> {
  const res = await apiFetch('/chat', {
    method: 'POST',
    body: JSON.stringify({ message, session_id: sessionId }),
  })
  if (!res.ok) throw new Error('Chat failed')
  return res.json()
}

export async function getChatHistory(sessionId = 'main') {
  const res = await apiFetch(`/chat/history?session_id=${sessionId}`)
  if (!res.ok) return []
  return res.json()
}

export async function getAgentCouncil(ticker: string): Promise<AgentCouncilResult> {
  const res = await apiFetch(`/council/${ticker}`, { method: 'POST' })
  if (!res.ok) throw new Error(`Council failed for ${ticker}`)
  return res.json()
}

export async function getSettings(): Promise<UserSettings> {
  const res = await apiFetch('/settings')
  if (!res.ok) throw new Error('Failed to fetch settings')
  return res.json()
}

export async function updateSettings(
  updates: Partial<UserSettings & { byok_claude_key?: string; byok_gemini_key?: string }>,
): Promise<UserSettings> {
  const res = await apiFetch('/settings', {
    method: 'PUT',
    body: JSON.stringify(updates),
  })
  if (!res.ok) throw new Error('Failed to update settings')
  return res.json()
}

export async function getUsage(): Promise<UsageSummary> {
  const res = await apiFetch('/usage')
  if (!res.ok) throw new Error('Failed to fetch usage')
  return res.json()
}
