export function stringifyExportJson(payload) {
  return JSON.stringify(payload, null, 2)
}

export async function copyJsonToClipboard(payload, clipboard = globalThis.navigator?.clipboard) {
  const text = stringifyExportJson(payload)
  if (clipboard?.writeText) {
    await clipboard.writeText(text)
    return text
  }

  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  const copied = document.execCommand('copy')
  textarea.remove()
  if (!copied) throw new Error('Clipboard indisponivel')
  return text
}

export function filenameFromDisposition(disposition, fallback) {
  const utf8 = disposition?.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8) return decodeURIComponent(utf8[1].replace(/["']/g, ''))
  const regular = disposition?.match(/filename="?([^";]+)"?/i)
  return regular?.[1] || fallback
}
