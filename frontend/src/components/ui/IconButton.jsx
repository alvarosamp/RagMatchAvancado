import Button from './Button'

export default function IconButton({ label, children, className = '', ...props }) {
  return (
    <Button
      variant="ghost"
      size="sm"
      className={`h-9 w-9 p-0 ${className}`}
      aria-label={label}
      title={label}
      {...props}
    >
      {children}
    </Button>
  )
}
