// @vitest-environment node

import { describe, expect, it } from 'vitest'

import { clearCrmSessionStorage, clearPortalSessionStorage } from './authStorage'
import { persistTheme, readStoredTheme } from './themeStorage'

describe('storage helpers during server-side rendering', () => {
  it('does not access browser storage when window is unavailable', () => {
    expect(() => clearCrmSessionStorage()).not.toThrow()
    expect(() => clearPortalSessionStorage()).not.toThrow()
    expect(() => persistTheme('dark')).not.toThrow()
    expect(readStoredTheme('dark')).toBe('dark')
  })
})
