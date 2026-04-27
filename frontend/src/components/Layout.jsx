import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import ChatWidget from './ChatWidget'
import torLogo from '../images/Tor.jpeg'

const NAV = [
  { path: '/dashboard',    icon: '▦',  label: 'Dashboard'   },
  { path: '/upload',       icon: '↑',  label: 'Novo Edital' },
  { path: '/pncp',         icon: '🏛', label: 'PNCP'        },
  { path: '/controle',     icon: '◫',  label: 'Controle'    },
  { path: '/analytics',    icon: '◈',  label: 'Análise'     },
  { path: '/jobs',         icon: '◎',  label: 'Jobs'        },
  { path: '/configuracoes', icon: '⚙', label: 'Configurações' },
]

const NAV_ADMIN = [
  { path: '/usuarios', icon: '⊕', label: 'Usuários' },
]

export default function Layout({ children }) {
  const { user, logout, isAdmin } = useAuth()
  const location = useLocation()

  const items = isAdmin ? [...NAV, ...NAV_ADMIN] : NAV

  return (
    <div className="flex h-screen overflow-hidden">

      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside className="w-60 flex-shrink-0 bg-ink-100 border-r border-slate-border flex flex-col"
             style={{ boxShadow: '4px 0 24px rgba(220,38,38,0.04)' }}>

        {/* Logo Tor Tecnologias */}
        <div className="px-5 py-5 border-b border-slate-border">
          <div className="flex items-center gap-3">
            <div className="relative w-10 h-10 flex-shrink-0">
              <div className="absolute inset-0 rounded-xl bg-azure opacity-20 blur-md" />
              <img
                src={torLogo}
                alt="Tor Tecnologias"
                className="relative w-10 h-10 rounded-xl object-cover ring-1 ring-azure/40"
              />
            </div>
            <div className="leading-tight">
              <p className="font-display font-black text-sm text-white tracking-wide">Tor Tecnologias</p>
              <p className="font-mono text-[10px] text-azure-glow tracking-widest uppercase">Licitações IA</p>
            </div>
          </div>

          {/* Linha decorativa */}
          <div className="mt-4 h-px bg-gradient-to-r from-azure/50 via-azure/10 to-transparent" />
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {items.map(item => {
            const active = location.pathname.startsWith(item.path)
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-body transition-all duration-150
                  ${active
                    ? 'bg-azure/10 text-azure-glow border border-azure/20 shadow-sm'
                    : 'text-gray-400 hover:text-white hover:bg-slate-hover'
                  }`}
              >
                <span className={`font-mono text-base w-4 text-center transition-colors ${active ? 'text-azure-glow' : ''}`}>
                  {item.icon}
                </span>
                <span className="truncate">{item.label}</span>
                {active && (
                  <div className="ml-auto w-1 h-1 rounded-full bg-azure-glow" />
                )}
              </Link>
            )
          })}
        </nav>

        {/* Tenant + usuário + logout */}
        <div className="px-3 pb-4 border-t border-slate-border pt-3 space-y-1">
          {/* Info do tenant */}
          <div className="px-3 py-2.5 rounded-lg bg-slate-card border border-slate-border mb-2">
            <p className="text-xs text-gray-500 font-mono uppercase tracking-widest leading-none mb-1">Empresa</p>
            <p className="text-sm text-white font-display font-semibold truncate">{user?.tenant?.name || '—'}</p>
            <p className="text-xs text-gray-500 font-mono truncate mt-0.5">{user?.email}</p>
          </div>

          <button
            onClick={logout}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-500 hover:text-red-fail hover:bg-red-dim/20 transition-all duration-150"
          >
            <span className="font-mono text-base">⊗</span>
            <span>Sair</span>
          </button>
        </div>
      </aside>

      {/* ── Conteúdo principal ───────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto">{children}</main>

      {/* ── ChatWidget flutuante (disponível em todas as páginas) ────────── */}
      <ChatWidget />
    </div>
  )
}
