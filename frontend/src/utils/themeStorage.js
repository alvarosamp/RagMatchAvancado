const THEME_KEY = 'tor-ui-theme'

export function readStoredTheme(defaultTheme = 'dark') {
  if (typeof window === 'undefined') return defaultTheme
  const value = window.localStorage.getItem(THEME_KEY)
  return value === 'light' ? 'light' : defaultTheme
}

export function persistTheme(theme) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(THEME_KEY, theme)
}

export { THEME_KEY }
