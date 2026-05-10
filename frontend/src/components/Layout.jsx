import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import ChatWidget from './ChatWidget'
import torLogo from '../images/Tor.jpeg'

const NAV = [
  { path: '/dashboard', badge: 'DB', label: 'Dashboard', hint: 'Visao geral do sistema' },
  { path: '/upload', badge: 'UP', label: 'Novo edital', hint: 'Entrada e processamento' },
  { path: '/pncp', badge: 'PN', label: 'PNCP', hint: 'Busca e importacao publica' },
  { path: '/controle', badge: 'CT', label: 'Controle', hint: 'Operacao e acompanhamento' },
  { path: '/analytics', badge: 'AN', label: 'Analise', hint: 'Performance e inteligencia' },
  { path: '/jobs', badge: 'JB', label: 'Jobs', hint: 'Fila e processamento' },
  { path: '/crm', badge: 'CRM', label: 'CRM', hint: 'Bid Buddy integrado' },
  { path: '/configuracoes', badge: 'CFG', label: 'Configuracoes', hint: 'Ajustes do ambiente' },
]

const NAV_ADMIN = [
  { path: '/usuarios', badge: 'USR', label: 'Usuarios', hint: 'Gestao de acessos' },
]

function isActive(pathname, path) {
  return pathname === path || pathname.startsWith(`${path}/`)
}

function NavItem({ item, pathname }) {
  const active = isActive(pathname, item.path)

  return (
    <Link
      to={item.path}
      className={`group flex items-center gap-3 rounded-2xl border px-3 py-3 transition-all duration-200 ${
        active
          ? 'border-azure/30 bg-azure/10 text-white shadow-lg shadow-azure/10'
          : 'border-transparent text-gray-400 hover:border-slate-border hover:bg-slate-hover hover:text-white'
      }`}
    >
      <div
        className={`grid h-10 w-10 place-items-center rounded-xl border text-[11px] font-mono font-bold uppercase transition-all ${
          active
            ? 'border-azure/30 bg-azure/20 text-azure-glow'
            : 'border-slate-border bg-ink-50 text-gray-500 group-hover:text-white'
        }`}
      >
        {item.badge}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">{item.label}</p>
        <p className="truncate text-xs text-gray-500">{item.hint}</p>
      </div>
      {active && <div className="h-2 w-2 rounded-full bg-azure-glow" />}
    </Link>
  )
}

export default function Layout({ children }) {
  const { user, logout, isAdmin } = useAuth()
  const location = useLocation()

  const items = isAdmin ? [...NAV, ...NAV_ADMIN] : NAV
  const showChatWidget = !location.pathname.startsWith('/crm')

  return (
    <div className="min-h-screen bg-ink text-white md:flex">
      <aside className="hidden w-72 flex-shrink-0 flex-col border-r border-slate-border bg-ink-100/95 md:flex">
        <div className="border-b border-slate-border px-5 py-5">
          <div className="flex items-center gap-3">
            <div className="relative h-12 w-12 flex-shrink-0">
              <div className="absolute inset-0 rounded-2xl bg-azure/25 blur-md" />
              <img
                src={torLogo}
                alt="Tor Tecnologias"
                className="relative h-12 w-12 rounded-2xl object-cover ring-1 ring-azure/40"
              />
            </div>
            <div className="leading-tight">
              <p className="font-display text-base font-black tracking-wide text-white">Tor Tecnologias</p>
              <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-azure-glow">Portal de Licitacoes</p>
            </div>
          </div>

          <div className="mt-5 rounded-2xl border border-slate-border bg-ink-50/80 px-4 py-4">
            <p className="text-[11px] font-mono uppercase tracking-[0.28em] text-gray-500">Empresa</p>
            <p className="mt-2 truncate text-sm font-semibold text-white">{user?.tenant?.name || 'Ambiente Tor'}</p>
            <p className="mt-1 truncate text-xs text-gray-500">{user?.email || 'sem email informado'}</p>
          </div>
        </div>

        <nav className="flex-1 space-y-2 overflow-y-auto px-4 py-5">
          {items.map((item) => (
            <NavItem key={item.path} item={item} pathname={location.pathname} />
          ))}
        </nav>

        <div className="border-t border-slate-border px-4 py-4">
          <button
            onClick={logout}
            className="flex w-full items-center justify-center rounded-2xl border border-slate-border bg-ink-50 px-4 py-3 text-sm font-semibold text-gray-300 transition-colors hover:border-red-fail/40 hover:text-red-fail"
          >
            Encerrar sessao
          </button>

          <div className="mt-4 rounded-2xl border border-slate-border bg-[#090909] px-4 py-4">
            <p className="text-[11px] font-mono uppercase tracking-[0.28em] text-gray-500">Creditos</p>
            <p className="mt-2 text-sm font-semibold text-white">Alvaro Sampaio</p>
            <p className="mt-1 text-xs leading-6 text-gray-500">
              Integracao visual, operacao do portal e publicacao do CRM dentro do ambiente Tor.
            </p>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-slate-border bg-ink-100/95 backdrop-blur md:hidden">
          <div className="flex items-center justify-between px-4 py-3">
            <div className="flex items-center gap-3">
              <img src={torLogo} alt="Tor Tecnologias" className="h-10 w-10 rounded-2xl object-cover ring-1 ring-azure/40" />
              <div>
                <p className="font-display text-sm font-black text-white">Tor Tecnologias</p>
                <p className="text-[10px] font-mono uppercase tracking-[0.24em] text-azure-glow">Portal de Licitacoes</p>
              </div>
            </div>
            <button
              onClick={logout}
              className="rounded-xl border border-slate-border px-3 py-2 text-xs font-semibold text-gray-300"
            >
              Sair
            </button>
          </div>

          <div className="overflow-x-auto px-4 pb-3">
            <div className="flex gap-2">
              {items.map((item) => {
                const active = isActive(location.pathname, item.path)
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-mono uppercase tracking-[0.2em] ${
                      active
                        ? 'border-azure/30 bg-azure/10 text-azure-glow'
                        : 'border-slate-border text-gray-400'
                    }`}
                  >
                    {item.label}
                  </Link>
                )
              })}
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">{children}</main>

        <footer className="border-t border-slate-border bg-ink-100/95 px-4 py-3 text-xs text-gray-500 md:px-6">
          <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
            <p>Tor Tecnologias | Plataforma de analise, RAG e operacao comercial de licitacoes.</p>
            <p>Creditos: Alvaro Sampaio</p>
          </div>
        </footer>
      </div>

      {showChatWidget && <ChatWidget />}
    </div>
  )
}
