export function parseSelectedLots(value) {
  const parts = String(value).trim().split(/[,;\s]+/).filter(Boolean)
  const valid = parts.every(part => /^\d+$/.test(part) && Number.isSafeInteger(Number(part)) && Number(part) > 0)
  return { valid, lots: valid ? [...new Set(parts.map(Number))] : [] }
}

export function classifyChatMessage(message) {
  const lot = Number(message.lot)
  if (Number.isSafeInteger(lot) && lot > 0) return { kind: 'lot', lots: [lot] }
  // Only explicit references: never treat dates, amounts or process numbers as lots.
  const text = String(message.message_highlight || '')
  // Ranges are ambiguous; keep the message instead of hiding a relevant item.
  if (/\b(?:itens|item|lotes|lote)\s+\d+\s*(?:a|até|-)\s*\d+/i.test(text)) return { kind: 'unassigned', lots: [] }
  const matches = [...text.matchAll(/\b(?:itens|item|lotes|lote)\s*(?:n[º°o.]?\s*)?[:#-]?\s*(\d+(?:\s*(?:,|;|\be\b)\s*\d+)*)/gi)]
  const lots = [...new Set(matches.flatMap(match => match[1].match(/\d+/g).map(Number)).filter(number => number > 0))]
  if (lots.length) return { kind: 'text', lots }
  return { kind: 'unassigned', lots: [] }
}

export function filterChatMessages(messages, selectedLots, showAll = false) {
  const selected = new Set(selectedLots)
  return messages.filter(message => {
    if (showAll) return true
    const classification = classifyChatMessage(message)
    return classification.kind === 'unassigned' || classification.lots.some(lot => selected.has(lot))
  })
}
