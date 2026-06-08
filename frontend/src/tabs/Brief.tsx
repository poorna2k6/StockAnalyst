import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Newspaper, TrendingUp, BarChart2, ExternalLink } from 'lucide-react'
import { getQuote, getScreenerBestDay, getScreenerLongTerm, getMarketNews } from '../lib/api'
import type { Quote, ScreenerResult, NewsBundle, DayPick, LongTermPick } from '../lib/types'
import { PriceChip } from '../components/PriceChip'

const INDICES = ['SPY', 'QQQ', 'DIA', 'IWM']

function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-white/5 ${className}`} />
}

function IndexBar() {
  const [quotes, setQuotes] = useState<Record<string, Quote>>({})

  useEffect(() => {
    INDICES.forEach(t => getQuote(t).then(q => setQuotes(prev => ({ ...prev, [t]: q }))).catch(() => {}))
  }, [])

  return (
    <div className="flex flex-wrap gap-3 mb-8">
      {INDICES.map(t => (
        quotes[t] ? (
          <div key={t} className="flex items-center gap-2 bg-card border border-white/5 rounded-xl px-3 py-2">
            <span className="text-slate-400 text-xs font-semibold">{t}</span>
            <PriceChip price={quotes[t].price} change_pct={quotes[t].change_pct} size="sm" />
          </div>
        ) : <Skeleton key={t} className="h-10 w-28" />
      ))}
    </div>
  )
}

export default function Brief() {
  const [dayScreener, setDayScreener]       = useState<ScreenerResult | null>(null)
  const [ltScreener, setLtScreener]         = useState<ScreenerResult | null>(null)
  const [news, setNews]                     = useState<NewsBundle | null>(null)
  const [dayErr, setDayErr]                 = useState(false)
  const [ltErr, setLtErr]                   = useState(false)
  const [newsErr, setNewsErr]               = useState(false)

  useEffect(() => {
    getScreenerBestDay(8).then(setDayScreener).catch(() => setDayErr(true))
    getScreenerLongTerm(6).then(setLtScreener).catch(() => setLtErr(true))
    getMarketNews().then(setNews).catch(() => setNewsErr(true))
  }, [])

  return (
    <div className="p-6 max-w-5xl mx-auto pb-24 md:pb-6">
      <h1 className="text-xl font-bold text-white mb-5">Market Brief</h1>

      <IndexBar />

      {/* Top Picks Today */}
      <Section icon={<TrendingUp size={16} />} title="Top Picks Today">
        {dayErr && <ErrMsg />}
        {!dayErr && !dayScreener && <SkeletonGrid n={8} />}
        {dayScreener && (
          <>
            {dayScreener.ai_narrative && (
              <p className="text-slate-400 text-sm mb-4">{dayScreener.ai_narrative}</p>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {(dayScreener.picks as DayPick[]).map((p, i) => (
                <motion.div key={p.ticker}
                  initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="bg-card border border-white/5 rounded-xl p-4"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-white">{p.ticker}</span>
                    {p.price && <span className="text-slate-400 text-sm">${p.price.toFixed(2)}</span>}
                  </div>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300">
                      Score {p.composite_score.toFixed(1)}
                    </span>
                    {p.rsi_14 && (
                      <span className="text-xs text-slate-500">RSI {p.rsi_14.toFixed(0)}</span>
                    )}
                  </div>
                  <ul className="space-y-1">
                    {p.reasoning.slice(0, 2).map((r, j) => (
                      <li key={j} className="text-xs text-slate-400 flex gap-1.5">
                        <span className="text-blue-500 mt-0.5">•</span>{r}
                      </li>
                    ))}
                  </ul>
                </motion.div>
              ))}
            </div>
          </>
        )}
      </Section>

      {/* Long-Term Value */}
      <Section icon={<BarChart2 size={16} />} title="Long-Term Value Picks">
        {ltErr && <ErrMsg />}
        {!ltErr && !ltScreener && <SkeletonGrid n={6} />}
        {ltScreener && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {(ltScreener.picks as LongTermPick[]).map((p, i) => (
              <motion.div key={p.ticker}
                initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
                className="bg-card border border-white/5 rounded-xl p-4"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-bold text-white">{p.ticker}</span>
                  {p.sector && <span className="text-xs text-slate-500">{p.sector}</span>}
                </div>
                <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 mb-3 inline-block">
                  Score {p.composite_score.toFixed(1)}
                </span>
                <div className="flex gap-3 text-xs text-slate-400 mb-3">
                  {p.roe        != null && <span>ROE {(p.roe * 100).toFixed(0)}%</span>}
                  {p.profit_margin != null && <span>Margin {(p.profit_margin * 100).toFixed(0)}%</span>}
                </div>
                <ul className="space-y-1">
                  {p.reasoning.slice(0, 2).map((r, j) => (
                    <li key={j} className="text-xs text-slate-400 flex gap-1.5">
                      <span className="text-purple-500 mt-0.5">•</span>{r}
                    </li>
                  ))}
                </ul>
              </motion.div>
            ))}
          </div>
        )}
      </Section>

      {/* News */}
      <Section icon={<Newspaper size={16} />} title="Market News">
        {newsErr && <ErrMsg />}
        {!newsErr && !news && (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-20" />)}
          </div>
        )}
        {news && (
          <div className="space-y-3">
            {news.articles.map((a, i) => (
              <motion.a key={i} href={a.url} target="_blank" rel="noopener noreferrer"
                initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                className="flex items-start justify-between gap-4 bg-card border border-white/5 rounded-xl p-4 hover:border-white/15 transition-colors group"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white font-medium mb-1 line-clamp-2 group-hover:text-blue-300 transition-colors">
                    {a.title}
                  </p>
                  {a.summary && (
                    <p className="text-xs text-slate-500 line-clamp-2 mb-2">{a.summary}</p>
                  )}
                  <div className="flex gap-2 text-xs text-slate-600">
                    <span>{a.publisher}</span>
                    <span>·</span>
                    <span>{new Date(a.published_at).toLocaleDateString()}</span>
                  </div>
                </div>
                <ExternalLink size={14} className="shrink-0 text-slate-600 group-hover:text-blue-400 mt-0.5" />
              </motion.a>
            ))}
          </div>
        )}
      </Section>
    </div>
  )
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-blue-400">{icon}</span>
        <h2 className="text-base font-semibold text-white">{title}</h2>
      </div>
      {children}
    </section>
  )
}

function SkeletonGrid({ n }: { n: number }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      {Array.from({ length: n }).map((_, i) => <Skeleton key={i} className="h-28" />)}
    </div>
  )
}

function ErrMsg() {
  return <p className="text-rose-400 text-sm">Failed to load — is the backend running?</p>
}
