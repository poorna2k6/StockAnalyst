import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Plus, Trash2, DollarSign, RotateCcw } from 'lucide-react'
import { getPortfolio, addPosition, removePosition, setCash, resetPortfolio } from '../lib/api'
import { useAppStore } from '../store/app'
import type { PositionSummary } from '../lib/types'

function fmt(n: number, decimals = 2) {
  return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

function pctColor(n: number) {
  return n >= 0 ? 'text-emerald-400' : 'text-rose-400'
}

export default function Portfolio() {
  const { portfolio, setPortfolio } = useAppStore()
  const [loading, setLoading]  = useState(false)
  const [error, setError]      = useState('')

  // Add form
  const [ticker, setTicker]   = useState('')
  const [shares, setShares]   = useState('')
  const [cost, setCostVal]    = useState('')
  const [addErr, setAddErr]   = useState('')

  // Cash form
  const [cashInput, setCashInput] = useState('')

  async function reload() {
    setLoading(true); setError('')
    try { setPortfolio(await getPortfolio()) }
    catch { setError('Failed to load portfolio. Is the backend running?') }
    finally { setLoading(false) }
  }

  useEffect(() => { reload() }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault(); setAddErr('')
    const t = ticker.trim().toUpperCase()
    const s = parseFloat(shares)
    const c = parseFloat(cost)
    if (!t || isNaN(s) || isNaN(c) || s <= 0 || c <= 0) { setAddErr('Enter valid ticker, shares, and cost.'); return }
    try {
      setPortfolio(await addPosition(t, s, c))
      setTicker(''); setShares(''); setCostVal('')
    } catch { setAddErr('Failed to add position.') }
  }

  async function handleRemove(t: string) {
    try { setPortfolio(await removePosition(t)) }
    catch { setError(`Failed to remove ${t}.`) }
  }

  async function handleSetCash(e: React.FormEvent) {
    e.preventDefault()
    const amount = parseFloat(cashInput)
    if (isNaN(amount) || amount < 0) return
    try { await setCash(amount); await reload(); setCashInput('') }
    catch { setError('Failed to update cash.') }
  }

  async function handleReset() {
    if (!confirm('Reset entire portfolio? This cannot be undone.')) return
    try { await resetPortfolio(); await reload() }
    catch { setError('Failed to reset portfolio.') }
  }

  const positions: PositionSummary[] = portfolio?.positions ?? []

  return (
    <div className="p-6 max-w-4xl mx-auto pb-24 md:pb-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-white">Portfolio</h1>
        <button onClick={handleReset}
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-rose-400 transition-colors"
        >
          <RotateCcw size={13} /> Reset
        </button>
      </div>

      {error && <p className="text-rose-400 text-sm mb-4">{error}</p>}

      {/* Summary */}
      {portfolio && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          {[
            { label: 'Total Value',   value: `$${fmt(portfolio.total_value)}` },
            { label: 'Total Cost',    value: `$${fmt(portfolio.total_cost)}` },
            { label: 'Gain / Loss',   value: `${portfolio.total_gain_loss >= 0 ? '+' : ''}$${fmt(portfolio.total_gain_loss)}`, color: pctColor(portfolio.total_gain_loss) },
            { label: 'Cash',          value: `$${fmt(portfolio.cash)}` },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-card border border-white/5 rounded-xl p-4">
              <p className="text-xs text-slate-500 mb-1">{label}</p>
              <p className={`font-semibold text-sm ${color ?? 'text-white'}`}>{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Positions table */}
      {loading && !portfolio && (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-14 rounded-xl animate-pulse bg-white/5" />
          ))}
        </div>
      )}

      {positions.length > 0 && (
        <div className="bg-card border border-white/5 rounded-xl overflow-hidden mb-6">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/5 text-slate-500 text-xs">
                  <th className="text-left px-4 py-3">Ticker</th>
                  <th className="text-right px-4 py-3">Shares</th>
                  <th className="text-right px-4 py-3">Avg Cost</th>
                  <th className="text-right px-4 py-3">Price</th>
                  <th className="text-right px-4 py-3">Value</th>
                  <th className="text-right px-4 py-3">G/L</th>
                  <th className="text-right px-4 py-3">G/L%</th>
                  <th className="text-right px-4 py-3">Wt%</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {positions.map((p, i) => (
                  <motion.tr key={p.ticker}
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.04 }}
                    className="border-b border-white/5 last:border-0 hover:bg-white/2 transition-colors"
                  >
                    <td className="px-4 py-3 font-bold text-white">{p.ticker}</td>
                    <td className="px-4 py-3 text-right text-slate-300">{fmt(p.shares, 4)}</td>
                    <td className="px-4 py-3 text-right text-slate-300">${fmt(p.avg_cost)}</td>
                    <td className="px-4 py-3 text-right text-slate-300">${fmt(p.current_price)}</td>
                    <td className="px-4 py-3 text-right text-white">${fmt(p.current_value)}</td>
                    <td className={`px-4 py-3 text-right ${pctColor(p.gain_loss)}`}>
                      {p.gain_loss >= 0 ? '+' : ''}${fmt(p.gain_loss)}
                    </td>
                    <td className={`px-4 py-3 text-right ${pctColor(p.gain_loss_pct)}`}>
                      {p.gain_loss_pct >= 0 ? '+' : ''}{fmt(p.gain_loss_pct)}%
                    </td>
                    <td className="px-4 py-3 text-right text-slate-500">{fmt(p.weight)}%</td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => handleRemove(p.ticker)}
                        className="text-slate-600 hover:text-rose-400 transition-colors"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {positions.length === 0 && !loading && (
        <p className="text-slate-500 text-sm text-center py-8">No positions yet. Add one below.</p>
      )}

      {/* Add position */}
      <div className="bg-card border border-white/5 rounded-xl p-4 mb-4">
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <Plus size={14} /> Add Position
        </h3>
        <form onSubmit={handleAdd} className="flex flex-wrap gap-2">
          <input value={ticker} onChange={e => setTicker(e.target.value)} placeholder="AAPL"
            className="w-24 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/60 uppercase"
          />
          <input value={shares} onChange={e => setShares(e.target.value)} placeholder="Shares" type="number" min="0" step="any"
            className="w-28 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/60"
          />
          <input value={cost} onChange={e => setCostVal(e.target.value)} placeholder="Avg cost $" type="number" min="0" step="any"
            className="w-32 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/60"
          />
          <button type="submit"
            className="px-4 py-2 rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 text-white text-sm font-medium hover:opacity-90 transition-opacity"
          >
            Add
          </button>
        </form>
        {addErr && <p className="text-rose-400 text-xs mt-2">{addErr}</p>}
      </div>

      {/* Set cash */}
      <div className="bg-card border border-white/5 rounded-xl p-4">
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <DollarSign size={14} /> Set Cash Balance
        </h3>
        <form onSubmit={handleSetCash} className="flex gap-2">
          <input value={cashInput} onChange={e => setCashInput(e.target.value)} placeholder="Amount $" type="number" min="0" step="any"
            className="w-40 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/60"
          />
          <button type="submit"
            className="px-4 py-2 rounded-lg bg-white/10 border border-white/10 text-white text-sm hover:bg-white/15 transition-colors"
          >
            Update
          </button>
        </form>
      </div>
    </div>
  )
}
