const THEME_KEY = 'edital-matcher-ui-theme'
const LEGACY_THEME_KEY = 'tor-ui-theme'

export function readStoredTheme(defaultTheme = 'light') {
  if (typeof window === 'undefined') return defaultTheme
  const value = window.localStorage.getItem(THEME_KEY) || window.localStorage.getItem(LEGACY_THEME_KEY)
  return value === 'light' || value === 'dark' ? value : defaultTheme
}

export function persistTheme(theme) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(THEME_KEY, theme)
  window.localStorage.removeItem(LEGACY_THEME_KEY)
}

export { THEME_KEY }
