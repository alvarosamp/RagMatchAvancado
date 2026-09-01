export default function SectionCard({
  title,
  description,
  action,
  children,
  className = '',
}) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800 ${className}`}>
      {(title || description || action) && (
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            {title && <p className="text-sm font-semibold text-slate-900 dark:text-white">{title}</p>}
            {description && <p className="mt-1 text-xs leading-5 text-slate-500 dark:text-slate-400">{description}</p>}
          </div>
          {action && (
            <button
              type="button"
              onClick={action.onClick}
              className="flex-shrink-0 text-xs font-medium text-slate-400 transition-colors hover:text-slate-700 dark:text-slate-400 dark:hover:text-white"
            >
              {action.label}
            </button>
          )}
        </div>
      )}
      {children}
    </section>
  )
}
