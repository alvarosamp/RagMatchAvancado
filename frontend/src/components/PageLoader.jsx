export default function PageLoader() {
  return (
    <div className="grid min-h-[40vh] place-items-center" role="status" aria-live="polite">
      <div className="flex items-center gap-3 text-sm text-slate-500 dark:text-slate-400">
        <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-brand dark:border-slate-600 dark:border-t-brand-light" />
        <span>Carregando página…</span>
      </div>
    </div>
  )
}
