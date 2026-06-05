import { useState } from 'react'
import { motion } from 'framer-motion'
import { TrendingUp, Mail, Lock, User, Eye, EyeOff } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { supabase, isSupabaseConfigured } from '../lib/supabase'

interface ChipProps {
  ticker: string; price: string; pct: string
  positive: boolean; delay: number; x: string; y: string
}

function FloatingChip({ ticker, price, pct, positive, delay, x, y }: ChipProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: [0.7, 1, 0.7], y: [0, -10, 0] }}
      transition={{ delay, duration: 4, repeat: Infinity, ease: 'easeInOut' }}
      className={`absolute backdrop-blur-sm rounded-xl px-3 py-1.5 border text-xs font-medium shadow-lg
        ${positive
          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
          : 'bg-rose-500/10 border-rose-500/30 text-rose-300'}`}
      style={{ left: x, top: y }}
    >
      <span className="text-white font-bold mr-1">{ticker}</span>
      {price}
      <span className="ml-1">{positive ? '▲' : '▼'} {pct}</span>
    </motion.div>
  )
}

const CHIPS: ChipProps[] = [
  { ticker: 'NVDA', price: '$875', pct: '4.3%', positive: true,  delay: 0,   x: '6%',  y: '18%' },
  { ticker: 'AAPL', price: '$189', pct: '0.9%', positive: true,  delay: 0.6, x: '10%', y: '52%' },
  { ticker: 'TSLA', price: '$242', pct: '2.1%', positive: false, delay: 1.1, x: '4%',  y: '76%' },
  { ticker: 'META', price: '$521', pct: '1.9%', positive: true,  delay: 0.3, x: '66%', y: '22%' },
  { ticker: 'AMD',  price: '$163', pct: '3.1%', positive: true,  delay: 0.8, x: '70%', y: '68%' },
]

export default function Landing() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  async function handleAuth(e: React.FormEvent) {
    e.preventDefault()
    setError(''); setMessage('')
    setLoading(true)
    try {
      if (!supabase) { navigate('/app/brief'); return }
      if (tab === 'signin') {
        const { error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) throw error
        navigate('/app/brief')
      } else {
        const { error } = await supabase.auth.signUp({
          email, password,
          options: { data: { full_name: name } },
        })
        if (error) throw error
        setMessage('Check your email to confirm your account!')
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleGoogle() {
    if (!supabase) return
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/app/brief` },
    })
  }

  return (
    <div className="min-h-screen bg-navy flex">
      {/* Left hero */}
      <div className="hidden lg:flex flex-1 flex-col items-center justify-center relative overflow-hidden border-r border-white/5">
        <div className="absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage:
              'linear-gradient(rgba(59,130,246,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(59,130,246,0.5) 1px, transparent 1px)',
            backgroundSize: '44px 44px',
          }}
        />
        {CHIPS.map((c, i) => <FloatingChip key={i} {...c} />)}

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="relative z-10 text-center px-14"
        >
          <div className="flex items-center justify-center gap-3 mb-7">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-xl shadow-blue-500/30">
              <TrendingUp size={22} className="text-white" />
            </div>
            <span className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
              StockAI
            </span>
          </div>
          <h1 className="text-4xl font-bold text-white leading-tight mb-4">
            Your AI-powered<br />investment council.
          </h1>
          <p className="text-slate-400 text-lg max-w-sm mx-auto">
            Real-time data. Zero hallucination. Three agents debate every stock so you don't have to.
          </p>
          <div className="flex gap-2 justify-center mt-8 flex-wrap">
            {['Real-time quotes', 'Agent Council', 'Claude & Gemini', 'BYOK support'].map(f => (
              <span key={f} className="text-xs px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-slate-300">
                {f}
              </span>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Right auth */}
      <div className="flex flex-1 items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          className="w-full max-w-md"
        >
          {/* Mobile logo */}
          <div className="flex lg:hidden items-center gap-2 mb-8">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
              <TrendingUp size={15} className="text-white" />
            </div>
            <span className="font-bold text-white">StockAI</span>
          </div>

          <h2 className="text-2xl font-bold text-white mb-1">
            {tab === 'signin' ? 'Welcome back' : 'Get started free'}
          </h2>
          <p className="text-slate-400 text-sm mb-6">
            {tab === 'signin' ? 'Sign in to your account' : 'Create your account'}
          </p>

          {!isSupabaseConfigured && (
            <div className="mb-4 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-sm">
              Dev mode — Supabase not configured. Click Sign In to continue.
            </div>
          )}

          {/* Tab toggle */}
          <div className="flex rounded-xl bg-white/5 border border-white/5 p-1 mb-5">
            {(['signin', 'signup'] as const).map(t => (
              <button key={t}
                onClick={() => { setTab(t); setError('') }}
                className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all
                  ${tab === t ? 'bg-white/10 text-white shadow-sm' : 'text-slate-400 hover:text-white'}`}
              >
                {t === 'signin' ? 'Sign In' : 'Sign Up'}
              </button>
            ))}
          </div>

          {isSupabaseConfigured && (
            <>
              <button onClick={handleGoogle}
                className="w-full flex items-center justify-center gap-3 py-2.5 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-white text-sm font-medium transition-colors mb-4"
              >
                <svg width="16" height="16" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Continue with Google
              </button>
              <div className="flex items-center gap-3 mb-4">
                <div className="flex-1 h-px bg-white/10" />
                <span className="text-xs text-slate-600">or</span>
                <div className="flex-1 h-px bg-white/10" />
              </div>
            </>
          )}

          <form onSubmit={handleAuth} className="space-y-3">
            {tab === 'signup' && (
              <div className="relative">
                <User size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" />
                <input value={name} onChange={e => setName(e.target.value)} placeholder="Full name"
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-600 text-sm focus:outline-none focus:border-blue-500/60 transition-colors"
                />
              </div>
            )}
            <div className="relative">
              <Mail size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" />
              <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                placeholder="Email address" required
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-600 text-sm focus:outline-none focus:border-blue-500/60 transition-colors"
              />
            </div>
            <div className="relative">
              <Lock size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" />
              <input type={showPw ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)}
                placeholder="Password" required
                className="w-full pl-10 pr-10 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-600 text-sm focus:outline-none focus:border-blue-500/60 transition-colors"
              />
              <button type="button" onClick={() => setShowPw(!showPw)}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white transition-colors">
                {showPw ? <EyeOff size={13} /> : <Eye size={13} />}
              </button>
            </div>

            {error   && <p className="text-rose-400 text-sm">{error}</p>}
            {message && <p className="text-emerald-400 text-sm">{message}</p>}

            <button type="submit" disabled={loading}
              className="w-full py-2.5 rounded-xl bg-gradient-to-r from-blue-500 to-purple-600 text-white text-sm font-semibold hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center justify-center gap-2 mt-1"
            >
              {loading
                ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Processing…</>
                : tab === 'signin' ? 'Sign In' : 'Create Account'
              }
            </button>
          </form>
        </motion.div>
      </div>
    </div>
  )
}
