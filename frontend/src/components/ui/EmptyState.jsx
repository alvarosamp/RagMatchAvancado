import Button from './Button'

export default function EmptyState({
  title,
  description,
  action,
  icon,
  className = '',
}) {
  return (
    <div className={`rounded-xl border border-dashed border-slate-200 bg-slate-50 px-5 py-10 text-center dark:border-slate-700 dark:bg-slate-900 ${className}`}>
      {icon && (
        <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-xl border border-slate-200 bg-white text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
          {icon}
        </div>
      )}
      <p className="text-base font-semibold text-slate-900 dark:text-white">{title}</p>
      {description && (
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">{description}</p>
      )}
      {action && (
        <Button className="mt-4" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  )
}
