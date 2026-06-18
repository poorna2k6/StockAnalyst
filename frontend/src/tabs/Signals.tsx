import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Zap, TrendingUp, TrendingDown, Minus, RefreshCw,
  ExternalLink, Radio, ChevronRight, AlertCircle,
} from 'lucide-react'
import { getSignals, getTaggedNews } from '../lib/api'
import type { SignalScanResult, StockSignal, TaggedNewsBundle } from '../lib/types'

// ── Helpers ──────────────────────────────────────────────────────────────────

const SIGNAL_LABELS: Record<string, string> = {
  momentum_burst:   'Momentum Burst',
  news_catalyst:    'News Catalyst',
  oversold_bounce:  'Oversold Bounce',
  sector_rotation:  'Sector Rotation',
}

const CONFIDENCE_COLORS: Record<string, string> = {
  high:   'text-emerald-400 bg-emerald-400/10 border-emerald-400/20',
  medium: 'text-amber-400  bg-amber-400/10  border-amber-400/20',
  low:    'text-slate-400  bg-slate-400/10  border-slate-400/20',
}

const LEAN_ICONS = {
  bullish: <TrendingUp  size={14} className="text-emerald-400" />,
  bearish: <TrendingDown size={14} className="text-red-400" />,
  neutral: <Minus       size={14} className="text-slate-400" />,
}

const LEAN_RING: Record<string, string> = {
  bullish: 'border-l-emerald-500',
  bearish: 'border-l-red-500',
  neutral: 'border-l-slate-500',
}

const SENTIMENT_COLORS: Record<string, string> = {
  bullish: 'text-emerald-400',
  bearish: 'text-red-400',
  neutral: 'text-slate-400',
}

function fmt(n?: number | null, decimals = 1): string {
  if (n == null) return 'N/A'
  return n.toFixed(decimals)
}

function fmtAge(iso?: string | null): string {
  if (!iso) return ''
  const diff = (Date.now() - new Date(iso).getTime()) / 60000
  if (diff < 1)  return 'just now'
  if (diff < 60) return `${Math.floor(diff)}m ago`
  return `${Math.floor(diff / 60)}h ago`
}

// ── Signal card ───────────────────────────────────────────────────────────────

function SignalCard({ signal, index }: { signal: StockSignal; index: number }) {
  const lean = signal.lean as 'bullish' | 'bearish' | 'neutral'
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.07 }}
      className={`bg-card border border-white/5 border-l-2 ${LEAN_RING[lean]} rounded-xl p-4 hover:bg-white/5 transition-colors`}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          {LEAN_ICONS[lean]}
          <span className="text-white font-bold text-lg">{signal.ticker}</span>
          {signal.name && (
            <span className="text-slate-500 text-xs truncate max-w-[140px]">{signal.name}</span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${CONFIDENCE_COLORS[signal.confidence]}`}>
            {signal.confidence.toUpperCase()}
          </span>
          <span className="text-[10px] text-slate-500 bg-white/5 px-2 py-0.5 rounded-full">
            {SIGNAL_LABELS[signal.signal_type] ?? signal.signal_type}
          </span>
        </div>
      </div>

      {/* Stats row */}
      <div className="flex flex-wrap gap-3 mb-3 text-xs text-slate-400">
        {signal.current_price != null && (
          <span>${fmt(signal.current_price, 2)}
            {signal.change_pct != null && (
              <span className={signal.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                {' '}{signal.change_pct >= 0 ? '+' : ''}{fmt(signal.change_pct)}%
              </span>
            )}
          </span>
        )}
        {signal.momentum_1d != null && (
          <span className={signal.momentum_1d >= 0 ? 'text-emerald-400' : 'text-red-400'}>
            1d {signal.momentum_1d >= 0 ? '+' : ''}{fmt(signal.momentum_1d)}%
          </span>
        )}
        {signal.rsi_14 != null && (
          <span>RSI {fmt(signal.rsi_14, 0)}</span>
        )}
        {signal.volume_ratio != null && (
          <span>Vol {fmt(signal.volume_ratio)}x avg</span>
        )}
      </div>

      {/* AI rationale */}
      <p className="text-slate-300 text-sm leading-relaxed">{signal.ai_rationale}</p>
    </motion.div>
  )
}

// ── News feed ─────────────────────────────────────────────────────────────────

function NewsFeed({ bundle }: { bundle: TaggedNewsBundle }) {
  return (
    <div className="space-y-1">
      {bundle.articles.slice(0, 15).map((item, i) => (
        <a
          key={i}
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-start gap-3 px-3 py-2.5 rounded-lg hover:bg-white/5 transition-colors group"
        >
          <span className={`mt-0.5 text-[10px] font-bold w-14 shrink-0 ${SENTIMENT_COLORS[item.sentiment]}`}>
            {item.sentiment === 'bullish' ? '▲ BULL' : item.sentiment === 'bearish' ? '▼ BEAR' : '— NEUT'}
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-slate-300 text-xs leading-snug group-hover:text-white transition-colors line-clamp-2">
              {item.title}
            </p>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-slate-600 text-[10px]">{item.publisher}</span>
              {item.published_at && (
                <span className="text-slate-600 text-[10px]">{fmtAge(item.published_at)}</span>
              )}
              {item.tickers.length > 0 && (
                <div className="flex gap-1">
                  {item.tickers.slice(0, 3).map(t => (
                    <span key={t} className="text-[10px] text-blue-400 bg-blue-400/10 px-1.5 py-0.5 rounded">
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
          <ExternalLink size={11} className="text-slate-600 group-hover:text-slate-400 shrink-0 mt-0.5" />
        </a>
      ))}
    </div>
  )
}

// ── Sentiment bar ─────────────────────────────────────────────────────────────

function SentimentBar({ bundle }: { bundle: TaggedNewsBundle }) {
  const pos = bundle.articles.filter(a => a.sentiment === 'bullish').length
  const neg = bundle.articles.filter(a => a.sentiment === 'bearish').length
  const total = bundle.articles.length || 1
  const posPct = Math.round((pos / total) * 100)
  const negPct = Math.round((neg / total) * 100)
  const neuPct = 100 - posPct - negPct

  const moodLabel = bundle.overall_sentiment === 'bullish'
    ? 'Cautiously Bullish' : bundle.overall_sentiment === 'bearish'
    ? 'Risk-Off' : 'Mixed'

  return (
    <div className="bg-card border border-white/5 rounded-xl px-4 py-3 flex items-center gap-4">
      <div className="flex-1">
        <div className="flex justify-between text-[10px] text-slate-500 mb-1">
          <span>Market Mood: <span className={`font-semibold ${SENTIMENT_COLORS[bundle.overall_sentiment]}`}>{moodLabel}</span></span>
          <span>{bundle.articles.length} articles</span>
        </div>
        <div className="flex h-1.5 rounded-full overflow-hidden gap-px">
          <div className="bg-emerald-500 transition-all" style={{ width: `${posPct}%` }} />
          <div className="bg-slate-600 transition-all" style={{ width: `${neuPct}%` }} />
          <div className="bg-red-500 transition-all"  style={{ width: `${negPct}%` }} />
        </div>
        <div className="flex gap-3 mt-1 text-[10px] text-slate-500">
          <span className="text-emerald-400">{posPct}% bullish</span>
          <span>{neuPct}% neutral</span>
          <span className="text-red-400">{negPct}% bearish</span>
        </div>
      </div>
    </div>
  )
}

// ── Main tab ──────────────────────────────────────────────────────────────────

export default function Signals() {
  const [scanResult, setScanResult]     = useState<SignalScanResult | null>(null)
  const [newsBundle, setNewsBundle]     = useState<TaggedNewsBundle | null>(null)
  const [scanLoading, setScanLoading]   = useState(true)
  const [newsLoading, setNewsLoading]   = useState(true)
  const [scanErr, setScanErr]           = useState<string | null>(null)
  const [newsErr, setNewsErr]           = useState<string | null>(null)
  const [lastRefresh, setLastRefresh]   = useState<Date>(new Date())
  const [refreshing, setRefreshing]     = useState(false)

  const loadAll = useCallback(async (showSpinner = false) => {
    if (showSpinner) setRefreshing(true)
    setScanErr(null)
    setNewsErr(null)

    await Promise.allSettled([
      getSignals()
        .then(r => { setScanResult(r); setScanLoading(false) })
        .catch(e => { setScanErr(e.message); setScanLoading(false) }),
      getTaggedNews(20)
        .then(r => { setNewsBundle(r); setNewsLoading(false) })
        .catch(e => { setNewsErr(e.message); setNewsLoading(false) }),
    ])

    setLastRefresh(new Date())
    if (showSpinner) setRefreshing(false)
  }, [])

  // Initial load
  useEffect(() => { loadAll() }, [loadAll])

  // Auto-refresh every 5 minutes
  useEffect(() => {
    const id = setInterval(() => loadAll(), 5 * 60 * 1000)
    return () => clearInterval(id)
  }, [loadAll])

  const ageMin = Math.floor((Date.now() - lastRefresh.getTime()) / 60000)

  return (
    <div className="p-6 max-w-5xl mx-auto pb-24 md:pb-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Radio size={18} className="text-blue-400" />
          <h1 className="text-xl font-bold text-white">Signals</h1>
          <span className="text-[10px] text-slate-500 bg-white/5 px-2 py-0.5 rounded-full ml-1">
            {ageMin < 1 ? 'live' : `${ageMin}m ago`}
          </span>
        </div>
        <button
          onClick={() => loadAll(true)}
          disabled={refreshing}
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors disabled:opacity-50"
        >
          <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Disclaimer banner */}
      <div className="flex items-start gap-2 bg-amber-500/5 border border-amber-500/20 rounded-xl px-4 py-3 mb-6">
        <AlertCircle size={14} className="text-amber-400 mt-0.5 shrink-0" />
        <p className="text-[11px] text-amber-200/70 leading-snug">
          Signal analysis identifies technical and news setups — it does <strong>not</strong> predict prices.
          Educational only. Not investment advice.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

        {/* Left: AI signals */}
        <div className="lg:col-span-3 space-y-4">
          <div className="flex items-center gap-2 mb-1">
            <Zap size={14} className="text-yellow-400" />
            <h2 className="text-sm font-semibold text-white">Top Setups Now</h2>
          </div>

          {/* Market summary */}
          {scanResult?.market_summary && (
            <div className="bg-white/5 rounded-lg px-4 py-3 text-sm text-slate-300 italic border border-white/5">
              {scanResult.market_summary}
            </div>
          )}

          {/* Loading skeleton */}
          {scanLoading && (
            <div className="space-y-3">
              {[1,2,3].map(i => (
                <div key={i} className="animate-pulse bg-white/5 rounded-xl h-28" />
              ))}
            </div>
          )}

          {/* Error */}
          {scanErr && !scanLoading && (
            <div className="text-slate-500 text-sm bg-white/5 rounded-xl p-4 text-center">
              Signal scan unavailable — {scanErr}
            </div>
          )}

          {/* Signals */}
          <AnimatePresence>
            {scanResult && !scanLoading && (
              scanResult.signals.length > 0 ? (
                <div className="space-y-3">
                  {scanResult.signals.map((s, i) => (
                    <SignalCard key={s.ticker} signal={s} index={i} />
                  ))}
                  <p className="text-[10px] text-slate-600 text-center pt-1">
                    {scanResult.scan_basis} · refreshes every 5 min
                  </p>
                </div>
              ) : (
                <div className="text-slate-500 text-sm bg-white/5 rounded-xl p-6 text-center">
                  No strong setups detected in the current scan.
                </div>
              )
            )}
          </AnimatePresence>
        </div>

        {/* Right: live news */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center gap-2 mb-1">
            <ChevronRight size={14} className="text-slate-400" />
            <h2 className="text-sm font-semibold text-white">Live News</h2>
          </div>

          {newsBundle && <SentimentBar bundle={newsBundle} />}

          <div className="bg-card border border-white/5 rounded-xl py-2">
            {newsLoading && (
              <div className="space-y-2 px-3 py-2">
                {[1,2,3,4,5].map(i => (
                  <div key={i} className="animate-pulse bg-white/5 rounded h-8" />
                ))}
              </div>
            )}
            {newsErr && !newsLoading && (
              <p className="text-slate-500 text-xs text-center p-4">News unavailable</p>
            )}
            {newsBundle && !newsLoading && <NewsFeed bundle={newsBundle} />}
          </div>
        </div>

      </div>
    </div>
  )
}
