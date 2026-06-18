import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { supabase, isSupabaseConfigured } from './lib/supabase'
import { useAuthStore } from './store/auth'
import Landing from './pages/Landing'
import Dashboard from './pages/Dashboard'
import Brief from './tabs/Brief'
import Signals from './tabs/Signals'
import Chat from './tabs/Chat'
import Portfolio from './tabs/Portfolio'
import Watchlist from './tabs/Watchlist'
import Settings from './tabs/Settings'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuthStore()
  if (loading) {
    return (
      <div className="min-h-screen bg-navy flex items-center justify-center">
        <div className="w-10 h-10 rounded-full border-2 border-white/10 border-t-blue-500 animate-spin" />
      </div>
    )
  }
  if (!user && isSupabaseConfigured) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  const { setUser, setSession, setLoading } = useAuthStore()

  useEffect(() => {
    if (!supabase) {
      setLoading(false)
      return
    }
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setUser(data.session?.user ?? null)
      setLoading(false)
    })
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      setUser(session?.user ?? null)
    })
    return () => subscription.unsubscribe()
  }, [setUser, setSession, setLoading])

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/app" element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }>
          <Route index element={<Navigate to="brief" replace />} />
          <Route path="brief" element={<Brief />} />
          <Route path="signals" element={<Signals />} />
          <Route path="chat" element={<Chat />} />
          <Route path="portfolio" element={<Portfolio />} />
          <Route path="watchlist" element={<Watchlist />} />
          <Route path="settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
