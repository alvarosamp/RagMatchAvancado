import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { clearPortalSessionStorage } from '../utils/authStorage'
const handlers = vi.hoisted(() => ({}))
vi.mock('axios', () => ({ default: { create: () => ({ interceptors: { response: { use: (success, failure) => { handlers.failure = failure } } } }) } }))
vi.mock('../utils/authStorage', () => ({ clearPortalSessionStorage: vi.fn() }))
import './client'

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { vi.unstubAllGlobals() })

it.each(['/', '/login', '/login/', '/cadastro-tor-gestao-interna', '/esqueci-senha', '/redefinir-senha'])
('keeps public page %s open when the initial session check returns 401', async path => {
  vi.stubGlobal('window', { location: { pathname: path, href: path } })
  const error = { response: { status: 401 }, config: { url: '/auth/me' } }
  await expect(handlers.failure(error)).rejects.toBe(error)
  expect(clearPortalSessionStorage).toHaveBeenCalledOnce()
  expect(window.location.href).toBe(path)
})
it('redirects an expired session on a protected page to login', async () => {
  vi.stubGlobal('window', { location: { pathname: '/dashboard', href: '/dashboard' } })
  const error = { response: { status: 401 }, config: { url: '/analysis/documents' } }
  await expect(handlers.failure(error)).rejects.toBe(error)
  expect(window.location.href).toBe('/login')
})
it('preserves login errors and non-authentication server errors for the caller', async () => {
  vi.stubGlobal('window', { location: { pathname: '/dashboard', href: '/dashboard' } })
  for (const error of [{ response: { status: 401 }, config: { url: '/auth/login' } }, { response: { status: 500 }, config: { url: '/analysis/documents' } }]) {
    await expect(handlers.failure(error)).rejects.toBe(error)
    expect(window.location.href).toBe('/dashboard')
  }
})
