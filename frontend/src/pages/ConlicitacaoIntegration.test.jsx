// @vitest-environment jsdom
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { conlicitacaoApi } from '../api/client'
import ConlicitacaoIntegration from './ConlicitacaoIntegration'

vi.mock('../api/client', () => ({ conlicitacaoApi: { status: vi.fn() } }))
vi.mock('../contexts/ToastContext', () => ({
  useToast: () => ({ toast: vi.fn(), confirm: vi.fn() }),
}))
vi.mock('../components/conlicitacao/ConlicitacaoLab', () => ({
  default: ({ enabled }) => <div>Laboratório: {enabled ? 'disponível' : 'indisponível'}</div>,
}))

describe('ConlicitacaoIntegration rendering', () => {
  let container
  let root

  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    vi.clearAllMocks()
  })

  afterEach(async () => {
    await act(async () => root.unmount())
    container.remove()
    delete globalThis.IS_REACT_ACT_ENVIRONMENT
  })

  async function renderPage() {
    await act(async () => {
      root.render(<MemoryRouter><ConlicitacaoIntegration /></MemoryRouter>)
    })
  }

  it('opens with read-only access even when synchronization is unauthorized', async () => {
    conlicitacaoApi.status.mockResolvedValue({ data: {
      enabled: true, configured: true, read_only_available: true, authorized: false,
    } })
    await renderPage()
    expect(container.textContent).toContain('Laboratório ConLicitação')
    expect(container.textContent).toContain('Download e exportação: sim')
    expect(container.textContent).toContain('Sincronização autorizada: não')
    expect(container.textContent).toContain('Teste: baixar edital e exportar dados')
    expect(container.textContent).not.toContain('Importação manual')
    expect(conlicitacaoApi.status).toHaveBeenCalledOnce()
  })

  it('keeps the page visible when configuration is unavailable', async () => {
    conlicitacaoApi.status.mockResolvedValue({ data: {
      enabled: false, configured: false, authorized: false,
    } })
    await renderPage()
    expect(container.textContent).toContain('Laboratório ConLicitação')
    expect(container.textContent).toContain('Download e exportação: não')
    expect(container.textContent).toContain('CONLICITACAO_ENABLED=1')
  })

  it('keeps the page visible when the status API fails', async () => {
    conlicitacaoApi.status.mockRejectedValue(new Error('Unavailable'))
    await renderPage()
    expect(container.textContent).toContain('Laboratório ConLicitação')
    expect(container.textContent).not.toContain('Consultando...')
  })
})
