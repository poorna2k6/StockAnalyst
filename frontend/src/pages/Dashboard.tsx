import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { TrendingUp, BarChart2, MessageSquare, Briefcase, Star, Settings2, LogOut, Radio } from 'lucide-react'
import { supabase } from '../lib/supabase'

const NAV = [
  { icon: BarChart2,      label: 'Brief',     path: '/app/brief'     },
  { icon: Radio,          label: 'Signals',   path: '/app/signals'   },
  { icon: MessageSquare,  label: 'Chat',      path: '/app/chat'      },
  { icon: Briefcase,      label: 'Portfolio', path: '/app/portfolio' },
  { icon: Star,           label: 'Watchlist', path: '/app/watchlist' },
  { icon: Settings2,      label: 'Settings',  path: '/app/settings'  },
]

export default function Dashboard() {
  const navigate = useNavigate()

  async function signOut() {
    if (supabase) await supabase.auth.signOut()
    navigate('/')
  }

  return (
    <div className="flex h-screen bg-navy overflow-hidden">
      {/* Sidebar */}
      <aside className="hidden md:flex flex-col w-56 border-r border-white/5 bg-card shrink-0">
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-5 py-5 border-b border-white/5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <TrendingUp size={15} className="text-white" />
          </div>
          <span className="font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
            StockAI
          </span>
        </div>

        {/* Nav links */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map(({ icon: Icon, label, path }) => (
            <NavLink key={path} to={path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all
                ${isActive
                  ? 'bg-white/10 text-white'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'}`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Sign out */}
        <div className="px-3 pb-5">
          <button onClick={signOut}
            className="flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-sm text-slate-500 hover:text-white hover:bg-white/5 transition-all"
          >
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>

      {/* Mobile bottom bar */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 bg-card border-t border-white/5 flex justify-around py-2 z-50">
        {NAV.map(({ icon: Icon, label, path }) => (
          <NavLink key={path} to={path}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 px-3 py-1 text-xs transition-colors
              ${isActive ? 'text-blue-400' : 'text-slate-500'}`
            }
          >
            <Icon size={20} />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
