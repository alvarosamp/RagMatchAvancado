// Badges sólidos (não translúcidos no claro) — tons compartilhados por
// categoria/risco/status entre páginas, pra não reinventar cor em cada tela.
const TONE_CLASSES = {
  slate:   'border-slate-200 bg-slate-100 text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300',
  blue:    'border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-300',
  emerald: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300',
  amber:   'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300',
  red:     'border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300',
}

export default function Badge({ tone = 'slate', className = '', children }) {
  return (
    <span className={`inline-flex items-center rounded-md border px-2.5 py-1 text-xs font-medium ${TONE_CLASSES[tone] || TONE_CLASSES.slate} ${className}`}>
      {children}
    </span>
  )
}

export function categoryTone(category) {
  const text = String(category || '').toLowerCase()
  if (text.includes('switch')) return 'blue'
  if (text.includes('access')) return 'emerald'
  if (text.includes('transceiver') || text.includes('modulo')) return 'amber'
  return 'slate'
}

export function riskTone(value) {
  return value && value !== 'Nenhum' ? 'red' : 'emerald'
}
