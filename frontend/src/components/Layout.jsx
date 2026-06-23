import { Link, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import torLogo from '../images/Tor.jpeg'
import { persistTheme, readStoredTheme } from '../utils/themeStorage'

const NAV = [
  { path: '/dashboard', badge: 'DB', label: 'Inicio', hint: 'Resumo e proximas acoes' },
  { path: '/upload', badge: 'UP', label: 'Enviar edital', hint: 'PDF ou planilha' },
  { path: '/crm', badge: 'CRM', label: 'CRM comercial', hint: 'Funil, itens e disputa' },
  { path: '/pncp', badge: 'PN', label: 'Buscar PNCP', hint: 'Novas oportunidades' },
  { path: '/controle', badge: 'CT', label: 'Controle', hint: 'Acompanhar processos' },
  { path: '/relatorios', badge: 'RP', label: 'Relatorios', hint: 'Resumo executivo' },
  { path: '/analytics', badge: 'AN', label: 'Indicadores', hint: 'Resultado e desempenho' },
  { path: '/jobs', badge: 'JB', label: 'Fila', hint: 'Processamentos' },
  { path: '/configuracoes', badge: 'CFG', label: 'Ajustes', hint: 'Preferencias' },
]

const NAV_ADMIN = [
  { path: '/usuarios', badge: 'USR', label: 'Usuarios', hint: 'Acessos do time' },
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
    case 'RP':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="8" y1="13" x2="16" y2="13" />
          <line x1="8" y1="17" x2="14" y2="17" />
          <line x1="8" y1="9" x2="10" y2="9" />
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
          ? 'border-red-200 bg-red-50 text-red-900 shadow-sm dark:border-azure/35 dark:bg-azure/10 dark:text-white dark:shadow-lg dark:shadow-azure/5'
          : 'border-transparent text-stone-600 hover:border-stone-200 hover:bg-white hover:text-stone-950 dark:text-gray-400 dark:hover:border-slate-border/50 dark:hover:bg-slate-hover dark:hover:text-white'
      }`}
    >
      <div
        className={`grid h-10 w-10 place-items-center rounded-xl border transition-all ${
          active
            ? 'border-red-200 bg-white text-red-700 dark:border-azure/30 dark:bg-azure/20 dark:text-azure-glow'
            : 'border-stone-200 bg-white text-stone-500 group-hover:text-red-700 dark:border-slate-border dark:bg-ink-50 dark:text-gray-500 dark:group-hover:text-white'
        }`}
      >
        {renderIcon(item.badge)}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">{item.label}</p>
        <p className="truncate text-xs text-stone-400 dark:text-gray-500">{item.hint}</p>
      </div>
      {active && <div className="h-2 w-2 rounded-full bg-red-500 dark:bg-azure-glow" />}
    </Link>
  )
}

export default function Layout({ children }) {
  const { user, logout, isAdmin } = useAuth()
  const location = useLocation()
  const [theme, setTheme] = useState(() => readStoredTheme())
  const isLight = theme === 'light'

  const items = isAdmin ? [...NAV, ...NAV_ADMIN] : NAV

  useEffect(() => {
    persistTheme(theme)
    document.documentElement.classList.toggle('light', isLight)
    document.documentElement.classList.toggle('dark', !isLight)
    document.body.classList.toggle('theme-light', isLight)
  }, [theme, isLight])

  return (
    <div className="min-h-screen bg-[#f6f1ea] text-stone-950 md:flex dark:bg-ink dark:text-white">
      <aside className="hidden w-72 flex-shrink-0 flex-col border-r border-stone-200 bg-[#fbf8f3]/95 md:flex dark:border-slate-border dark:bg-ink-100/95">
        <div className="border-b border-stone-200 px-5 py-5 dark:border-slate-border">
          <div className="flex items-center gap-3">
            <img
              src={torLogo}
              alt="Tor Tecnologias"
              className="h-11 w-11 flex-shrink-0 rounded-2xl object-cover ring-1 ring-white/10"
            />
            <div className="leading-tight">
              <p className="text-base font-semibold text-stone-950 dark:text-white">Tor Tecnologias</p>
              <p className="text-xs text-stone-500 dark:text-gray-500">Portal de licitacoes</p>
            </div>
          </div>

          <div className="mt-5 rounded-3xl border border-stone-200 bg-white px-4 py-4 shadow-sm dark:border-slate-border dark:bg-ink-50/80">
            <p className="text-xs font-medium text-stone-500 dark:text-gray-500">Ambiente de trabalho</p>
            <p className="mt-2 truncate text-sm font-semibold text-stone-950 dark:text-white">{user?.tenant?.name || 'Ambiente Tor'}</p>
            <p className="mt-1 truncate text-xs text-stone-500 dark:text-gray-500">{user?.email || 'sem email informado'}</p>
          </div>
        </div>

        <nav className="flex-1 space-y-2 overflow-y-auto px-4 py-5">
          {items.map((item) => (
            <NavItem key={item.path} item={item} pathname={location.pathname} />
          ))}
        </nav>

        <div className="border-t border-stone-200 px-4 py-4 dark:border-slate-border">
          <button
            onClick={() => setTheme(isLight ? 'dark' : 'light')}
            className="mb-3 flex w-full items-center justify-center rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm font-semibold text-stone-700 transition-colors hover:border-red-200 hover:text-red-700 dark:border-slate-border dark:bg-ink-50 dark:text-gray-300 dark:hover:border-azure/40 dark:hover:text-white"
          >
            {isLight ? 'Usar modo escuro' : 'Usar modo claro'}
          </button>
          <button
            onClick={logout}
            className="flex w-full items-center justify-center rounded-2xl border border-stone-200 bg-transparent px-4 py-3 text-sm font-semibold text-stone-500 transition-colors hover:border-red-200 hover:bg-red-50 hover:text-red-700 dark:border-slate-border dark:text-gray-300 dark:hover:border-red-fail/40 dark:hover:text-red-fail"
          >
            Encerrar sessao
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-stone-200 bg-[#fbf8f3]/95 backdrop-blur md:hidden dark:border-slate-border dark:bg-ink-100/95">
          <div className="flex items-center justify-between px-4 py-3">
            <div className="flex items-center gap-3">
              <img src={torLogo} alt="Tor Tecnologias" className="h-10 w-10 rounded-2xl object-cover ring-1 ring-white/10" />
              <div>
                <p className="text-sm font-semibold text-stone-950 dark:text-white">Tor Tecnologias</p>
                <p className="text-[11px] text-stone-500 dark:text-gray-500">Portal de licitacoes</p>
              </div>
            </div>
            <button
              onClick={() => setTheme(isLight ? 'dark' : 'light')}
              className="rounded-xl border border-stone-200 bg-white px-3 py-2 text-xs font-semibold text-stone-600 dark:border-slate-border dark:bg-ink-50 dark:text-gray-300"
            >
              {isLight ? 'Escuro' : 'Claro'}
            </button>
            <button
              onClick={logout}
              className="rounded-xl border border-stone-200 bg-white px-3 py-2 text-xs font-semibold text-stone-600 dark:border-slate-border dark:bg-ink-50 dark:text-gray-300"
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
                        ? 'border-red-200 bg-red-50 text-red-800 dark:border-azure/30 dark:bg-azure/10 dark:text-azure-glow'
                        : 'border-stone-200 bg-white text-stone-500 dark:border-slate-border dark:bg-ink-50 dark:text-gray-400'
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

        <footer className="border-t border-stone-200 bg-[#fbf8f3]/80 px-4 py-3 text-xs text-stone-500 md:px-6 dark:border-slate-border dark:bg-ink-100/95 dark:text-gray-500">
          <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
            <p>Tor Tecnologias | Portal operacional de licitacoes.</p>
            <p>Captar, analisar, disputar e acompanhar em um lugar.</p>
          </div>
        </footer>
      </div>
    </div>
  )
}
