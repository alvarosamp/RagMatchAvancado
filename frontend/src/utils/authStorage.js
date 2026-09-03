const PORTAL_AUTH_KEYS = ['access_token', 'tenant_slug', 'user_role', 'demo_mode']
const CRM_AUTH_KEY_PATTERN = /^sb-.*-auth-token/

export function clearCrmSessionStorage() {
  if (typeof window === 'undefined') return

  Object.keys(window.localStorage).forEach((key) => {
    if (CRM_AUTH_KEY_PATTERN.test(key)) {
      window.localStorage.removeItem(key)
    }
  })
}

export function clearPortalSessionStorage() {
  if (typeof window === 'undefined') return

  PORTAL_AUTH_KEYS.forEach((key) => window.localStorage.removeItem(key))
  clearCrmSessionStorage()
}
