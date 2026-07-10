import { formatNumber } from './format'

export function MetricRow({ label, value, max }) {
  const numericValue = Number(value || 0)
  const width = max > 0 ? Math.max(2, (numericValue / max) * 100) : 0
  return (
    <div className="grid grid-cols-[150px_1fr_52px] items-center gap-3">
      <span className="truncate text-sm text-slate-700 dark:text-slate-300" title={label}>{label}</span>
      <div className="h-2 rounded bg-slate-100 dark:bg-slate-700">
        <div className="h-2 rounded bg-brand dark:bg-brand-light" style={{ width: `${width}%` }} />
      </div>
      <span className="text-right text-sm text-slate-700 dark:text-slate-300">{formatNumber(value)}</span>
    </div>
  )
}

export function BreakdownGroup({ title, rows }) {
  if (!rows?.length) return null
  const max = Math.max(...rows.map((row) => Number(row.unidades || 0)))
  return (
    <div>
      <h4 className="mb-3 text-sm font-semibold text-slate-950 dark:text-white">{title}</h4>
      <div className="space-y-3">
        {rows.slice(0, 5).map((row) => (
          <MetricRow key={row.valor || row.uf} label={row.valor || row.uf} value={row.unidades} max={max} />
        ))}
      </div>
    </div>
  )
}
