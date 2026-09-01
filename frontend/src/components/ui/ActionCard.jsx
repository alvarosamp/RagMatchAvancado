import Badge from './Badge'

const TONE_CLASSES = {
  blue: 'border-blue-200 bg-blue-50 hover:bg-blue-100 dark:border-blue-800 dark:bg-blue-950/30 dark:hover:bg-blue-950/50',
  emerald: 'border-emerald-200 bg-emerald-50 hover:bg-emerald-100 dark:border-emerald-800 dark:bg-emerald-950/30 dark:hover:bg-emerald-950/50',
  amber: 'border-amber-200 bg-amber-50 hover:bg-amber-100 dark:border-amber-800 dark:bg-amber-950/30 dark:hover:bg-amber-950/50',
  slate: 'border-slate-200 bg-white hover:border-blue-200 hover:bg-blue-50/60 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-blue-800 dark:hover:bg-slate-800/80',
}

export default function ActionCard({
  title,
  description,
  cta,
  badge,
  badgeTone = 'slate',
  tone = 'slate',
  icon,
  onClick,
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`group flex h-full flex-col rounded-xl border p-5 text-left transition-colors ${TONE_CLASSES[tone] || TONE_CLASSES.slate}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-base font-semibold text-slate-950 dark:text-white">{title}</p>
          {description && (
            <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">{description}</p>
          )}
        </div>
        {icon && (
          <span className="grid h-10 w-10 flex-shrink-0 place-items-center rounded-lg border border-white/70 bg-white/70 text-slate-700 shadow-sm transition-colors group-hover:text-brand dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-300">
            {icon}
          </span>
        )}
      </div>

      <div className="mt-auto flex items-center justify-between gap-3 pt-5">
        <span className="text-sm font-semibold text-blue-700 dark:text-blue-300">{cta} →</span>
        {badge && <Badge tone={badgeTone}>{badge}</Badge>}
      </div>
    </button>
  )
}
