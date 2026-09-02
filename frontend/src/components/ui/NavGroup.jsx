import NavItem, { isActive } from './NavItem'

export default function NavGroup({ group, itemsByKey, pathname, onNavigate }) {
  const groupItems = group.keys.map((key) => itemsByKey.get(key)).filter(Boolean)
  if (groupItems.length === 0) return null

  const active = groupItems.some((item) => isActive(pathname, item.path))

  return (
    <details className="group/nav rounded-lg" open={active}>
      <summary className={`flex cursor-pointer list-none items-center justify-between rounded-lg px-3 py-2 text-xs font-semibold transition-colors ${
        active
          ? 'bg-blue-50 text-blue-800 dark:bg-blue-950/30 dark:text-blue-300'
          : 'text-slate-400 hover:bg-slate-50 hover:text-slate-600 dark:text-slate-500 dark:hover:bg-slate-800 dark:hover:text-slate-300'
      }`}>
        <span>{group.title}</span>
        <span className="text-sm transition-transform group-open/nav:rotate-90">›</span>
      </summary>
      <div className="mt-1.5 space-y-1.5 pl-2">
        {groupItems.map((item) => (
          <NavItem key={item.path} item={item} pathname={pathname} onNavigate={onNavigate} />
        ))}
      </div>
    </details>
  )
}
