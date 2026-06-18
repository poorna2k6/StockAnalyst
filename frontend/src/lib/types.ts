export interface Quote {
  ticker: string
  price: number
  change: number
  change_pct: number
  volume: number
  market_cap?: number
  week_52_low?: number
  week_52_high?: number
}

export interface PositionSummary {
  ticker: string
  shares: number
  avg_cost: number
  current_price: number
  current_value: number
  gain_loss: number
  gain_loss_pct: number
  weight: number
}

export interface PortfolioSummary {
  name: string
  total_value: number
  total_cost: number
  total_gain_loss: number
  total_gain_loss_pct: number
  cash: number
  positions: PositionSummary[]
}

export interface NewsItem {
  title: string
  url: string
  publisher: string
  published_at: string
  summary?: string
}

export interface NewsBundle {
  ticker?: string
  articles: NewsItem[]
  fetched_at: string
}

export interface DayPick {
  ticker: string
  price?: number
  momentum_1d?: number
  momentum_5d?: number
  volume_ratio?: number
  rsi_14?: number
  news_count: number
  composite_score: number
  reasoning: string[]
}

export interface LongTermPick {
  ticker: string
  sector?: string
  roe?: number
  debt_to_equity?: number
  profit_margin?: number
  composite_score: number
  reasoning: string[]
}

export interface ScreenerResult {
  screener_type: string
  picks: (DayPick | LongTermPick)[]
  ai_narrative?: string
  universe_size: number
  fetched_at: string
}

export interface AgentCouncilResult {
  ticker: string
  name?: string
  bull: string
  bear: string
  risk: string
  verdict: string
  fetched_at: string
}

export interface StockSignal {
  ticker: string
  name?: string
  signal_type: 'momentum_burst' | 'news_catalyst' | 'oversold_bounce' | 'sector_rotation'
  lean: 'bullish' | 'bearish' | 'neutral'
  confidence: 'high' | 'medium' | 'low'
  ai_rationale: string
  momentum_1d?: number
  rsi_14?: number
  volume_ratio?: number
  current_price?: number
  change_pct?: number
}

export interface SignalScanResult {
  signals: StockSignal[]
  market_summary: string
  scan_basis: string
  fetched_at: string
  disclaimer: string
}

export interface TaggedNewsItem {
  title: string
  url: string
  publisher: string
  published_at?: string
  tickers: string[]
  sentiment: 'bullish' | 'bearish' | 'neutral'
  sentiment_score: number
}

export interface TaggedNewsBundle {
  articles: TaggedNewsItem[]
  fetched_at: string
  overall_sentiment: 'bullish' | 'bearish' | 'neutral'
}

export interface UserSettings {
  user_id: string
  preferred_model: string
  use_byok: boolean
  has_claude_key: boolean
  has_gemini_key: boolean
  credit_balance: number
}

export interface UsageSummary {
  total_calls: number
  total_tokens: number
  total_cost_usd: number
  by_feature: Record<string, { calls: number; tokens: number; cost_usd: number }>
}
