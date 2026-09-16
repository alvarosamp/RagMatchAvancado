import { beforeEach, describe, expect, it } from 'vitest'

import { clearCrmSessionStorage, clearPortalSessionStorage } from './authStorage'

describe('authentication storage cleanup', () => {
  beforeEach(() => window.localStorage.clear())

  it('removes only Supabase CRM authentication keys', () => {
    window.localStorage.setItem('sb-project-auth-token', 'crm-token')
    window.localStorage.setItem('unrelated', 'keep-me')

    clearCrmSessionStorage()

    expect(window.localStorage.getItem('sb-project-auth-token')).toBeNull()
    expect(window.localStorage.getItem('unrelated')).toBe('keep-me')
  })

  it('clears portal and CRM sessions while preserving unrelated data', () => {
    window.localStorage.setItem('access_token', 'portal-token')
    window.localStorage.setItem('tenant_slug', 'tenant')
    window.localStorage.setItem('user_role', 'admin')
    window.localStorage.setItem('sb-project-auth-token', 'crm-token')
    window.localStorage.setItem('theme', 'dark')

    clearPortalSessionStorage()

    expect(window.localStorage.getItem('access_token')).toBeNull()
    expect(window.localStorage.getItem('tenant_slug')).toBeNull()
    expect(window.localStorage.getItem('user_role')).toBeNull()
    expect(window.localStorage.getItem('sb-project-auth-token')).toBeNull()
    expect(window.localStorage.getItem('theme')).toBe('dark')
  })
})
