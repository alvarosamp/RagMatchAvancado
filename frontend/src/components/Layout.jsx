import { Link, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useMarket } from '../contexts/MarketContext'
import torLogo from '../images/Tor.jpeg'
import { persistTheme, readStoredTheme } from '../utils/themeStorage'

const NAV = [
  { key: 'dashboard', path: '/dashboard', badge: 'DB' },
  { key: 'suite', path: '/suite', badge: 'ST' },
  { key: 'pncp_monitor', path: '/monitoramento-pncp', badge: '24' },
  { key: 'upload', path: '/upload', badge: 'UP' },
  { key: 'radar', path: '/radar', badge: 'RD' },
  { key: 'proposal_studio', path: '/propostas', badge: 'DC' },
  { key: 'compliance', path: '/habilitacao', badge: 'CK' },
  { key: 'pricing', path: '/precificacao', badge: 'PR' },
  { key: 'auction_monitor', path: '/monitor-pregao', badge: 'PG' },
  { key: 'bid_robot', path: '/robo-lances', badge: 'LB' },
  { key: 'crm', path: '/crm/', badge: 'CRM' },
  { key: 'post_award', path: '/pos-vitoria', badge: 'PV' },
  { key: 'controle', path: '/controle', badge: 'CT' },
  { key: 'reports', path: '/relatorios', badge: 'RP' },
  { key: 'analytics', path: '/analytics', badge: 'AN' },
  { key: 'analysis_dashboard', path: '/analise/dashboard', badge: 'BI' },
  { key: 'datasheets', path: '/inteligencia/datasheets', badge: 'VS' },
  { key: 'competitive', path: '/inteligencia/competitiva', badge: 'CI' },
  { key: 'jobs', path: '/jobs', badge: 'JB' },
  { key: 'onboarding_plans', path: '/onboarding-planos', badge: 'ON' },
  { key: 'subscription', path: '/assinatura', badge: 'SB' },
  { key: 'integrations', path: '/integracoes', badge: 'IN' },
  { key: 'settings', path: '/configuracoes', badge: 'CFG' },
]

const NAV_ADMIN = [
  { key: 'users', path: '/usuarios', badge: 'USR' },
]

const AI_FEATURES_ENABLED = import.meta.env.VITE_AI_FEATURES_ENABLED === '1'
const AI_NAV_KEYS = new Set(['analysis_dashboard', 'datasheets', 'competitive', 'jobs'])

const NAV_STRUCTURE = [
  { type: 'item', key: 'dashboard' },
  { type: 'group', title: 'Oportunidades', keys: ['pncp_monitor', 'radar'] },
  { type: 'item', key: 'upload' },
  { type: 'item', key: 'crm' },
  { type: 'group', title: 'Analise', keys: ['analysis_dashboard', 'datasheets', 'competitive'] },
  { type: 'group', title: 'Proposta', keys: ['proposal_studio', 'compliance', 'pricing', 'subscription'] },
  { type: 'group', title: 'Disputa', keys: ['auction_monitor', 'bid_robot', 'controle'] },
  { type: 'group', title: 'Comercial', keys: ['post_award', 'reports', 'analytics'] },
  { type: 'group', title: 'Sistema', keys: ['suite', 'jobs', 'onboarding_plans', 'integrations', 'settings'] },
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
    case 'RD':
    case '24':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
          {(badge === 'RD' || badge === '24') && <path d="M11 7v4l3 2" />}
        </svg>
      );
    case 'DC':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <path d="M14 2v6h6" />
          <path d="M8 13h8" />
          <path d="M8 17h6" />
        </svg>
      );
    case 'CK':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <path d="M9 11l3 3L22 4" />
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
        </svg>
      );
    case 'PR':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <path d="M12 1v22" />
          <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7H14a3.5 3.5 0 0 1 0 7H6" />
        </svg>
      );
    case 'PG':
    case 'LB':
      return (
        <svg {...props} viewBox="0 0 24 24">
          {badge === 'PG' ? (
            <>
              <path d="M14 9V5a3 3 0 0 0-6 0v4" />
              <rect x="4" y="9" width="16" height="12" rx="2" />
              <path d="M9 15h6" />
            </>
          ) : (
            <>
              <path d="M12 3v18" />
              <path d="M7 8h7.5a2.5 2.5 0 0 1 0 5H9.5a2.5 2.5 0 0 0 0 5H17" />
              <path d="M4 21h16" />
            </>
          )}
        </svg>
      );
    case 'PV':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <path d="M20 6L9 17l-5-5" />
          <path d="M4 21h16" />
        </svg>
      );
    case 'ON':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <path d="M12 2v20" />
          <path d="M5 9h14" />
          <path d="M7 4h10" />
          <path d="M7 20h10" />
        </svg>
      );
    case 'IN':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
        </svg>
      );
    case 'SB':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <rect x="3" y="5" width="18" height="14" rx="2" />
          <path d="M3 10h18" />
          <path d="M7 15h4" />
          <path d="M15 15h2" />
        </svg>
      );
    case 'ST':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <path d="M4 5h16" />
          <path d="M4 12h16" />
          <path d="M4 19h16" />
          <circle cx="7" cy="5" r="1" />
          <circle cx="12" cy="12" r="1" />
          <circle cx="17" cy="19" r="1" />
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
    case 'VS':
    case 'CI':
      return (
        <svg {...props} viewBox="0 0 24 24">
          {badge === 'VS' ? (
            <>
              <path d="M8 3v18" />
              <path d="M16 3v18" />
              <path d="M3 8h5" />
              <path d="M16 8h5" />
              <path d="M3 16h5" />
              <path d="M16 16h5" />
            </>
          ) : (
            <>
              <path d="M3 17l6-6 4 4 8-8" />
              <path d="M14 7h7v7" />
              <path d="M3 21h18" />
            </>
          )}
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
  const className = `group flex items-center gap-3 rounded-lg border px-3 py-2.5 transition-colors duration-150 ${
    active
      ? 'border-blue-200 bg-blue-50 text-blue-950 dark:border-blue-800 dark:bg-blue-950/30 dark:text-white'
      : 'border-transparent text-slate-600 hover:border-slate-200 hover:bg-white hover:text-slate-950 dark:text-slate-400 dark:hover:border-slate-700 dark:hover:bg-slate-800 dark:hover:text-white'
  }`
  const content = (
    <>
      <div
        className={`grid h-10 w-10 flex-shrink-0 place-items-center rounded-lg border transition-colors ${
          active
            ? 'border-blue-200 bg-white text-brand dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-300'
            : 'border-slate-200 bg-white text-slate-500 group-hover:text-brand dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500 dark:group-hover:text-white'
        }`}
      >
        {renderIcon(item.badge)}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">{item.label}</p>
        <p className="truncate text-xs text-slate-400 dark:text-slate-500">{item.hint}</p>
      </div>
      {active && <div className="h-2 w-2 flex-shrink-0 rounded-full bg-brand dark:bg-brand-light" />}
    </>
  )

  if (item.key === 'crm') {
    return (
      <a href={item.path} className={className}>
        {content}
      </a>
    )
  }

  return (
    <Link to={item.path} className={className}>
      {content}
    </Link>
  )
}

function NavGroup({ group, itemsByKey, pathname }) {
  const groupItems = group.keys.map((key) => itemsByKey.get(key)).filter(Boolean)
  if (groupItems.length === 0) return null

  const active = groupItems.some((item) => isActive(pathname, item.path))

  return (
    <details className="group/nav rounded-lg" open={active}>
      <summary className={`flex cursor-pointer list-none items-center justify-between rounded-lg px-3 py-2 text-xs font-semibold uppercase tracking-wide transition-colors ${
        active
          ? 'bg-blue-50 text-blue-800 dark:bg-blue-950/30 dark:text-blue-300'
          : 'text-slate-400 hover:bg-slate-50 hover:text-slate-600 dark:text-slate-500 dark:hover:bg-slate-800 dark:hover:text-slate-300'
      }`}>
        <span>{group.title}</span>
        <span className="text-sm transition-transform group-open/nav:rotate-90">›</span>
      </summary>
      <div className="mt-2 space-y-2 pl-2">
        {groupItems.map((item) => (
          <NavItem key={item.path} item={item} pathname={pathname} />
        ))}
      </div>
    </details>
  )
}

export default function Layout({ children }) {
  const { user, logout, isAdmin } = useAuth()
  const market = useMarket()
  const location = useLocation()
  const [theme, setTheme] = useState(() => readStoredTheme())
  const isLight = theme === 'light'

  const baseItems = (isAdmin ? [...NAV, ...NAV_ADMIN] : NAV).filter(
    (item) => AI_FEATURES_ENABLED || !AI_NAV_KEYS.has(item.key)
  )
  const items = baseItems.map((item) => ({
    ...item,
    label: market.nav?.[item.key]?.label || item.key,
    hint: market.nav?.[item.key]?.hint || '',
  }))
  const itemsByKey = new Map(items.map((item) => [item.key, item]))
  const navStructure = isAdmin
    ? [...NAV_STRUCTURE, { type: 'group', title: 'Admin', keys: ['users'] }]
    : NAV_STRUCTURE

  useEffect(() => {
    persistTheme(theme)
    document.documentElement.classList.toggle('light', isLight)
    document.documentElement.classList.toggle('dark', !isLight)
    document.body.classList.toggle('theme-light', isLight)
  }, [theme, isLight])

  return (
    <div className="min-h-screen bg-surface text-slate-950 dark:bg-surface-dark dark:text-white md:flex">
      <aside className="hidden w-72 flex-shrink-0 flex-col border-r border-slate-200 bg-white md:flex dark:border-slate-700 dark:bg-slate-900">
        <div className="border-b border-slate-200 px-5 py-5 dark:border-slate-700">
          <div className="flex items-center gap-3">
            <img
              src={torLogo}
              alt="Tor Tecnologias"
              className="h-11 w-11 flex-shrink-0 rounded-lg object-cover"
            />
            <div className="leading-tight">
              <p className="text-base font-semibold text-slate-950 dark:text-white">{market.app.product_name}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">{market.app.tagline}</p>
            </div>
          </div>

          <div className="mt-5 rounded-lg border border-slate-200 bg-white px-4 py-4 dark:border-slate-700 dark:bg-slate-800">
            <p className="text-xs font-medium text-slate-500 dark:text-slate-400">Ambiente de trabalho</p>
            <p className="mt-2 truncate text-sm font-semibold text-slate-950 dark:text-white">{user?.tenant?.name || 'Ambiente Tor'}</p>
            <p className="mt-1 truncate text-xs text-slate-500 dark:text-slate-400">{user?.email || 'sem email informado'}</p>
          </div>
        </div>

        <nav className="flex-1 space-y-3 overflow-y-auto px-4 py-5">
          {navStructure.map((entry) => {
            if (entry.type === 'item') {
              const item = itemsByKey.get(entry.key)
              return item ? <NavItem key={item.path} item={item} pathname={location.pathname} /> : null
            }
            return <NavGroup key={entry.title} group={entry} itemsByKey={itemsByKey} pathname={location.pathname} />
          })}
        </nav>

        <div className="border-t border-slate-200 px-4 py-4 dark:border-slate-700">
          <button
            onClick={() => setTheme(isLight ? 'dark' : 'light')}
            className="mb-3 flex w-full items-center justify-center rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition-colors hover:border-blue-200 hover:text-brand dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-blue-800 dark:hover:text-white"
          >
            {isLight ? 'Usar modo escuro' : 'Usar modo claro'}
          </button>
          <button
            onClick={logout}
            className="flex w-full items-center justify-center rounded-lg border border-slate-200 bg-transparent px-4 py-3 text-sm font-semibold text-slate-500 transition-colors hover:border-blue-200 hover:bg-blue-50 hover:text-brand dark:border-slate-700 dark:text-slate-300 dark:hover:border-blue-800 dark:hover:text-blue-300"
          >
            Encerrar sessao
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-slate-200 bg-white md:hidden dark:border-slate-700 dark:bg-slate-900">
          <div className="flex items-center justify-between px-4 py-3">
            <div className="flex items-center gap-3">
              <img src={torLogo} alt="Tor Tecnologias" className="h-10 w-10 rounded-lg object-cover" />
              <div>
                <p className="text-sm font-semibold text-slate-950 dark:text-white">{market.app.product_name}</p>
                <p className="text-[11px] text-slate-500 dark:text-slate-400">{market.app.tagline}</p>
              </div>
            </div>
            <button
              onClick={() => setTheme(isLight ? 'dark' : 'light')}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
            >
              {isLight ? 'Escuro' : 'Claro'}
            </button>
            <button
              onClick={logout}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
            >
              Sair
            </button>
          </div>

          <div className="overflow-x-auto px-4 pb-3">
            <div className="flex gap-2">
              {items.map((item) => {
                const active = isActive(location.pathname, item.path)
                const className = `whitespace-nowrap rounded-md border px-3 py-1.5 text-xs font-medium ${
                  active
                    ? 'border-blue-200 bg-blue-50 text-blue-900 dark:border-blue-800 dark:bg-blue-950/30 dark:text-blue-300'
                    : 'border-slate-200 bg-white text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400'
                }`
                if (item.key === 'crm') {
                  return (
                    <a key={item.path} href={item.path} className={className}>
                      {item.label}
                    </a>
                  )
                }
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={className}
                  >
                    {item.label}
                  </Link>
                )
              })}
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">{children}</main>

        <footer className="border-t border-slate-200 bg-white px-4 py-3 text-xs text-slate-500 md:px-6 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
          <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
            <p>{market.app.footer_primary}</p>
            <p>{market.app.footer_secondary}</p>
          </div>
        </footer>
      </div>
    </div>
  )
}
