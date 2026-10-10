import { describe, expect, it } from 'vitest'
import { classifyChatMessage, filterChatMessages, parseSelectedLots } from './conlicitacaoChatFilter'

describe('focused ConLicitação chat', () => {
  const messages = [
    { id: 1, lot: 0, message_highlight: 'Sessão suspensa até amanhã.' },
    { id: 2, lot: 12, message_highlight: 'Convocação' },
    { id: 3, lot: 13, message_highlight: 'Homologado' },
    { id: 4, lot: null, message_highlight: 'Solicito documentos para o item 12.' },
    { id: 5, lot: null, message_highlight: 'Lote 13 encerrado.' },
    { id: 6, lot: null, message_highlight: 'Prazo 09/10/2026 11:00, valor R$ 100.' },
  ]
  it('shows unassigned messages and only the selected lots', () => {
    expect(filterChatMessages(messages, [12]).map(row => row.id)).toEqual([1, 2, 4, 6])
  })
  it('keeps unidentified messages without guessing from dates or amounts', () => {
    expect(classifyChatMessage(messages[5])).toEqual({ kind: 'unassigned', lots: [] })
    expect(classifyChatMessage({ message_highlight: 'Itens 1 a 10 convocados' }).kind).toBe('unassigned')
    expect(filterChatMessages(messages, []).map(row => row.id)).toEqual([1, 6])
  })
  it('supports multiple explicit item references and gives API lot priority', () => {
    expect(classifyChatMessage({ lot: 0, message_highlight: 'Itens 1, 12 e 15 convocados; lote 20 encerrado.' }).lots).toEqual([1, 12, 15, 20])
    expect(classifyChatMessage({ lot: '9', message_highlight: 'Item 12' }).lots).toEqual([9])
    expect(classifyChatMessage({ lot: null, message_highlight: 'Item nº 12: documentos.' }).lots).toEqual([12])
  })
  it('allows inspection of all messages', () => {
    expect(filterChatMessages(messages, [12], true)).toEqual(messages)
  })
  it('validates selection without silently accepting malformed numbers', () => {
    expect(parseSelectedLots('12, 15; 12 20')).toEqual({ valid: true, lots: [12, 15, 20] })
    for (const value of ['0', '-1', '1.5', '12abc', '1-10']) expect(parseSelectedLots(value).valid).toBe(false)
    expect(parseSelectedLots('')).toEqual({ valid: true, lots: [] })
  })
})
