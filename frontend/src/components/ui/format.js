export function formatNumber(value) {
  return Number(value || 0).toLocaleString('pt-BR', { maximumFractionDigits: 0 })
}

export function formatMoney(value) {
  return Number(value || 0).toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    notation: Number(value || 0) >= 1000000 ? 'compact' : 'standard',
    maximumFractionDigits: Number(value || 0) >= 1000000 ? 1 : 2,
  })
}

export function compactDescription(text, max = 86) {
  const value = String(text || '').replace(/\s+/g, ' ').trim()
  return value.length > max ? `${value.slice(0, max - 1)}...` : value
}
