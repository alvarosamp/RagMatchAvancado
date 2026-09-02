export default function Skeleton({ className = '' }) {
  return <div className={`animate-pulse rounded-lg bg-slate-100 dark:bg-slate-900 ${className}`} />
}

export function EditalSkeleton() {
  return (
    <div className="flex items-center gap-4 rounded-lg border border-slate-100 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-900">
      <Skeleton className="h-8 w-8 flex-shrink-0" />
      <div className="min-w-0 flex-1 space-y-2">
        <Skeleton className="h-3 w-2/3" />
        <Skeleton className="h-3 w-1/3" />
      </div>
      <Skeleton className="hidden h-8 w-24 sm:block" />
    </div>
  )
}
