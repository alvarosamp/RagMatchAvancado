export const BRASILIA_TIME_ZONE = 'America/Sao_Paulo'

function parseBackendDate(value) {
  if (!value) return null
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value
  const raw = String(value).trim()
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return new Date(`${raw}T12:00:00-03:00`)
  const hasOffset = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(raw)
  const date = new Date(hasOffset ? raw : `${raw}Z`)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatBrasiliaDateTime(value, fallback = '—', options = {}) {
  const date = parseBackendDate(value)
  if (!date) return fallback
  return date.toLocaleString('pt-BR', {
    timeZone: BRASILIA_TIME_ZONE,
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
    ...options,
  })
}

export function formatBrasiliaDate(value, fallback = '—', options = {}) {
  const date = parseBackendDate(value)
  if (!date) return fallback
  return date.toLocaleDateString('pt-BR', {
    timeZone: BRASILIA_TIME_ZONE,
    day: '2-digit', month: '2-digit', year: 'numeric',
    ...options,
  })
}

export function formatBrasiliaTime(value, fallback = '—', options = {}) {
  const date = parseBackendDate(value)
  if (!date) return fallback
  return date.toLocaleTimeString('pt-BR', {
    timeZone: BRASILIA_TIME_ZONE,
    hour: '2-digit', minute: '2-digit',
    ...options,
  })
}
