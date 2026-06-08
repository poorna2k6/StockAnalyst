import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Settings2, Eye, EyeOff, LogOut, Cpu, Zap } from 'lucide-react'
import { getSettings, updateSettings, getUsage } from '../lib/api'
import { useAppStore } from '../store/app'
import type { UsageSummary } from '../lib/types'
import { supabase } from '../lib/supabase'
import { useNavigate } from 'react-router-dom'

export default function Settings() {
  const navigate = useNavigate()
  const { settings, setSettings } = useAppStore()
  const [usage, setUsage]         = useState<UsageSummary | null>(null)
  const [loading, setLoading]     = useState(true)
  const [saving, setSaving]       = useState(false)
  const [error, setError]         = useState('')
  const [saved, setSaved]         = useState(false)

  const [claudeKey, setClaudeKey] = useState('')
  const [geminiKey, setGeminiKey] = useState('')
  const [showClaude, setShowClaude] = useState(false)
  const [showGemini, setShowGemini] = useState(false)

  useEffect(() => {
    Promise.all([
      getSettings().then(s => setSettings(s)).catch(() => {}),
      getUsage().then(setUsage).catch(() => {}),
    ]).finally(() => setLoading(false))
  }, [setSettings])

  async function save(updates: Parameters<typeof updateSettings>[0]) {
    setSaving(true); setError(''); setSaved(false)
    try {
      const updated = await updateSettings(updates)
      setSettings(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch { setError('Failed to save settings.') }
    finally { setSaving(false) }
  }

  async function signOut() {
    if (supabase) await supabase.auth.signOut()
    navigate('/')
  }

  return (
    <div className="p-6 max-w-2xl mx-auto pb-24 md:pb-6">
      <div className="flex items-center gap-2 mb-6">
        <Settings2 size={18} className="text-blue-400" />
        <h1 className="text-xl font-bold text-white">Settings</h1>
      </div>

      {error && <p className="text-rose-400 text-sm mb-4">{error}</p>}
      {saved  && <p className="text-emerald-400 text-sm mb-4">Saved ✓</p>}

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-20 rounded-xl animate-pulse bg-white/5" />)}
        </div>
      ) : (
        <div className="space-y-4">

          {/* Model selector */}
          <Card title="AI Model" icon={<Cpu size={14} />}>
            <div className="flex gap-2">
              {(['claude', 'gemini'] as const).map(m => (
                <button key={m} disabled={saving}
                  onClick={() => save({ preferred_model: m })}
                  className={`flex-1 py-2.5 rounded-xl text-sm font-medium transition-all capitalize
                    ${settings?.preferred_model === m
                      ? 'bg-gradient-to-r from-blue-500 to-purple-600 text-white shadow-lg shadow-blue-500/20'
                      : 'bg-white/5 border border-white/10 text-slate-400 hover:text-white'}`}
                >
                  {m === 'claude' ? '✦ Claude' : '◆ Gemini'}
                </button>
              ))}
            </div>
            <p className="text-xs text-slate-600 mt-2">
              Current: <span className="text-slate-400 capitalize">{settings?.preferred_model ?? '—'}</span>
            </p>
          </Card>

          {/* BYOK */}
          <Card title="Bring Your Own Key (BYOK)" icon={<Zap size={14} />}>
            <label className="flex items-center gap-3 mb-4 cursor-pointer">
              <div className="relative">
                <input type="checkbox" className="sr-only"
                  checked={settings?.use_byok ?? false}
                  onChange={e => save({ use_byok: e.target.checked })}
                />
                <div className={`w-10 h-5 rounded-full transition-colors ${settings?.use_byok ? 'bg-blue-500' : 'bg-white/10'}`} />
                <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${settings?.use_byok ? 'translate-x-5' : 'translate-x-0.5'}`} />
              </div>
              <span className="text-sm text-slate-300">Use my own API keys</span>
            </label>

            <div className="space-y-3">
              <KeyInput label="Claude API Key" placeholder={settings?.has_claude_key ? '••••••••••••••••' : 'sk-ant-...'}
                value={claudeKey} onChange={setClaudeKey}
                show={showClaude} onToggle={() => setShowClaude(p => !p)}
                saved={settings?.has_claude_key}
                onSave={() => { save({ byok_claude_key: claudeKey }); setClaudeKey('') }}
              />
              <KeyInput label="Gemini API Key" placeholder={settings?.has_gemini_key ? '••••••••••••••••' : 'AIza...'}
                value={geminiKey} onChange={setGeminiKey}
                show={showGemini} onToggle={() => setShowGemini(p => !p)}
                saved={settings?.has_gemini_key}
                onSave={() => { save({ byok_gemini_key: geminiKey }); setGeminiKey('') }}
              />
            </div>
          </Card>

          {/* Credits */}
          <Card title="App Credits" icon={<span className="text-xs">$</span>}>
            <p className="text-2xl font-bold text-white">
              ${settings?.credit_balance?.toFixed(4) ?? '0.0000'}
            </p>
            <p className="text-xs text-slate-600 mt-1">Used when BYOK is off</p>
          </Card>

          {/* Usage */}
          {usage && (
            <Card title="Usage This Period" icon={<span className="text-xs">📊</span>}>
              <div className="grid grid-cols-3 gap-3 mb-4">
                {[
                  { label: 'Calls',   value: usage.total_calls.toLocaleString() },
                  { label: 'Tokens',  value: usage.total_tokens.toLocaleString() },
                  { label: 'Cost',    value: `$${usage.total_cost_usd.toFixed(4)}` },
                ].map(({ label, value }) => (
                  <div key={label} className="bg-white/5 rounded-lg p-3 text-center">
                    <p className="text-xs text-slate-500 mb-0.5">{label}</p>
                    <p className="text-sm font-semibold text-white">{value}</p>
                  </div>
                ))}
              </div>
              {Object.keys(usage.by_feature).length > 0 && (
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-slate-600 border-b border-white/5">
                      <th className="text-left py-1.5">Feature</th>
                      <th className="text-right py-1.5">Calls</th>
                      <th className="text-right py-1.5">Tokens</th>
                      <th className="text-right py-1.5">Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(usage.by_feature).map(([feature, stats]) => (
                      <motion.tr key={feature} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                        className="border-b border-white/5 last:border-0"
                      >
                        <td className="py-1.5 text-slate-400 capitalize">{feature}</td>
                        <td className="py-1.5 text-right text-slate-500">{stats.calls}</td>
                        <td className="py-1.5 text-right text-slate-500">{stats.tokens.toLocaleString()}</td>
                        <td className="py-1.5 text-right text-slate-500">${stats.cost_usd.toFixed(4)}</td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          )}

          {/* Sign out */}
          <button onClick={signOut}
            className="flex items-center gap-2 w-full justify-center py-3 rounded-xl border border-rose-500/30 text-rose-400 hover:bg-rose-500/10 transition-colors text-sm"
          >
            <LogOut size={15} /> Sign out
          </button>

        </div>
      )}
    </div>
  )
}

function Card({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="bg-card border border-white/5 rounded-xl p-4">
      <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
        <span className="text-blue-400">{icon}</span>{title}
      </h3>
      {children}
    </div>
  )
}

function KeyInput({ label, placeholder, value, onChange, show, onToggle, saved, onSave }: {
  label: string; placeholder: string; value: string; onChange: (v: string) => void
  show: boolean; onToggle: () => void; saved?: boolean; onSave: () => void
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-slate-500">{label}</span>
        {saved && <span className="text-xs text-emerald-400">Saved ✓</span>}
      </div>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <input type={show ? 'text' : 'password'} value={value} onChange={e => onChange(e.target.value)}
            placeholder={placeholder}
            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 pr-9 py-2 text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-500/60 transition-colors"
          />
          <button type="button" onClick={onToggle} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-600 hover:text-white transition-colors">
            {show ? <EyeOff size={12} /> : <Eye size={12} />}
          </button>
        </div>
        <button onClick={onSave} disabled={!value.trim()}
          className="px-3 py-2 rounded-lg bg-white/10 border border-white/10 text-white text-xs hover:bg-white/15 disabled:opacity-40 transition-colors"
        >
          Save
        </button>
      </div>
    </div>
  )
}
