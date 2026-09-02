import { cn } from '../../utils/cn'

export default function Card({ className = '', children, ...props }) {
  return (
    <div
      className={cn('rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800', className)}
      {...props}
    >
      {children}
    </div>
  )
}
