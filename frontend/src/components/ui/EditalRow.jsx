import StatusBadge from './StatusBadge'

function formatDate(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function RowAction({ children, danger = false, ...props }) {
  return (
    <button
      type="button"
      className={`rounded-lg border border-slate-200 px-2.5 py-1.5 font-mono text-[11px] transition-colors disabled:opacity-40 dark:border-slate-700 ${
        danger
          ? 'text-slate-400 hover:bg-red-50 hover:text-red-700 dark:text-slate-400 dark:hover:bg-red-950/40 dark:hover:text-red-300'
          : 'text-slate-400 hover:bg-white hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-700 dark:hover:text-white'
      }`}
      {...props}
    >
      {children}
    </button>
  )
}

export default function EditalRow({
  edital,
  onClick,
  onChat,
  onAnalysis,
  onExportXlsx,
  onExportCsv,
  onDelete,
  exporting,
  deleting,
  aiEnabled,
  isEditor,
}) {
  return (
    <div
      onClick={onClick}
      className="group/row flex cursor-pointer items-center gap-4 rounded-lg border border-slate-100 bg-slate-50 px-4 py-3 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:hover:bg-slate-700"
    >
      <div className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
        <span className="text-[9px] font-bold text-slate-400 dark:text-slate-400">PDF</span>
      </div>

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-900 dark:text-white">{edital.filename}</p>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <StatusBadge status={(edital.requirements || 0) > 0 ? 'ok' : 'pending'}>
            {(edital.requirements || 0) > 0 ? `${edital.requirements} requisitos` : 'Aguardando análise'}
          </StatusBadge>
          {edital.parsed_at && <span className="text-xs text-slate-400 dark:text-slate-400">{formatDate(edital.parsed_at)}</span>}
        </div>
      </div>

      <div
        className="flex flex-shrink-0 items-center gap-1.5 opacity-100 transition-opacity md:opacity-0 md:group-hover/row:opacity-100 md:group-focus-within/row:opacity-100"
        onClick={(event) => event.stopPropagation()}
      >
        {aiEnabled && (
          <>
            <RowAction onClick={onChat}>Chat</RowAction>
            <RowAction onClick={onAnalysis}>Análise</RowAction>
          </>
        )}
        <RowAction onClick={onExportXlsx} disabled={Boolean(exporting)}>
          {exporting === `${edital.id}-xlsx` ? '…' : 'XLSX'}
        </RowAction>
        <RowAction onClick={onExportCsv} disabled={Boolean(exporting)}>
          {exporting === `${edital.id}-csv` ? '…' : 'CSV'}
        </RowAction>
        {isEditor && (
          <RowAction danger onClick={onDelete} disabled={deleting === edital.id}>
            {deleting === edital.id ? '...' : 'Apagar'}
          </RowAction>
        )}
      </div>
    </div>
  )
}
