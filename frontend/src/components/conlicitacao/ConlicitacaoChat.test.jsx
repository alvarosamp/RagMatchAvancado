// @vitest-environment jsdom
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { expect, it, vi } from 'vitest'
import { ChatTab } from './ConlicitacaoLab'

vi.mock('../../contexts/ToastContext', () => ({ useToast: () => ({ toast: vi.fn() }) }))
vi.mock('../../api/client', () => ({ conlicitacaoApi: {
  labMonitored: vi.fn(async () => ({ data: { data: { electronics_trading: [] } } })),
  labMessages: vi.fn(async () => ({ data: { data: { trading_messages: [
    { id: 1, lot: 0, message_highlight: 'Aviso geral' },
    { id: 2, lot: 12, message_highlight: 'Convocação minha' },
    { id: 3, lot: 13, message_highlight: 'Convocação de outro item' },
  ] } } })),
} }))

it('renders focused chat and lets the user select a lot or inspect all messages', async () => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  try {
    await act(async () => root.render(<ChatTab watchId={123} />))
    expect(container.textContent).toContain('Aviso geral')
    expect(container.textContent).not.toContain('Convocação minha')
    const input = container.querySelector('input[placeholder="Ex.: 12, 15, 20"]')
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '12')
      input.dispatchEvent(new Event('input', { bubbles: true }))
    })
    expect(container.textContent).toContain('Convocação minha')
    expect(container.textContent).not.toContain('Convocação de outro item')
    expect(container.textContent).toContain('2 de 3 mensagens carregadas visíveis')
    await act(async () => {
      const checkbox = [...container.querySelectorAll('input[type="checkbox"]')].find(el => el.parentElement.textContent.includes('Mostrar também'))
      checkbox.click()
    })
    expect(container.textContent).toContain('Convocação de outro item')
  } finally {
    await act(async () => root.unmount())
    container.remove()
    delete globalThis.IS_REACT_ACT_ENVIRONMENT
  }
})
