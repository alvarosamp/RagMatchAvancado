import { describe, expect, it, vi } from 'vitest'
import { copyJsonToClipboard, filenameFromDisposition, stringifyExportJson } from './jsonExport'

describe('jsonExport', () => {
  it('serializes readable JSON without losing accents', () => {
    expect(stringifyExportJson({ descricao: 'Módulo óptico' })).toContain('Módulo óptico')
  })

  it('copies exactly the serialized payload', async () => {
    const clipboard = { writeText: vi.fn().mockResolvedValue(undefined) }
    const text = await copyJsonToClipboard({ item: 67 }, clipboard)
    expect(clipboard.writeText).toHaveBeenCalledWith(text)
    expect(JSON.parse(text)).toEqual({ item: 67 })
  })

  it('extracts the server filename', () => {
    expect(filenameFromDisposition('attachment; filename="match_pe-16_item_67.json"', 'item.json'))
      .toBe('match_pe-16_item_67.json')
  })
})
