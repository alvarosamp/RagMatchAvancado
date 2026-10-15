import { expect, it } from 'vitest'
import { buildTenderExport, tenderExportJson } from './conlicitacaoTenderExport'

const preview = { bulletin_id: 10, opportunity: { external_id: '19399420', opening_at: '2026-10-07T08:00:00', documents: [{ filename: 'edital.pdf', index: 2 }] } }
const source = { id: 19399420, edital: 'PE/20/2026', objeto: 'Equipamentos', processo: '123/2026', valor_estimado: 0, orgao: { nome: 'Prefeitura', cidade: 'Apiacás', uf: 'MT', codigo: '001' }, item: 'Itens publicados', documento: [{ url: 'https://provider/?auth=private' }], documentos: [{ filename: 'edital.pdf', index: 2 }] }

it('reuses CRM fields while preserving original process and item data', () => {
  const exported = buildTenderExport(preview, source)
  expect(exported.edital).toMatchObject({ number: 'PE/20/2026', title: 'Equipamentos', municipality_name: 'Apiacás', state: 'MT', uasg: '001', estimated_value: 0 })
  expect(exported.provider_data).toMatchObject({ processo: '123/2026', item: 'Itens publicados' })
  expect(exported.campos_nao_informados).toContain('modality')
  expect(exported.documentos[0].index).toBe(2)
  expect(tenderExportJson(preview, source)).not.toContain('private')
  expect(source.documento).toHaveLength(1)
})
it('rejects missing original data rather than exporting an empty report', () => {
  expect(() => buildTenderExport(preview, null)).toThrow('indisponíveis')
})
