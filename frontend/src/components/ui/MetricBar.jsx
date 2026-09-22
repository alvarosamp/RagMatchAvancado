import { formatNumber } from './format'

export function MetricRow({ label, value, max, detail }) {
  const numericValue = Number(value || 0)
  const width = max > 0 ? Math.max(2, (numericValue / max) * 100) : 0
  return (
    <div className="grid grid-cols-[minmax(120px,1fr)_minmax(70px,1fr)_58px] items-center gap-3">
      <span className="min-w-0 truncate text-sm text-slate-700 dark:text-slate-300" title={detail || label}>{label}</span>
      <div className="h-2 rounded bg-slate-100 dark:bg-slate-700">
        <div className="h-2 rounded bg-brand dark:bg-brand-light" style={{ width: `${width}%` }} />
      </div>
      <span className="text-right text-sm text-slate-700 dark:text-slate-300">{formatNumber(value)}</span>
    </div>
  )
}

export function BreakdownGroup({ title, rows, metric = 'unidades' }) {
  if (!rows?.length) return null
  const ranked = [...rows].sort((a, b) => Number(b[metric] || 0) - Number(a[metric] || 0))
  const max = Math.max(...ranked.map((row) => Number(row[metric] || 0)))
  return (
    <div>
      <h4 className="mb-3 text-sm font-semibold text-slate-950 dark:text-white">{title}</h4>
      <div className="space-y-3">
        {ranked.slice(0, 5).map((row) => (
          <MetricRow
            key={row.valor || row.uf}
            label={row.valor || row.uf}
            value={row[metric] ?? row.unidades}
            max={max}
            detail={row.itens == null ? null : `${row.valor}: ${formatNumber(row.editais)} editais, ${formatNumber(row.itens)} itens, ${formatNumber(row.unidades)} unidades`}
          />
        ))}
      </div>
    </div>
  )
}
