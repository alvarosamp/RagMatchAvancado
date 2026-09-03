import Badge from './Badge'

const STATUS_TONES = {
  ok: 'emerald',
  success: 'emerald',
  available: 'emerald',
  pending: 'amber',
  warning: 'amber',
  attention: 'red',
  error: 'red',
  neutral: 'slate',
  info: 'blue',
}

export default function StatusBadge({ status = 'neutral', children, className = '' }) {
  return (
    <Badge tone={STATUS_TONES[status] || 'slate'} className={className}>
      {children}
    </Badge>
  )
}
