/**
 * components/Layout.jsx
 * ──────────────────────
 * Shell principal da aplicação: sidebar + área de conteúdo.
 */

import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const NAV = [
  { path: '/dashboard',  icon: '▦',  label: 'Dashboard'  },
  { path: '/upload',     icon: '↑',  label: 'Novo Edital' },
  { path: '/jobs',       icon: '◎',  label: 'Jobs'        },
]

const NAV_ADMIN = [
  { path: '/usuarios',   icon: '⊕',  label: 'Usuários'   },
]

export default function Layout({ children }) {
  const { user, logout, isAdmin } = useAuth()
  const location = useLocation()

  const items = isAdmin ? [...NAV, ...NAV_ADMIN] : NAV

  return (
    <div className="flex h-screen overflow-hidden">

      {/* ── Sidebar ──────────────────────────────────────────────────────── */}
      <aside className="w-56 flex-shrink-0 bg-ink-100 border-r border-slate-border flex flex-col">

        {/* Logo */}
        <div className="px-5 py-6 border-b border-slate-border">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-azure flex items-center justify-center text-white text-xs font-mono font-bold">EM</div>
            <div>
              <p className="font-display font-bold text-sm text-white leading-none">Edital</p>
              <p className="font-display font-bold text-sm text-azure-glow leading-none">Matcher</p>
            </div>
          </div>
        </div>

        {/* Nav links */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {items.map(item => {
            const active = location.pathname.startsWith(item.path)
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-body transition-all duration-150
                  ${active
                    ? 'bg-azure/10 text-azure-glow border border-azure/20'
                    : 'text-gray-400 hover:text-white hover:bg-slate-hover'
                  }`}
              >
                <span className="font-mono text-base w-4 text-center">{item.icon}</span>
                {item.label}
              </Link>
            )
          })}
        </nav>

        {/* Tenant + logout */}
        <div className="px-3 py-4 border-t border-slate-border">
          <div className="px-3 py-2 mb-2">
            <p className="text-xs text-gray-500 font-mono uppercase tracking-widest">Tenant</p>
            <p className="text-sm text-white font-display font-semibold truncate mt-0.5">
              {user?.tenant?.name || '—'}
            </p>
            <p className="text-xs text-gray-500 font-mono mt-0.5">{user?.email}</p>
          </div>
          <button
            onClick={logout}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-500 hover:text-red-fail hover:bg-red-dim/20 transition-all duration-150"
          >
            <span className="font-mono">⊗</span> Sair
          </button>
        </div>
      </aside>

      {/* ── Conteúdo ─────────────────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  )
}
