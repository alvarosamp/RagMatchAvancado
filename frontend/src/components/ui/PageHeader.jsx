import Button from './Button'

export default function PageHeader({
  eyebrow,
  title,
  description,
  primaryAction,
  secondaryAction,
  children,
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800 lg:p-6">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-2xl">
          {eyebrow && (
            <p className="text-sm text-slate-500 dark:text-slate-400">{eyebrow}</p>
          )}
          <h1 className="text-2xl font-bold tracking-tight text-slate-950 dark:text-white">
            {title}
          </h1>
          {description && (
            <p className="mt-3 max-w-xl text-sm leading-6 text-slate-500 dark:text-slate-400">
              {description}
            </p>
          )}
        </div>

        {(primaryAction || secondaryAction) && (
          <div className="flex flex-col gap-2 sm:flex-row lg:flex-col xl:flex-row">
            {secondaryAction && (
              <Button variant="ghost" onClick={secondaryAction.onClick}>
                {secondaryAction.label}
              </Button>
            )}
            {primaryAction && (
              <Button onClick={primaryAction.onClick}>
                {primaryAction.label}
              </Button>
            )}
          </div>
        )}
      </div>

      {children && <div className="mt-6">{children}</div>}
    </section>
  )
}
