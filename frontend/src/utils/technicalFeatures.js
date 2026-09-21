export function flattenTechnicalFeatures(value, prefix = '') {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return []

  return Object.entries(value).flatMap(([key, nested]) => {
    const path = prefix ? `${prefix}.${key}` : key
    if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
      return flattenTechnicalFeatures(nested, path)
    }
    if (nested == null || nested === '' || nested === 'N/C') return []
    return [{ path, label: key.replace(/_/g, ' '), value: String(nested) }]
  })
}

export function summarizeTechnicalFeatures(value, limit = 6) {
  return flattenTechnicalFeatures(value)
    .slice(0, limit)
    .map(({ value: featureValue }) => featureValue)
    .join(' / ')
}
