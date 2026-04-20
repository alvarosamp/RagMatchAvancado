/**
 * pages/Chatbot.jsx
 * ──────────────────
 * ChatBot de editais — seletor de edital à esquerda + interface de chat.
 * Acessa POST /editais/{id}/chat com histórico de mensagens.
 */

import { useState, useRef, useEffect } from 'react'
import { editaisApi, ragApi } from '../api/client'

const SUGESTOES = [
  'Quais são os requisitos técnicos deste edital?',
  'Qual é o valor estimado dos itens?',
  'Quem é o órgão responsável pela licitação?',
  'Quais são os prazos de entrega?',
  'Há exigências de garantia? Quais?',
  'Quais documentos são exigidos para habilitação?',
  'Qual é a data de abertura das propostas?',
  'Quais produtos ou serviços são solicitados?',
]

// ── Bubbles ──────────────────────────────────────────────────────────────────

function BubbleUser({ text }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[75%] bg-azure/20 border border-azure/30 rounded-2xl rounded-tr-sm px-4 py-3">
        <p className="text-sm text-white font-body leading-relaxed whitespace-pre-wrap">{text}</p>
      </div>
    </div>
  )
}

function BubbleAssistant({ text, sources, model, loading }) {
  const [showSources, setShowSources] = useState(false)

  if (loading) return (
    <div className="flex justify-start">
      <div className="max-w-[75%] card py-3 px-4 flex items-center gap-3">
        <div className="flex gap-1">
          {[0, 1, 2].map(i => (
            <div
              key={i}
              className="w-1.5 h-1.5 rounded-full bg-azure-glow animate-pulse-dot"
              style={{ animationDelay: `${i * 0.2}s` }}
            />
          ))}
        </div>
        <span className="text-xs text-gray-500 font-mono">Analisando edital…</span>
      </div>
    </div>
  )

  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] space-y-2">
        <div className="card py-3 px-4 rounded-2xl rounded-tl-sm">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-5 h-5 rounded bg-gradient-to-br from-azure to-amber flex items-center justify-center">
              <span className="text-white text-xs font-mono font-black">T</span>
            </div>
            <span className="text-xs font-mono text-gray-500">{model || 'IA'}</span>
          </div>
          <p className="text-sm text-gray-200 font-body leading-relaxed whitespace-pre-wrap">{text}</p>
        </div>

        {sources && sources.length > 0 && (
          <div>
            <button
              onClick={() => setShowSources(v => !v)}
              className="flex items-center gap-1.5 text-xs font-mono text-gray-500 hover:text-azure-glow transition-colors px-1"
            >
              <span>{showSources ? '▼' : '▶'}</span>
              {sources.length} trecho{sources.length !== 1 ? 's' : ''} consultado{sources.length !== 1 ? 's' : ''}
            </button>
            {showSources && (
              <div className="mt-2 space-y-1.5">
                {sources.map((s, i) => (
                  <div key={i} className="bg-ink-50 border border-slate-border rounded-lg px-3 py-2">
                    <p className="text-xs font-mono text-gray-500 mb-1">Trecho #{s.chunk_idx + 1}</p>
                    <p className="text-xs text-gray-400 font-body leading-relaxed line-clamp-3">{s.text}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function Chatbot() {
  const [editais,      setEditais]      = useState([])
  const [loadingList,  setLoadingList]  = useState(true)
  const [selected,     setSelected]     = useState(null)   // edital object
  const [messages,     setMessages]     = useState([])
  const [input,        setInput]        = useState('')
  const [sending,      setSending]      = useState(false)
  const [llmModel,     setLlmModel]     = useState('gpt')
  const [error,        setError]        = useState(null)

  const bottomRef = useRef(null)
  const inputRef  = useRef(null)

  // Carrega lista de editais
  useEffect(() => {
    editaisApi.list()
      .then(r => setEditais(r.data))
      .catch(() => setEditais([]))
      .finally(() => setLoadingList(false))
  }, [])

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Foca no input ao selecionar edital
  useEffect(() => {
    if (selected) inputRef.current?.focus()
  }, [selected])

  const handleSelectEdital = (edital) => {
    if (selected?.id === edital.id) return
    if (messages.length > 0 && !confirm('Trocar de edital vai limpar o histórico. Continuar?')) return
    setSelected(edital)
    setMessages([])
    setError(null)
    setInput('')
  }

  const buildHistory = () =>
    messages.map(m => ({ role: m.role, content: m.content }))

  const enviar = async (texto) => {
    const q = (texto || input).trim()
    if (!q || sending || !selected) return

    setInput('')
    setError(null)

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
        history:  buildHistory(),
      })
      setMessages(prev => {
        const copy = [...prev]
        copy[copy.length - 1] = {
          role:    'assistant',
          content: res.data.answer,
          sources: res.data.sources,
          model:   res.data.model_used,
        }
        return copy
      })
    } catch (err) {
      const msg = err.response?.data?.detail || 'Erro ao conectar com o servidor.'
      setMessages(prev => {
        const copy = [...prev]
        copy[copy.length - 1] = {
          role:    'assistant',
          content: `⚠️ ${msg}`,
          sources: [],
          model:   llmModel,
        }
        return copy
      })
      setError(msg)
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

  const limpar = () => {
    if (messages.length === 0) return
    if (confirm('Limpar histórico desta conversa?')) {
      setMessages([])
      setError(null)
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="flex h-full min-h-full overflow-hidden">

      {/* ── Sidebar de editais ──────────────────────────────────────────── */}
      <aside className="w-64 flex-shrink-0 border-r border-slate-border bg-ink-100 flex flex-col">
        <div className="px-4 py-4 border-b border-slate-border">
          <p className="font-display font-bold text-white text-sm">Editais</p>
          <p className="text-xs text-gray-500 font-mono mt-0.5">Selecione para conversar</p>
        </div>

        <div className="flex-1 overflow-y-auto py-2">
          {loadingList ? (
            <div className="px-4 py-3 space-y-2">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-14 rounded-lg bg-slate-border/30 animate-pulse" />
              ))}
            </div>
          ) : editais.length === 0 ? (
            <div className="px-4 py-6 text-center">
              <p className="text-xs text-gray-500 font-body">Nenhum edital encontrado.</p>
              <p className="text-xs text-gray-600 font-body mt-1">Faça upload em Novo Edital.</p>
            </div>
          ) : (
            editais.map(edital => {
              const active = selected?.id === edital.id
              return (
                <button
                  key={edital.id}
                  onClick={() => handleSelectEdital(edital)}
                  className={`w-full text-left px-4 py-3 transition-all duration-150 border-l-2 ${
                    active
                      ? 'border-azure bg-azure/10 text-white'
                      : 'border-transparent text-gray-400 hover:bg-slate-hover hover:text-white'
                  }`}
                >
                  <p className="text-xs font-mono font-semibold truncate">
                    #{edital.id} — {edital.filename}
                  </p>
                  <p className="text-xs text-gray-600 font-mono mt-0.5">
                    {edital.chunks} chunks · {edital.requirements} requisitos
                  </p>
                </button>
              )
            })
          )}
        </div>
      </aside>

      {/* ── Área de chat ────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">

        {/* Header */}
        <div className="flex-shrink-0 border-b border-slate-border bg-ink-100 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-azure to-amber flex items-center justify-center">
                <span className="text-white text-xs font-mono font-black">T</span>
              </div>
              <div>
                <p className="font-display font-bold text-white text-sm">
                  {selected ? `Chat — ${selected.filename}` : 'ChatBot de Editais'}
                </p>
                <p className="text-xs text-gray-500 font-mono">
                  {selected
                    ? `${selected.chunks} chunks indexados`
                    : 'Selecione um edital para começar'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {messages.length > 0 && (
                <button
                  onClick={limpar}
                  className="text-xs font-mono text-gray-600 hover:text-red-fail transition-colors px-2 py-1"
                >
                  Limpar
                </button>
              )}
              <div className="flex rounded-lg border border-slate-border overflow-hidden">
                {[['gpt', 'GPT'], ['ollama', 'Local']].map(([val, lbl]) => (
                  <button
                    key={val}
                    onClick={() => setLlmModel(val)}
                    className={`px-3 py-1.5 text-xs font-mono transition-all duration-150 ${
                      llmModel === val
                        ? 'bg-azure text-white'
                        : 'text-gray-400 hover:text-white hover:bg-slate-hover'
                    }`}
                  >
                    {lbl}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Mensagens */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5">

          {/* Sem edital selecionado */}
          {!selected && (
            <div className="flex flex-col items-center justify-center h-full text-center py-8">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-azure/20 to-amber/20 border border-azure/20 flex items-center justify-center text-3xl mb-4">
                💬
              </div>
              <p className="font-display font-bold text-white text-lg mb-1">
                ChatBot de Editais
              </p>
              <p className="text-gray-500 text-sm max-w-xs leading-relaxed">
                Selecione um edital na lista ao lado para começar a conversar com a IA sobre o documento.
              </p>
            </div>
          )}

          {/* Edital selecionado, sem mensagens — sugestões */}
          {selected && messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center py-8">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-azure/20 to-amber/20 border border-azure/20 flex items-center justify-center text-2xl mb-4">
                📄
              </div>
              <p className="font-display font-bold text-white text-lg mb-1">
                Pergunte sobre o edital
              </p>
              <p className="text-gray-500 text-sm mb-8 max-w-sm">
                A IA analisa os trechos relevantes do documento e responde com base no conteúdo real.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-2xl w-full">
                {SUGESTOES.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => enviar(s)}
                    className="text-left px-4 py-3 rounded-xl border border-slate-border bg-ink-50 hover:border-azure/40 hover:bg-azure/5 text-sm text-gray-400 hover:text-white font-body transition-all duration-150"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Mensagens */}
          {messages.map((msg, i) =>
            msg.role === 'user'
              ? <BubbleUser key={i} text={msg.content} />
              : <BubbleAssistant
                  key={i}
                  text={msg.content}
                  sources={msg.sources}
                  model={msg.model}
                  loading={msg.loading}
                />
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="flex-shrink-0 border-t border-slate-border bg-ink-100 px-6 py-4">
          {error && (
            <p className="text-xs text-red-fail font-mono mb-2 px-1">⚠️ {error}</p>
          )}
          <div className="flex gap-3 items-end">
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  selected
                    ? 'Faça uma pergunta sobre o edital… (Enter para enviar)'
                    : 'Selecione um edital para começar…'
                }
                rows={1}
                disabled={sending || !selected}
                className="input resize-none min-h-[44px] max-h-32 py-3 pr-4 leading-snug disabled:opacity-50"
                style={{ height: 'auto' }}
                onInput={e => {
                  e.target.style.height = 'auto'
                  e.target.style.height = Math.min(e.target.scrollHeight, 128) + 'px'
                }}
              />
            </div>
            <button
              onClick={() => enviar()}
              disabled={!input.trim() || sending || !selected}
              className="btn-primary px-5 py-3 flex items-center gap-2 disabled:opacity-40 flex-shrink-0"
            >
              {sending
                ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                : <span className="font-mono text-base leading-none">→</span>
              }
              {!sending && <span>Enviar</span>}
            </button>
          </div>
          <p className="text-xs text-gray-600 font-mono mt-2 px-1">
            Modelo: <span className="text-gray-500">{llmModel === 'gpt' ? 'GPT-4o mini (OpenAI)' : 'Llama 3 (local)'}</span>
            {' · '}Enter para enviar · Shift+Enter para nova linha
          </p>
        </div>
      </div>
    </div>
  )
}
