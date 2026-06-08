import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Plus, Trash2, Star } from 'lucide-react'
import { getWatchlist, addToWatchlist, removeFromWatchlist } from '../lib/api'
import type { Quote } from '../lib/types'
import { PriceChip } from '../components/PriceChip'

interface WatchItem {
  ticker: string
  added_at: string
  quote?: Quote
}

export default function Watchlist() {
  const [items, setItems]   = useState<WatchItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState('')
  const [input, setInput]   = useState('')
  const [addErr, setAddErr] = useState('')

  async function reload() {
    setLoading(true); setError('')
    try { setItems(await getWatchlist()) }
    catch { setError('Failed to load watchlist. Is the backend running?') }
    finally { setLoading(false) }
  }

  useEffect(() => { reload() }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault(); setAddErr('')
    const t = input.trim().toUpperCase()
    if (!t) return
    try { await addToWatchlist(t); setInput(''); await reload() }
    catch { setAddErr(`Failed to add ${t}.`) }
  }

  async function handleRemove(ticker: string) {
    try { await removeFromWatchlist(ticker); setItems(prev => prev.filter(i => i.ticker !== ticker)) }
    catch { setError(`Failed to remove ${ticker}.`) }
  }

  return (
    <div className="p-6 max-w-3xl mx-auto pb-24 md:pb-6">
      <div className="flex items-center gap-2 mb-6">
        <Star size={18} className="text-yellow-400" />
        <h1 className="text-xl font-bold text-white">Watchlist</h1>
      </div>

      {error && <p className="text-rose-400 text-sm mb-4">{error}</p>}

      {/* Add form */}
      <form onSubmit={handleAdd} className="flex gap-2 mb-6">
        <input value={input} onChange={e => setInput(e.target.value)} placeholder="Add ticker, e.g. MSFT"
          className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/60 transition-colors uppercase"
        />
        <button type="submit"
          className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-gradient-to-r from-blue-500 to-purple-600 text-white text-sm font-medium hover:opacity-90 transition-opacity"
        >
          <Plus size={14} /> Add
        </button>
      </form>
      {addErr && <p className="text-rose-400 text-xs mb-4">{addErr}</p>}

      {/* Loading skeletons */}
      {loading && (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-16 rounded-xl animate-pulse bg-white/5" />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && items.length === 0 && (
        <div className="text-center py-16">
          <Star size={32} className="text-slate-700 mx-auto mb-3" />
          <p className="text-slate-500 text-sm">Your watchlist is empty.</p>
          <p className="text-slate-600 text-xs mt-1">Add tickers above to track them.</p>
        </div>
      )}

      {/* Watchlist rows */}
      {!loading && items.length > 0 && (
        <div className="bg-card border border-white/5 rounded-xl overflow-hidden">
          {items.map((item, i) => (
            <motion.div key={item.ticker}
              initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="flex items-center justify-between px-4 py-3.5 border-b border-white/5 last:border-0 hover:bg-white/2 transition-colors"
            >
              <div className="flex items-center gap-4">
                <span className="font-bold text-white w-16">{item.ticker}</span>
                {item.quote ? (
                  <PriceChip price={item.quote.price} change_pct={item.quote.change_pct} size="sm" />
                ) : (
                  <span className="text-xs text-slate-600">—</span>
                )}
                {item.quote?.week_52_low != null && item.quote?.week_52_high != null && (
                  <div className="hidden sm:flex items-center gap-1.5 text-xs text-slate-600">
                    <span>${item.quote.week_52_low.toFixed(2)}</span>
                    <div className="w-20 h-1.5 bg-white/10 rounded-full relative">
                      <div
                        className="absolute left-0 top-0 h-full bg-blue-500 rounded-full"
                        style={{
                          width: `${Math.min(100, Math.max(0,
                            ((item.quote.price - item.quote.week_52_low) /
                             (item.quote.week_52_high - item.quote.week_52_low)) * 100
                          ))}%`,
                        }}
                      />
                    </div>
                    <span>${item.quote.week_52_high.toFixed(2)}</span>
                  </div>
                )}
              </div>
              <div className="flex items-center gap-4">
                <span className="text-xs text-slate-600 hidden sm:block">
                  {new Date(item.added_at).toLocaleDateString()}
                </span>
                <button onClick={() => handleRemove(item.ticker)}
                  className="text-slate-600 hover:text-rose-400 transition-colors"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}
