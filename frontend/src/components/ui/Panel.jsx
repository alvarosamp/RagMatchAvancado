export function Panel({ children, className = '' }) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800 ${className}`}>
      {children}
    </section>
  )
}

export function PanelHeader({ children, className = '' }) {
  return (
    <div className={`mb-4 flex items-start justify-between gap-4 ${className}`}>
      {children}
    </div>
  )
}

export function PanelTitle({ children, className = '' }) {
  return <p className={`text-sm font-semibold text-slate-900 dark:text-white ${className}`}>{children}</p>
}
