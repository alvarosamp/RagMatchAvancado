/* Shared by the portal and its compiled CRM. Cookies remain HttpOnly. */
(() => {
  const nativeFetch = window.fetch.bind(window)
  let pending = null
  let stopped = false
  const managed = url => url.origin === location.origin && url.pathname.startsWith('/api/')
  const publicAuth = /\/auth\/(login|register|refresh|logout|password\/reset)(\/|$)/

  async function renew() {
    // Same-origin frames use their parent's flight to prevent cookie races.
    try {
      if (window.parent !== window && window.parent.ragmatchSession) {
        return window.parent.ragmatchSession.refresh()
      }
    } catch { /* standalone frame */ }
    if (stopped) return false
    if (!pending) pending = (async () => {
      const me = await nativeFetch('/api/auth/me', {credentials: 'same-origin', cache: 'no-store'})
      if (me.ok) return true
      if (me.status !== 401) return false
      const response = await nativeFetch('/api/auth/refresh', {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: {'X-Session-Refresh': '1'},
      })
      if (response.status === 401) stopped = true
      if (response.ok) window.dispatchEvent(new Event('ragmatch-session-renewed'))
      return response.ok
    })().finally(() => { pending = null })
    return pending
  }
  window.ragmatchSession = {refresh: renew, resume: () => { stopped = false }, stop: () => { stopped = true }}

  window.fetch = async (input, init) => {
    const request = new Request(input, init)
    const url = new URL(request.url)
    if (!managed(url)) return nativeFetch(request)
    const retry = request.clone()
    const response = await nativeFetch(request)
    if (url.pathname === '/api/auth/logout') stopped = true
    if (response.ok && /\/auth\/(login|register)$/.test(url.pathname)) stopped = false
    if (response.status === 401 && !publicAuth.test(url.pathname) && !request.headers.has('Authorization')) {
      try { if (await renew()) return nativeFetch(retry) } catch { /* preserve original failure */ }
    }
    return response
  }
  // Keep a currently open portal/CRM usable. The database's absolute deadline
  // still ends the session; this timer never creates an unlimited session.
  setInterval(() => { if (!stopped && document.visibilityState === 'visible') renew().catch(() => {}) }, 300000)
  document.addEventListener('visibilitychange', () => {
    if (!stopped && document.visibilityState === 'visible') renew().catch(() => {})
  })
})()
