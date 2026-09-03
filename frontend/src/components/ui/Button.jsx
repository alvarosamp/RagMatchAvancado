import { cn } from '../../utils/cn'

const VARIANT_CLASSES = {
  primary: 'border-brand bg-brand text-white hover:bg-brand-dark focus-visible:ring-blue-300 dark:focus-visible:ring-blue-700',
  secondary: 'border-blue-200 bg-blue-50 text-blue-800 hover:bg-blue-100 focus-visible:ring-blue-300 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-200 dark:hover:bg-blue-950/60',
  ghost: 'border-slate-200 bg-white text-slate-700 hover:border-blue-200 hover:bg-blue-50/70 hover:text-slate-950 focus-visible:ring-blue-200 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:border-blue-800 dark:hover:bg-slate-700',
  quiet: 'border-transparent bg-transparent text-slate-500 hover:bg-slate-100 hover:text-slate-900 focus-visible:ring-slate-200 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white',
}

const SIZE_CLASSES = {
  sm: 'px-3 py-2 text-xs',
  md: 'px-4 py-2.5 text-sm',
  lg: 'px-5 py-3 text-sm',
}

export default function Button({
  as: Component = 'button',
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  ...props
}) {
  return (
    <Component
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-lg border font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 disabled:cursor-not-allowed disabled:opacity-50',
        VARIANT_CLASSES[variant] || VARIANT_CLASSES.primary,
        SIZE_CLASSES[size] || SIZE_CLASSES.md,
        className,
      )}
      {...props}
    >
      {children}
    </Component>
  )
}
