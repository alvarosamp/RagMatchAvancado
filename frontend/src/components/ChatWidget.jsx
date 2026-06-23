/**
 * components/ChatWidget.jsx
 * ──────────────────────────
 * Widget de chat flutuante disponível em todas as páginas autenticadas.
 * Botão fixo no canto inferior direito; clique abre painel compacto.
 * O usuário seleciona um edital pelo dropdown (sem fazer upload).
 */

import { useState, useRef, useEffect } from 'react'
import { editaisApi, ragApi } from '../api/client'

function BubbleUser({ text }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] bg-azure/20 border border-azure/30 rounded-xl rounded-tr-sm px-3 py-2">
        <p className="text-xs text-white font-body leading-relaxed whitespace-pre-wrap">{text}</p>
      </div>
    </div>
  )
}

function BubbleAssistant({ text, loading }) {
  if (loading) return (
    <div className="flex justify-start">
      <div className="max-w-[85%] bg-ink-100 border border-slate-border rounded-xl px-3 py-2 flex items-center gap-2">
        <div className="flex gap-1">
          {[0, 1, 2].map(i => (
            <div
              key={i}
              className="w-1.5 h-1.5 rounded-full bg-azure-glow animate-pulse-dot"
              style={{ animationDelay: `${i * 0.2}s` }}
            />
          ))}
        </div>
        <span className="text-[10px] text-gray-500 font-body">Analisando...</span>
      </div>
    </div>
  )
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] bg-ink-100 border border-slate-border rounded-xl rounded-tl-sm px-3 py-2">
        <p className="text-xs text-gray-200 font-body leading-relaxed whitespace-pre-wrap">{text}</p>
      </div>
    </div>
  )
}

export default function ChatWidget() {
  const [open,         setOpen]         = useState(false)
  const [editais,      setEditais]      = useState([])
  const [selected,     setSelected]     = useState(null)
  const [messages,     setMessages]     = useState([])
  const [input,        setInput]        = useState('')
  const [sending,      setSending]      = useState(false)
  const [llmModel,     setLlmModel]     = useState('gpt')
  const [showSelector, setShowSelector] = useState(false)
  const [loadingList,  setLoadingList]  = useState(false)

  const bottomRef = useRef(null)
  const inputRef  = useRef(null)

  // Carrega editais quando abre o widget
  useEffect(() => {
    if (!open || editais.length > 0) return
    setLoadingList(true)
    editaisApi.list()
      .then(r => setEditais(r.data || []))
      .catch(() => setEditais([]))
      .finally(() => setLoadingList(false))
  }, [open])

  // Auto-scroll nas mensagens
  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open])

  // Foca input ao selecionar edital
  useEffect(() => {
    if (open && selected) inputRef.current?.focus()
  }, [open, selected])

  const handleSelectEdital = (edital) => {
    if (selected?.id === edital.id) { setShowSelector(false); return }
    setSelected(edital)
    setMessages([])
    setInput('')
    setShowSelector(false)
  }

  const enviar = async () => {
    const q = input.trim()
    if (!q || sending || !selected) return

    setInput('')
    setMessages(prev => [
      ...prev,
      { role: 'user',      content: q },
      { role: 'assistant', content: '', loading: true },
    ])
    setSending(true)

    try {
      const res = await ragApi.chat(selected.id, {
        question: q,
        model:    llmModel,
        history:  messages.map(m => ({ role: m.role, content: m.content })),
      })
      setMessages(prev => {
        const copy = [...prev]
        copy[copy.length - 1] = {
          role:    'assistant',
          content: res.data.answer,
        }
        return copy
      })
    } catch (err) {
      const msg = err.response?.data?.detail || 'Erro ao conectar com o servidor.'
      setMessages(prev => {
        const copy = [...prev]
        copy[copy.length - 1] = { role: 'assistant', content: `Erro: ${msg}` }
        return copy
      })
    } finally {
      setSending(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      enviar()
    }
  }

  return (
    <>
      {/* ── Botão flutuante ──────────────────────────────────────────────── */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-full border border-stone-200 bg-white px-4 py-3 text-sm font-semibold text-stone-800 shadow-xl transition-transform duration-150 hover:-translate-y-0.5 hover:border-red-200 dark:border-slate-border dark:bg-ink-50 dark:text-white"
          title="Abrir assistente"
        >
          <span className="grid h-7 w-7 place-items-center rounded-full bg-red-700 text-xs text-white dark:bg-azure">?</span>
          Assistente
        </button>
      )}

      {/* ── Painel do chat ───────────────────────────────────────────────── */}
      {open && (
        <div className="fixed bottom-6 right-6 z-50 flex h-[580px] w-96 flex-col overflow-hidden rounded-[28px] border border-stone-200 bg-white shadow-2xl dark:border-slate-border dark:bg-ink-50">

          {/* Header */}
          <div className="flex-shrink-0 border-b border-stone-200 bg-[#fbf8f3] px-4 py-3 dark:border-slate-border dark:bg-ink-100">
            <div className="flex items-center justify-between">
              {/* Título */}
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-red-700 text-white dark:bg-azure">
                  <span className="text-xs font-bold">T</span>
                </div>
                <div>
                  <p className="text-sm font-display font-bold text-stone-950 leading-none dark:text-white">Assistente do edital</p>
                  <p className="mt-0.5 max-w-[160px] truncate text-[11px] text-stone-500 dark:text-gray-500">
                    {selected ? selected.filename : 'Nenhum edital selecionado'}
                  </p>
                </div>
              </div>

              {/* Modelo + fechar */}
              <div className="flex items-center gap-1.5">
                <div className="flex overflow-hidden rounded-xl border border-stone-200 bg-white dark:border-slate-border dark:bg-ink-50">
                  {[['gpt', 'Online'], ['ollama', 'Local leve']].map(([val, lbl]) => (
                    <button
                      key={val}
                      onClick={() => setLlmModel(val)}
                      className={`px-2 py-1 text-[10px] font-semibold transition-all duration-100 ${
                        llmModel === val
                          ? 'bg-red-700 text-white dark:bg-azure'
                          : 'text-stone-500 hover:bg-stone-50 hover:text-stone-900 dark:text-gray-500 dark:hover:bg-slate-hover dark:hover:text-white'
                      }`}
                    >
                      {lbl}
                    </button>
                  ))}
                </div>
                {messages.length > 0 && (
                  <button
                    onClick={() => setMessages([])}
                    className="px-1 py-1 text-[10px] font-semibold text-stone-400 transition-colors hover:text-red-fail dark:text-gray-600"
                    title="Limpar histórico"
                  >
                    limpar
                  </button>
                )}
                <button
                  onClick={() => setOpen(false)}
                  className="p-1 text-lg leading-none text-stone-500 transition-colors hover:text-stone-950 dark:text-gray-500 dark:hover:text-white"
                  title="Fechar"
                >
                  ×
                </button>
              </div>
            </div>

            {/* Seletor de edital */}
            <div className="mt-2 relative">
              <button
                onClick={() => setShowSelector(v => !v)}
                className="flex w-full items-center justify-between gap-2 rounded-xl border border-stone-200 bg-white px-3 py-2 text-left text-xs text-stone-600 transition-all hover:border-red-200 hover:text-stone-950 dark:border-slate-border dark:bg-ink-50 dark:text-gray-400 dark:hover:border-azure/40 dark:hover:text-white"
              >
                <span className="truncate flex-1">
                  {selected ? `#${selected.id} - ${selected.filename}` : 'Selecionar edital para conversar'}
                </span>
                <span className="text-[9px] flex-shrink-0">{showSelector ? '▲' : '▼'}</span>
              </button>

              {showSelector && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-ink-100 border border-slate-border
                                rounded-lg shadow-xl z-10 max-h-52 overflow-y-auto">
                  {loadingList ? (
                    <div className="px-3 py-3 space-y-2">
                      {[1, 2, 3].map(i => (
                        <div key={i} className="h-8 rounded bg-slate-border/30 animate-pulse" />
                      ))}
                    </div>
                  ) : editais.length === 0 ? (
                    <p className="px-3 py-3 text-xs text-gray-500 font-mono">
                      Nenhum edital disponível. Faça upload em Novo Edital.
                    </p>
                  ) : (
                    editais.map(e => (
                      <button
                        key={e.id}
                        onClick={() => handleSelectEdital(e)}
                        className={`w-full text-left px-3 py-2.5 text-xs font-mono hover:bg-slate-hover
                                    transition-all border-l-2 ${
                          selected?.id === e.id
                            ? 'border-azure text-azure-glow bg-azure/5'
                            : 'border-transparent text-gray-400 hover:text-white'
                        }`}
                      >
                        <p className="font-semibold truncate">#{e.id} — {e.filename}</p>
                        <p className="text-gray-600 mt-0.5">{e.chunks} chunks · {e.requirements} requisitos</p>
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>

          {/* ── Mensagens ──────────────────────────────────────────────────── */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
            {!selected && (
              <div className="flex flex-col items-center justify-center h-full text-center gap-3">
                <div className="grid h-14 w-14 place-items-center rounded-2xl border border-stone-200 bg-white text-sm font-semibold text-stone-500 dark:border-slate-border dark:bg-ink-50 dark:text-gray-400">PDF</div>
                <div>
                  <p className="text-sm font-display font-bold text-stone-950 dark:text-white">Escolha um edital</p>
                  <p className="text-xs text-stone-500 mt-1 max-w-[220px] leading-relaxed dark:text-gray-500">
                    Depois disso, pergunte sobre prazos, requisitos, itens ou documentos.
                  </p>
                </div>
              </div>
            )}

            {selected && messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center gap-3">
                <div className="grid h-14 w-14 place-items-center rounded-2xl border border-stone-200 bg-white text-sm font-semibold text-stone-500 dark:border-slate-border dark:bg-ink-50 dark:text-gray-400">?</div>
                <div>
                  <p className="text-sm font-display font-bold text-stone-950 dark:text-white">Como posso ajudar?</p>
                  <p className="text-xs text-stone-500 mt-1 max-w-[220px] leading-relaxed dark:text-gray-500">
                    Pergunte sobre <span className="text-red-700 dark:text-azure-glow">{selected.filename}</span>
                  </p>
                </div>
              </div>
            )}

            {messages.map((msg, i) =>
              msg.role === 'user'
                ? <BubbleUser key={i} text={msg.content} />
                : <BubbleAssistant key={i} text={msg.content} loading={msg.loading} />
            )}
            <div ref={bottomRef} />
          </div>

          {/* ── Input ──────────────────────────────────────────────────────── */}
          <div className="flex-shrink-0 border-t border-slate-border bg-ink-100 px-4 py-3">
            <div className="flex gap-2 items-end">
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={selected ? 'Pergunte sobre o edital… (Enter para enviar)' : 'Selecione um edital…'}
                disabled={sending || !selected}
                rows={1}
                className="input flex-1 resize-none text-xs min-h-[36px] max-h-24 py-2 disabled:opacity-50"
                style={{ height: 'auto' }}
                onInput={e => {
                  e.target.style.height = 'auto'
                  e.target.style.height = Math.min(e.target.scrollHeight, 96) + 'px'
                }}
              />
              <button
                onClick={enviar}
                disabled={!input.trim() || sending || !selected}
                className="btn-primary px-4 py-2 flex-shrink-0 disabled:opacity-40 text-sm"
              >
                {sending
                  ? <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  : <span>Enviar</span>
                }
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
