import { Link } from 'react-router-dom'

function isActive(pathname, path) {
  return pathname === path || pathname.startsWith(`${path}/`)
}

export default function NavItem({ item, pathname, onNavigate }) {
  const active = isActive(pathname, item.path)
  const Icon = item.icon
  const className = `group flex items-center gap-3 rounded-lg border px-3 py-2 transition-colors duration-150 ${
    active
      ? 'border-blue-200 bg-blue-50 text-blue-950 shadow-sm dark:border-blue-800 dark:bg-blue-950/30 dark:text-white'
      : 'border-transparent text-slate-600 hover:border-slate-200 hover:bg-white hover:text-slate-950 dark:text-slate-400 dark:hover:border-slate-700 dark:hover:bg-slate-800 dark:hover:text-white'
  }`

  const content = (
    <>
      <div
        className={`grid h-9 w-9 flex-shrink-0 place-items-center rounded-lg border transition-colors ${
          active
            ? 'border-blue-200 bg-white text-brand dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-300'
            : 'border-slate-200 bg-white text-slate-500 group-hover:text-brand dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500 dark:group-hover:text-white'
        }`}
      >
        {Icon ? <Icon className="h-5 w-5" aria-hidden="true" /> : item.badge}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">{item.label}</p>
        {active && item.hint && <p className="truncate text-[11px] text-slate-400 dark:text-slate-500">{item.hint}</p>}
      </div>
    </>
  )

  if (item.external) {
    return (
      <a href={item.path} className={className} onClick={onNavigate}>
        {content}
      </a>
    )
  }

  return (
    <Link to={item.path} className={className} onClick={onNavigate}>
      {content}
    </Link>
  )
}

export { isActive }
