import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import {
  BadgeCheck,
  BarChart3,
  Bot,
  BrainCircuit,
  BriefcaseBusiness,
  CalendarClock,
  ClipboardCheck,
  CreditCard,
  DatabaseZap,
  FileBarChart,
  FileCheck2,
  FileSearch,
  Gauge,
  LayoutDashboard,
  ListChecks,
  Menu,
  MessageSquareText,
  Search,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Upload,
  Users,
  Workflow,
  Wrench,
} from 'lucide-react'

import { useAuth } from '../contexts/AuthContext'
import { useMarket } from '../contexts/MarketContext'
import { persistTheme, readStoredTheme } from '../utils/themeStorage'
import ProductMark from './ProductMark'
import NavGroup from './ui/NavGroup'
import NavItem from './ui/NavItem'

const NAV = [
  { key: 'dashboard', path: '/dashboard', icon: LayoutDashboard },
  { key: 'suite', path: '/suite', icon: Workflow },
  { key: 'pncp_monitor', path: '/monitoramento-pncp', icon: CalendarClock },
  { key: 'upload', path: '/upload', icon: Upload },
  { key: 'radar', path: '/radar', icon: Search },
  { key: 'proposal_studio', path: '/propostas', icon: FileCheck2 },
  { key: 'compliance', path: '/habilitacao', icon: ShieldCheck },
  { key: 'pricing', path: '/precificacao', icon: BadgeCheck },
  { key: 'auction_monitor', path: '/monitor-pregao', icon: ClipboardCheck },
  { key: 'bid_robot', path: '/robo-lances', icon: Bot },
  { key: 'crm', path: '/crm/', icon: BriefcaseBusiness, external: true },
  { key: 'post_award', path: '/pos-vitoria', icon: ListChecks },
  { key: 'controle', path: '/controle', icon: SlidersHorizontal },
  { key: 'reports', path: '/relatorios', icon: FileBarChart },
  { key: 'analytics', path: '/analytics', icon: BarChart3 },
  { key: 'analysis_dashboard', path: '/analise/dashboard', icon: Gauge },
  { key: 'datasheets', path: '/inteligencia/datasheets', icon: DatabaseZap },
  { key: 'competitive', path: '/inteligencia/competitiva', icon: BrainCircuit },
  { key: 'jobs', path: '/jobs', icon: Wrench },
  { key: 'onboarding_plans', path: '/onboarding-planos', icon: FileSearch },
  { key: 'subscription', path: '/assinatura', icon: CreditCard },
  { key: 'integrations', path: '/integracoes', icon: MessageSquareText },
  { key: 'settings', path: '/configuracoes', icon: Settings },
]

const NAV_ADMIN = [
  { key: 'users', path: '/usuarios', icon: Users },
]

const AI_FEATURES_ENABLED = import.meta.env.VITE_AI_FEATURES_ENABLED === '1'
const AI_NAV_KEYS = new Set(['analysis_dashboard', 'datasheets', 'competitive', 'jobs'])

const NAV_STRUCTURE = [
  { type: 'item', key: 'dashboard' },
  { type: 'item', key: 'radar' },
  { type: 'item', key: 'upload' },
  { type: 'item', key: 'crm' },
  { type: 'group', title: 'Analise', keys: ['analysis_dashboard', 'datasheets', 'competitive', 'pncp_monitor'] },
  { type: 'group', title: 'Disputa', keys: ['auction_monitor', 'bid_robot', 'controle'] },
  { type: 'group', title: 'Documentos', keys: ['proposal_studio', 'compliance', 'pricing', 'subscription', 'reports'] },
  { type: 'group', title: 'Gestao', keys: ['analytics', 'post_award'] },
  { type: 'group', title: 'Administracao', keys: ['settings', 'integrations', 'suite', 'onboarding_plans', 'jobs'] },
]

export default function Layout({ children }) {
  const { user, logout, isAdmin } = useAuth()
  const market = useMarket()
  const location = useLocation()
  const [theme, setTheme] = useState(() => readStoredTheme())
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const isLight = theme === 'light'

  const baseItems = (isAdmin ? [...NAV, ...NAV_ADMIN] : NAV).filter(
    (item) => AI_FEATURES_ENABLED || !AI_NAV_KEYS.has(item.key),
  )
  const items = baseItems.map((item) => ({
    ...item,
    label: market.nav?.[item.key]?.label || item.key,
    hint: market.nav?.[item.key]?.hint || '',
  }))
  const itemsByKey = new Map(items.map((item) => [item.key, item]))
  const navStructure = isAdmin
    ? NAV_STRUCTURE.map((entry) => (
        entry.type === 'group' && entry.title === 'Administracao'
          ? { ...entry, keys: ['users', ...entry.keys] }
          : entry
      ))
    : NAV_STRUCTURE

  useEffect(() => {
    persistTheme(theme)
    document.documentElement.classList.toggle('light', isLight)
    document.documentElement.classList.toggle('dark', !isLight)
    document.body.classList.toggle('theme-light', isLight)
  }, [theme, isLight])

  useEffect(() => {
    setMobileNavOpen(false)
  }, [location.pathname])

  useEffect(() => {
    if (!mobileNavOpen) return undefined
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setMobileNavOpen(false)
    }
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', onKeyDown)
    }
  }, [mobileNavOpen])

  const renderNavigation = (onNavigate) => (
    <nav className="flex-1 space-y-2 overflow-y-auto px-3 py-4" aria-label="Navegação principal">
      {navStructure.map((entry) => {
        if (entry.type === 'item') {
          const item = itemsByKey.get(entry.key)
          return item ? <NavItem key={item.path} item={item} pathname={location.pathname} onNavigate={onNavigate} /> : null
        }
        return <NavGroup key={entry.title} group={entry} itemsByKey={itemsByKey} pathname={location.pathname} onNavigate={onNavigate} />
      })}
    </nav>
  )

  return (
    <div className="min-h-screen bg-surface text-slate-950 dark:bg-surface-dark dark:text-white md:flex">
      <aside className="hidden w-64 flex-shrink-0 flex-col border-r border-slate-200 bg-white md:flex dark:border-slate-700 dark:bg-slate-900">
        <div className="border-b border-slate-200 px-4 py-4 dark:border-slate-700">
          <div className="flex items-center gap-3">
            <ProductMark className="h-10 w-10" title={market.app.product_name} />
            <div className="leading-tight">
              <p className="text-base font-semibold text-slate-950 dark:text-white">{market.app.product_name}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">{market.app.tagline}</p>
            </div>
          </div>

          <div className="mt-4 rounded-lg bg-slate-50 px-3 py-3 dark:bg-slate-800/70">
            <p className="truncate text-sm font-semibold text-slate-950 dark:text-white">{user?.tenant?.name || 'Meu ambiente'}</p>
            <p className="mt-1 truncate text-xs text-slate-500 dark:text-slate-400">{user?.email || 'sem email informado'}</p>
          </div>
        </div>

        {renderNavigation()}

        <div className="border-t border-slate-200 px-3 py-3 dark:border-slate-700">
          <button
            onClick={() => setTheme(isLight ? 'dark' : 'light')}
            className="mb-2 flex w-full items-center justify-center rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm font-semibold text-slate-700 transition-colors hover:border-blue-200 hover:text-brand dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-blue-800 dark:hover:text-white"
          >
            {isLight ? 'Usar modo escuro' : 'Usar modo claro'}
          </button>
          <button
            onClick={logout}
            className="flex w-full items-center justify-center rounded-lg border border-transparent bg-transparent px-3 py-2.5 text-sm font-semibold text-slate-500 transition-colors hover:border-blue-200 hover:bg-blue-50 hover:text-brand dark:text-slate-300 dark:hover:border-blue-800 dark:hover:text-blue-300"
          >
            Encerrar sessao
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-slate-200 bg-white md:hidden dark:border-slate-700 dark:bg-slate-900">
          <div className="flex items-center justify-between px-4 py-3">
            <div className="flex min-w-0 items-center gap-3">
              <ProductMark className="h-10 w-10" title={market.app.product_name} />
              <div>
                <p className="text-sm font-semibold text-slate-950 dark:text-white">{market.app.product_name}</p>
                <p className="text-[11px] text-slate-500 dark:text-slate-400">{market.app.tagline}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setTheme(isLight ? 'dark' : 'light')}
                className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
              >
                {isLight ? 'Escuro' : 'Claro'}
              </button>
              <button
                onClick={() => setMobileNavOpen(true)}
                aria-label="Abrir menu de navegação"
                aria-expanded={mobileNavOpen}
                className="grid h-9 w-9 place-items-center rounded-lg border border-slate-200 bg-white text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              >
                <Menu className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
          </div>
        </header>

        {mobileNavOpen && (
          <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true" aria-label="Menu de navegação">
            <button
              aria-label="Fechar menu"
              className="absolute inset-0 cursor-default bg-slate-950/40"
              onClick={() => setMobileNavOpen(false)}
            />
            <aside className="relative flex h-full w-[min(20rem,86vw)] flex-col border-r border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-900">
              <div className="flex items-center justify-between border-b border-slate-200 px-4 py-4 dark:border-slate-700">
                <p className="text-sm font-semibold text-slate-950 dark:text-white">Navegação</p>
                <button onClick={() => setMobileNavOpen(false)} aria-label="Fechar menu" className="grid h-9 w-9 place-items-center rounded-lg text-xl text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800">×</button>
              </div>
              {renderNavigation(() => setMobileNavOpen(false))}
              <div className="border-t border-slate-200 p-4 dark:border-slate-700">
                <button onClick={logout} className="flex w-full items-center justify-center rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">Encerrar sessão</button>
              </div>
            </aside>
          </div>
        )}

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
