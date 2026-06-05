import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, TrendingUp, TrendingDown, Shield, Target, Loader2 } from 'lucide-react'
import { getAgentCouncil } from '../lib/api'
import type { AgentCouncilResult } from '../lib/types'

interface Props {
  ticker: string
  onClose: () => void
}

const AGENTS = [
  {
    id: 'bull' as const,
    label: 'Bull Agent',
    emoji: '🐂',
    Icon: TrendingUp,
    border: 'border-emerald-500/40',
    shadow: 'shadow-emerald-500/10',
    bg: 'bg-emerald-500/5',
    headerColor: 'text-emerald-300',
    thinking: 'Scanning for opportunities...',
  },
  {
    id: 'bear' as const,
    label: 'Bear Agent',
    emoji: '🐻',
    Icon: TrendingDown,
    border: 'border-rose-500/40',
    shadow: 'shadow-rose-500/10',
    bg: 'bg-rose-500/5',
    headerColor: 'text-rose-300',
    thinking: 'Evaluating risks...',
  },
  {
    id: 'risk' as const,
    label: 'Risk Agent',
    emoji: '⚖️',
    Icon: Shield,
    border: 'border-amber-500/40',
    shadow: 'shadow-amber-500/10',
    bg: 'bg-amber-500/5',
    headerColor: 'text-amber-300',
    thinking: 'Assessing volatility...',
  },
]

export function AgentCouncil({ ticker, onClose }: Props) {
  const [result, setResult] = useState<AgentCouncilResult | null>(null)
  const [error, setError] = useState('')
  const [status, setStatus] = useState(`Fetching live data for ${ticker}...`)

  useEffect(() => {
    let cancelled = false
    setStatus(`Fetching live data for ${ticker}...`)
    getAgentCouncil(ticker)
      .then((data) => {
        if (!cancelled) { setResult(data); setStatus('Analysis complete') }
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message || 'Analysis failed')
      })
    return () => { cancelled = true }
  }, [ticker])

  const verdictColorClass = (() => {
    if (!result?.verdict) return 'text-slate-200'
    const v = result.verdict.toLowerCase()
    if (v.includes('**buy') || v.includes('buy**')) return 'text-emerald-300'
    if (v.includes('**sell') || v.includes('sell**')) return 'text-rose-300'
    return 'text-amber-300'
  })()

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-3 sm:p-6 bg-black/70 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, y: 48 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 48 }}
        transition={{ type: 'spring', damping: 26, stiffness: 320 }}
        className="w-full max-w-3xl max-h-[92vh] overflow-y-auto bg-[#0d1424] border border-white/10 rounded-2xl shadow-2xl"
      >
        {/* Header */}
        <div className="sticky top-0 bg-[#0d1424]/95 backdrop-blur-sm border-b border-white/5 px-5 py-4 flex items-center justify-between z-10">
          <div>
            <h2 className="font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
              🎯 Investment Committee — {ticker}
            </h2>
            <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-1.5">
              {!result && !error && <Loader2 size={10} className="animate-spin text-blue-400" />}
              {status}
            </p>
          </div>
          <button onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-white/5 text-slate-400 hover:text-white transition-colors">
            <X size={17} />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {error && (
            <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 text-rose-300 text-sm">
              {error}
            </div>
          )}

          {/* 3 Agent Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {AGENTS.map((agent, i) => (
              <motion.div
                key={agent.id}
                initial={{ opacity: 0, x: -16 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.12 }}
                className={`rounded-xl border p-4 shadow-lg ${agent.border} ${agent.shadow} ${agent.bg}`}
              >
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-base">{agent.emoji}</span>
                  <span className={`text-sm font-semibold ${agent.headerColor}`}>{agent.label}</span>
                </div>
                {!result ? (
                  <div className="space-y-2">
                    <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-2">
                      <Loader2 size={9} className="animate-spin" />
                      {agent.thinking}
                    </div>
                    {[80, 65, 72].map((w, n) => (
                      <div key={n} className="h-2 rounded bg-white/5 animate-pulse" style={{ width: `${w}%` }} />
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-300 leading-relaxed">{result[agent.id]}</p>
                )}
              </motion.div>
            ))}
          </div>

          {/* Moderator Verdict */}
          <AnimatePresence>
            {result && (
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.25 }}
                className="rounded-xl border border-purple-500/40 bg-purple-500/5 shadow-lg shadow-purple-500/10 p-5"
              >
                <div className="flex items-center gap-2 mb-3">
                  <Target size={15} className="text-purple-400" />
                  <span className="text-sm font-bold text-purple-300">Committee Verdict</span>
                </div>
                <div className={`text-sm leading-relaxed whitespace-pre-wrap ${verdictColorClass}`}>
                  {result.verdict}
                </div>
                <p className="text-xs text-slate-600 mt-3 border-t border-white/5 pt-3">
                  Data fetched: {result.fetched_at} · Educational analysis, not financial advice.
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
    </div>
  )
}
