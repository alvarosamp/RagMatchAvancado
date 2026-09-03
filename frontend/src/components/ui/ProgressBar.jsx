export default function ProgressBar({ value = 0, className = '' }) {
  const safeValue = Math.max(0, Math.min(100, Number(value) || 0))

  return (
    <div className={`h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700 ${className}`}>
      <div className="h-full rounded-full bg-brand transition-all duration-500" style={{ width: `${safeValue}%` }} />
    </div>
  )
}
