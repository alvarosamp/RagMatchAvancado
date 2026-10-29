import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import WhatsAppSettings from './WhatsAppSettings'
import { whatsappApi } from '../api/client'

vi.mock('../api/client', () => ({ whatsappApi: {
  status: vi.fn(), link: vi.fn(), unlink: vi.fn(), preferences: vi.fn(), test: vi.fn(),
} }))

let root, container
beforeEach(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  vi.resetAllMocks()
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})
afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  delete globalThis.IS_REACT_ACT_ENVIRONMENT
})
async function render(status) {
  whatsappApi.status.mockResolvedValue({ data: status })
  await act(async () => root.render(<WhatsAppSettings />))
}
async function click(label) {
  const button = [...container.querySelectorAll('button')].find(el => el.textContent === label)
  expect(button).toBeTruthy()
  await act(async () => button.click())
}

it('explains that the service is not activated and identifies the provider', async () => {
  await render({ configured: false, linked: false })
  expect(container.textContent).toContain('ainda não foi ativado')
  expect(container.textContent).toContain('Evolution API')
  expect(container.querySelector('button')).toBeNull()
})

it('requires WhatsApp confirmation before showing a linked account', async () => {
  await render({ configured: true, linked: false })
  whatsappApi.link.mockResolvedValue({ data: { url: 'https://wa.me/5511999990000?text=VINCULAR', message: 'VINCULAR abc' } })
  await click('Vincular meu WhatsApp')
  expect(container.textContent).toContain('VINCULAR abc')
  expect(container.textContent).toContain('10 minutos')
  expect(container.textContent).not.toContain('Vinculado ao número')
  whatsappApi.status.mockResolvedValue({ data: { configured: true, linked: true, phone_suffix: '1111', notifications_enabled: false } })
  await click('Já enviei, verificar vínculo')
  expect(container.textContent).toContain('final 1111')
  expect(container.querySelector('input[type=checkbox]').checked).toBe(false)
  expect(container.textContent).not.toContain('VINCULAR abc')
})

it('updates explicit consent, sends a test and unlinks', async () => {
  await render({ configured: true, linked: true, phone_suffix: '2222', notifications_enabled: false })
  whatsappApi.preferences.mockResolvedValue({ data: { notifications_enabled: true } })
  whatsappApi.status.mockResolvedValue({ data: { configured: true, linked: true, phone_suffix: '2222', notifications_enabled: true } })
  await act(async () => container.querySelector('input').click())
  expect(whatsappApi.preferences).toHaveBeenCalledWith({ notifications_enabled: true })
  await click('Enviar resumo de teste')
  expect(whatsappApi.test).toHaveBeenCalledOnce()
  whatsappApi.status.mockResolvedValue({ data: { configured: true, linked: false } })
  await click('Desvincular')
  expect(whatsappApi.unlink).toHaveBeenCalledOnce()
  expect(container.textContent).toContain('ainda não está vinculado')
})

it('shows service errors without confirming a delivery', async () => {
  await render({ configured: true, linked: true, phone_suffix: '2222', notifications_enabled: false })
  whatsappApi.test.mockRejectedValue({ response: { data: { detail: 'Não foi possível enviar pelo WhatsApp.' } } })
  await click('Enviar resumo de teste')
  expect(container.querySelector('[role=alert]').textContent).toContain('Não foi possível enviar')
  expect(container.textContent).not.toContain('Resumo enviado')
})
