import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import Login from './Login'
import ForgotPassword from './ForgotPassword'
import ResetPassword from './ResetPassword'

const calls = vi.hoisted(() => ({ login: vi.fn(), navigate: vi.fn(), request: vi.fn(), confirm: vi.fn() }))
vi.mock('react-router-dom', () => ({
  Link: ({ children, to }) => <a href={to}>{children}</a>,
  useNavigate: () => calls.navigate,
  useSearchParams: () => [new URLSearchParams(window.location.search)],
}))
vi.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ login: calls.login }) }))
vi.mock('../contexts/MarketContext', () => ({ useMarket: () => ({ app: { product_name: 'QA', tagline: 'Portal', description: 'QA', footer_secondary: 'QA' } }) }))
vi.mock('../api/client', () => ({ authApi: { requestPasswordReset: calls.request, confirmPasswordReset: calls.confirm } }))

let root, container
beforeEach(() => {
  vi.resetAllMocks()
  window.history.replaceState({}, '', '/login')
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
})
afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
  localStorage.clear()
  delete globalThis.IS_REACT_ACT_ENVIRONMENT
})
async function render(Component) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => root.render(<Component />))
  return container
}
async function fill(selector, value) {
  const element = container.querySelector(selector)
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(element, value)
    element.dispatchEvent(new Event('input', { bubbles: true }))
  })
}
async function submit() {
  await act(async () => container.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })))
}

it('login normalizes email and navigates only after authentication succeeds', async () => {
  calls.login.mockResolvedValue({ id: 1 })
  await render(Login)
  await fill('input[type=email]', 'Admin@EXAMPLE.com')
  await fill('input[type=password]', 'Password-2026!')
  await submit()
  expect(calls.login).toHaveBeenCalledWith('admin@example.com', 'Password-2026!')
  expect(calls.navigate).toHaveBeenCalledWith('/dashboard')
})
it.each([403, 429, 500])('login displays API failure %s without navigating', async status => {
  calls.login.mockRejectedValue({ response: { status, data: { detail: `Falha ${status}` } } })
  await render(Login)
  await submit()
  expect(container.textContent).toContain(`Falha ${status}`)
  expect(calls.navigate).not.toHaveBeenCalled()
  expect(container.querySelector('button[type=submit]').disabled).toBe(false)
})
it('login prevents duplicate submissions while the request is pending', async () => {
  let resolve
  calls.login.mockImplementation(() => new Promise(done => { resolve = done }))
  await render(Login)
  await submit()
  expect(container.querySelector('button[type=submit]').disabled).toBe(true)
  expect(container.textContent).toContain('Entrando...')
  await act(async () => resolve({ id: 1 }))
  expect(container.querySelector('button[type=submit]').disabled).toBe(false)
})
it('password recovery displays generic confirmation and disables another request', async () => {
  calls.request.mockResolvedValue({ data: { message: 'Se o e-mail estiver cadastrado, enviaremos as instrucoes.' } })
  await render(ForgotPassword)
  await fill('input[type=email]', 'USER@EXAMPLE.com')
  await submit()
  expect(calls.request).toHaveBeenCalledWith({ email: 'user@example.com' })
  expect(container.textContent).toContain('Se o e-mail estiver cadastrado')
  expect(container.querySelector('button[type=submit]').disabled).toBe(true)
})
it('password recovery network failure permits retry', async () => {
  calls.request.mockRejectedValue(new Error('offline'))
  await render(ForgotPassword)
  await submit()
  expect(container.textContent).toContain('Nao foi possivel processar')
  expect(container.querySelector('button[type=submit]').disabled).toBe(false)
})
it('password reset cannot send mismatching confirmation', async () => {
  window.history.replaceState({}, '', '/redefinir-senha?token=quality-token')
  await render(ResetPassword)
  await fill('input[autocomplete=new-password]', 'Another-Quality-2026!')
  await submit()
  expect(calls.confirm).not.toHaveBeenCalled()
  expect(container.textContent).toMatch(/coincidem|iguais|confirma/i)
})
it('password reset sends the token and renders success', async () => {
  window.history.replaceState({}, '', '/redefinir-senha?token=quality-token')
  calls.confirm.mockResolvedValue({ data: { message: 'Senha redefinida.' } })
  await render(ResetPassword)
  const inputs = container.querySelectorAll('input[type=password]')
  // Inputs belong to separate labels, so address each through its label.
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
    for (const input of inputs) { setter.call(input, 'Another-Quality-2026!'); input.dispatchEvent(new Event('input', { bubbles: true })) }
  })
  await submit()
  expect(calls.confirm).toHaveBeenCalledWith({ token: 'quality-token', new_password: 'Another-Quality-2026!' })
  expect(container.textContent).toContain('Senha redefinida')
})
