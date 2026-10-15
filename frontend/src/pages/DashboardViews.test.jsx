// @vitest-environment jsdom
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, expect, it, vi } from 'vitest'
import Dashboard from './Dashboard'
import Analytics from './Analytics'
import AnalysisDashboard from './AnalysisDashboard'
import CompetitiveIntelligence from './CompetitiveIntelligence'

const api = vi.hoisted(() => ({ get: vi.fn(), dashboard: vi.fn(), list: vi.fn(), competitors: vi.fn() }))
vi.mock('react-router-dom', () => ({ useNavigate: () => vi.fn() }))
vi.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ user: { tenant: { name: 'Empresa Teste' } }, isEditor: true }) }))
vi.mock('../contexts/MarketContext', () => ({ useMarket: () => ({ labels: {} }) }))
vi.mock('../contexts/ToastContext', () => ({ useToast: () => ({ toast: vi.fn(), confirm: vi.fn() }) }))
vi.mock('../api/client', () => ({
 default: { get: api.get }, downloadBlob: vi.fn(),
 documentsApi: { signatureAlert: async () => ({ data: { count: 1 } }) },
 editaisApi: { list: api.list },
 opsApi: { summary: async () => ({ data: { crm: { active_pipeline: 2, attention_required: 1 }, jobs: { stale_count: 0 } } }) },
 analysisApi: { dashboard: api.dashboard, editaisListagem: api.list },
 datasheetsApi: { competitiveIntelligence: api.competitors },
}))
let root, container
async function render(Component) {
 globalThis.IS_REACT_ACT_ENVIRONMENT = true
 container = document.createElement('div'); document.body.appendChild(container)
 root = createRoot(container)
 await act(async () => root.render(<Component />))
 return container
}
afterEach(async () => {
 if (root) await act(async () => root.unmount())
 container?.remove(); root = null
 vi.restoreAllMocks(); vi.unstubAllGlobals()
 delete globalThis.IS_REACT_ACT_ENVIRONMENT
})
it('dashboard displays operational alerts and uploaded documents', async () => {
 vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false })))
 api.list.mockResolvedValue({ data: [{ id: 1, filename: 'Edital teste', requirements: 4 }] })
 const view = await render(Dashboard)
 expect(view.textContent).toContain('Olá, Empresa')
 expect(view.textContent).toContain('Edital teste')
 expect(view.textContent).toContain('aguardando assinatura')
 expect(view.textContent).toContain('disputa pedindo atenção')
})
it('product analytics renders populated API contracts including histogram and evolution', async () => {
 const data = {
  overview: { total_editais: 1, total_matchings: 2, score_medio: .8, taxa_atendimento: .5, melhor_produto: 'Switch teste' },
  produtos: [{ produto: 'Switch teste', score_medio: .8 }],
  requisitos: [{ requisito: 'PoE', taxa_falha: .5 }],
  evolucao: [{ edital_id: 1, data: '2026-10-09', score_medio: .8 }],
  distribuicao: { buckets: [{ faixa: '80-90%', count: 2, pct: 1 }], total: 2 },
 }
 api.get.mockImplementation(async url => ({ data: data[url.split('/').at(-1)] }))
 const view = await render(Analytics)
 expect(view.textContent).toContain('Switch teste')
 expect(view.textContent).toContain('80%')
 expect(view.textContent).toContain('PoE')
 expect(view.querySelector('svg path')).not.toBeNull()
})
it('product analytics reports request failures without showing a false empty state', async () => {
 api.get.mockRejectedValue(new Error('offline'))
 const view = await render(Analytics)
 expect(view.textContent).toContain('Erro ao carregar dados')
 expect(view.textContent).not.toContain('Nenhum dado de matching ainda')
})
it('analysis dashboard renders the object and complete item description', async () => {
 api.dashboard.mockResolvedValue({ data: { kpis: {}, categories: [] } })
 api.list.mockResolvedValue({ data: [{ id: 1, numero_pregao: 'PE 123', objeto: 'Aquisição de equipamentos', items: [{ description: 'Switch 48 portas', categoria: 'Switch', quantity: 2 }] }] })
 const view = await render(AnalysisDashboard)
 expect(view.textContent).toContain('Aquisição de equipamentos')
 expect(view.textContent).toContain('PE 123')
})
it('competitive intelligence expands comparisons and requests selected category', async () => {
 api.competitors.mockResolvedValue({ data: { summary: { competitor_products: 1 }, competitors: [{ competitor: { id: 1, model: 'Concorrente teste', category: 'Switch' }, history: { suppliers: ['Fornecedor A'] }, best_own_counters: [{ product_id: 2, model: 'Produto próprio', score: 80, advantages: 1, disadvantages: 0, ties: 0 }] }] } })
 const view = await render(CompetitiveIntelligence)
 await act(async () => [...view.querySelectorAll('button')].find(b => b.textContent.includes('Concorrente teste')).click())
 expect(view.textContent).toContain('Produto próprio')
 expect(view.textContent).toContain('Fornecedor A')
 await act(async () => { const s = view.querySelector('select'); s.value = 'Switch'; s.dispatchEvent(new Event('change', { bubbles: true })) })
 await act(async () => [...view.querySelectorAll('button')].find(b => b.textContent.includes('Atualizar')).click())
 expect(api.competitors).toHaveBeenLastCalledWith({ category: 'Switch' })
})
