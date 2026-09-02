import Badge from './Badge'

export default function SuiteCard({
  title,
  description,
  cta,
  status,
  tone = 'slate',
  onClick,
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex h-full flex-col rounded-lg border border-slate-200 bg-slate-50 p-4 text-left transition-colors hover:border-blue-200 hover:bg-blue-50 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-blue-800 dark:hover:bg-slate-800"
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-semibold text-slate-950 dark:text-white">{title}</p>
        {status && <Badge tone={tone}>{status}</Badge>}
      </div>
      <p className="mt-3 flex-1 text-sm leading-6 text-slate-500 dark:text-slate-400">{description}</p>
      {cta && <span className="mt-4 text-sm font-semibold text-blue-700 transition-colors group-hover:text-blue-900 dark:text-blue-300 dark:group-hover:text-blue-200">{cta}</span>}
    </button>
  )
}
