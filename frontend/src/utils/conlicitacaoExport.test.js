import { expect, it, vi } from 'vitest'
import { collectConlicitacaoExport, conlicitacaoExportJson } from './conlicitacaoExport'

const response = data => Promise.resolve({ data: { data } })
it('collects every page, deduplicates bulletins and includes chat messages', async () => {
  const api = {
    labFilters: () => response({ filtros: [{ id: 1 }] }),
    labUsers: () => response({ users: [] }),
    labBulletins: vi.fn((id, { page }) => response({ filtro: { total_boletins: 101 }, boletins: [{ id: page }] })),
    labBulletin: vi.fn(id => response({ boletim: { id }, licitacoes: [], acompanhamentos: [] })),
    labMonitored: () => response({ electronics_trading: [{ bidding_id: 9 }], total_pages: 1 }),
    labMessages: () => response({ trading_messages: [{ id: 5 }], pagination: { total_pages: 1 } }),
  }
  const result = await collectConlicitacaoExport(api)
  expect(result.complete).toBe(true)
  expect(api.labBulletins).toHaveBeenCalledTimes(2)
  expect(api.labBulletin).toHaveBeenCalledTimes(2)
  expect(result.responses.at(-1).response.data.trading_messages[0].id).toBe(5)
})
it('exports a partial report with failures instead of claiming completeness', async () => {
  const result = await collectConlicitacaoExport({ labFilters: () => Promise.reject(new Error('error')), labUsers: () => response({ users: [] }), labMonitored: () => response({ electronics_trading: [] }) })
  expect(result.complete).toBe(false)
  expect(result.errors[0].endpoint).toBe('filters')
  expect(conlicitacaoExportJson({ token: 'secret', objeto: 'dados reais' })).not.toContain('secret')
})
