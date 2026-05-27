import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import torLogo from '../images/Tor.jpeg'

const NAV = [
  { path: '/dashboard', badge: 'DB', label: 'Dashboard', hint: 'Visao geral do sistema' },
  { path: '/upload', badge: 'UP', label: 'Novo edital', hint: 'Entrada e processamento' },
  { path: '/pncp', badge: 'PN', label: 'PNCP', hint: 'Busca e importacao publica' },
  { path: '/controle', badge: 'CT', label: 'Controle', hint: 'Operacao e acompanhamento' },
  { path: '/analytics', badge: 'AN', label: 'Analise', hint: 'Performance e inteligencia' },
  { path: '/jobs', badge: 'JB', label: 'Jobs', hint: 'Fila e processamento' },
  { path: '/crm', badge: 'CRM', label: 'CRM', hint: 'Oportunidades e operacao comercial' },
  { path: '/configuracoes', badge: 'CFG', label: 'Configuracoes', hint: 'Ajustes do ambiente' },
]

const NAV_ADMIN = [
  { path: '/usuarios', badge: 'USR', label: 'Usuarios', hint: 'Gestao de acessos' },
]

function isActive(pathname, path) {
  return pathname === path || pathname.startsWith(`${path}/`)
}

function renderIcon(badge) {
  const props = { className: "h-5 w-5 stroke-current", fill: "none", stroke: "currentColor", strokeWidth: "2", strokeLinecap: "round", strokeLinejoin: "round" };
  switch (badge) {
    case 'DB':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <rect x="3" y="3" width="7" height="9" rx="1" />
          <rect x="14" y="3" width="7" height="5" rx="1" />
          <rect x="14" y="12" width="7" height="9" rx="1" />
          <rect x="3" y="16" width="7" height="5" rx="1" />
        </svg>
      );
    case 'UP':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
      );
    case 'PN':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      );
    case 'CT':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <path d="M12 20h9" />
          <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
        </svg>
      );
    case 'AN':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <line x1="18" y1="20" x2="18" y2="10" />
          <line x1="12" y1="20" x2="12" y2="4" />
          <line x1="6" y1="20" x2="6" y2="14" />
        </svg>
      );
    case 'JB':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
      );
    case 'CRM':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
          <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
        </svg>
      );
    case 'CFG':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      );
    case 'USR':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
          <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
      );
    default:
      return badge;
  }
}

function NavItem({ item, pathname }) {
  const active = isActive(pathname, item.path)

  return (
    <Link
      to={item.path}
      className={`group flex items-center gap-3 rounded-2xl border px-3 py-2.5 transition-all duration-200 ${
        active
          ? 'border-azure/35 bg-azure/10 text-white shadow-lg shadow-azure/5'
          : 'border-transparent text-gray-400 hover:border-slate-border/50 hover:bg-slate-hover hover:text-white'
      }`}
    >
      <div
        className={`grid h-10 w-10 place-items-center rounded-xl border transition-all ${
          active
            ? 'border-azure/30 bg-azure/20 text-azure-glow'
            : 'border-slate-border bg-ink-50 text-gray-500 group-hover:text-white'
        }`}
      >
        {renderIcon(item.badge)}
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

  return (
    <div className="min-h-screen bg-ink text-white md:flex">
      <aside className="hidden w-72 flex-shrink-0 flex-col border-r border-slate-border bg-ink-100/95 md:flex">
        <div className="border-b border-slate-border px-5 py-5">
          <div className="flex items-center gap-3">
            <img
              src={torLogo}
              alt="Tor Tecnologias"
              className="h-11 w-11 flex-shrink-0 rounded-2xl object-cover ring-1 ring-white/10"
            />
            <div className="leading-tight">
              <p className="text-base font-semibold text-white">Tor Tecnologias</p>
              <p className="text-xs text-gray-500">Portal de Licitacoes</p>
            </div>
          </div>

          <div className="mt-5 rounded-2xl border border-slate-border bg-ink-50/80 px-4 py-4">
            <p className="text-xs font-medium text-gray-500">Empresa</p>
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
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-slate-border bg-ink-100/95 backdrop-blur md:hidden">
          <div className="flex items-center justify-between px-4 py-3">
            <div className="flex items-center gap-3">
              <img src={torLogo} alt="Tor Tecnologias" className="h-10 w-10 rounded-2xl object-cover ring-1 ring-white/10" />
              <div>
                <p className="text-sm font-semibold text-white">Tor Tecnologias</p>
                <p className="text-[11px] text-gray-500">Portal de Licitacoes</p>
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
                    className={`whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-medium ${
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
            <p>Tor Tecnologias | Operacao de licitacoes e CRM.</p>
            <p>Ambiente interno unificado.</p>
          </div>
        </footer>
      </div>
    </div>
  )
}
