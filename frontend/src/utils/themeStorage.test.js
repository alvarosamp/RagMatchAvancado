import { beforeEach, describe, expect, it } from 'vitest'

import { persistTheme, readStoredTheme, THEME_KEY } from './themeStorage'

describe('theme storage', () => {
  beforeEach(() => window.localStorage.clear())

  it('returns the default when there is no valid stored theme', () => {
    expect(readStoredTheme('dark')).toBe('dark')
    window.localStorage.setItem(THEME_KEY, 'unexpected')
    expect(readStoredTheme('light')).toBe('light')
  })

  it('migrates a valid legacy theme on the next write', () => {
    window.localStorage.setItem('tor-ui-theme', 'dark')
    expect(readStoredTheme()).toBe('dark')

    persistTheme('light')

    expect(window.localStorage.getItem(THEME_KEY)).toBe('light')
    expect(window.localStorage.getItem('tor-ui-theme')).toBeNull()
  })
})
