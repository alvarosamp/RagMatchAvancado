/**
 * pages/EditalChat.jsx
 * ─────────────────────
 * Mini-RAG: chat por edital específico.
 * O usuário faz perguntas sobre o conteúdo do edital e a IA responde
 * com base nos chunks indexados (GPT ou Ollama local).
 */

import { useState, useRef, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ragApi }    from '../api/client'
import { useToast }  from '../contexts/ToastContext'

const SUGESTOES = [
  'Quais são os requisitos técnicos de switch neste edital?',
  'Qual é o valor estimado dos itens?',
  'Quem é o órgão responsável pela licitação?',
  'Quais são os prazos de entrega?',
  'Há exigências de garantia? Quais?',
  'Qual a quantidade de switches solicitada?',
]

function BubbleUser({ text }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[75%] bg-red-600/20 border border-red-600/30 rounded-lg rounded-tr-sm px-4 py-3">
        <p className="text-sm text-white font-body leading-relaxed">{text}</p>
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
              className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse-dot"
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
        {/* Resposta */}
        <div className="card py-3 px-4 rounded-lg rounded-tl-sm">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-5 h-5 rounded bg-gradient-to-br from-red-600 to-amber flex items-center justify-center">
              <span className="text-white text-xs font-mono font-black">T</span>
            </div>
            <span className="text-xs font-mono text-gray-500">{model || 'modelo'}</span>
          </div>
          <p className="text-sm text-gray-200 font-body leading-relaxed whitespace-pre-wrap">
            {text}
          </p>
        </div>

        {/* Fontes (collapsível) */}
        {sources && sources.length > 0 && (
          <div>
            <button
              onClick={() => setShowSources(v => !v)}
              className="flex items-center gap-1.5 text-xs font-mono text-gray-500 hover:text-red-400 transition-colors px-1"
            >
              <span>{showSources ? '▼' : '▶'}</span>
              {sources.length} trecho{sources.length !== 1 ? 's' : ''} consultado{sources.length !== 1 ? 's' : ''}
            </button>
            {showSources && (
              <div className="mt-2 space-y-1.5">
                {sources.map((s, i) => (
                  <div
                    key={i}
                    className="bg-ink-50 border border-slate-700 rounded-lg px-3 py-2"
                  >
                    <p className="text-xs font-mono text-gray-500 mb-1">
                      Trecho #{s.chunk_idx + 1}
                    </p>
                    <p className="text-xs text-gray-400 font-body leading-relaxed line-clamp-3">
                      {s.text}
                    </p>
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

export default function EditalChat() {
  const { id }     = useParams()
  const navigate   = useNavigate()
  const { confirm } = useToast()

  const [messages,  setMessages]  = useState([])   // { role, content, sources?, model? }
  const [input,     setInput]     = useState('')
  const [sending,   setSending]   = useState(false)
  const [llmModel,  setLlmModel]  = useState('gpt') // 'gpt' | 'ollama'
  const [error,     setError]     = useState(null)

  const bottomRef = useRef(null)
  const inputRef  = useRef(null)

  // Rola para o fundo quando chega nova mensagem
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Foca no input ao abrir
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const buildHistory = () =>
    messages.map(m => ({ role: m.role, content: m.content }))

  const enviar = async (texto) => {
    const q = (texto || input).trim()
    if (!q || sending) return

    setInput('')
    setError(null)

    const userMsg = { role: 'user', content: q }
    const loadMsg = { role: 'assistant', content: '', loading: true }

    setMessages(prev => [...prev, userMsg, loadMsg])
    setSending(true)

    try {
      const res = await ragApi.chat(id, {
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

  const limpar = async () => {
    if (messages.length === 0) return
    const ok = await confirm('Limpar o histórico desta conversa?', { title: 'Limpar histórico' })
    if (ok) setMessages([])
  }

  return (
    <div className="flex flex-col h-full min-h-full">

      {/* ── Header ──────────────────────────────────────────────────── */}
      <div className="flex-shrink-0 border-b border-slate-700 bg-ink-100 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate(`/editais/${id}`)}
              className="text-gray-500 hover:text-white transition-colors font-mono text-sm"
            >
              ← Voltar
            </button>
            <div className="w-px h-5 bg-slate-border" />
            <div>
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded bg-gradient-to-br from-red-600 to-amber flex items-center justify-center">
                  <span className="text-white text-xs font-mono font-black">T</span>
                </div>
                <p className="font-display font-bold text-white text-sm">Chat do Edital #{id}</p>
              </div>
              <p className="text-xs text-gray-500 font-mono mt-0.5">
                Pergunte sobre o conteúdo deste edital
              </p>
            </div>
          </div>

          {/* Seletor de modelo */}
          <div className="flex items-center gap-2">
            {messages.length > 0 && (
              <button
                onClick={limpar}
                className="text-xs font-mono text-gray-600 hover:text-red-fail transition-colors px-2 py-1"
              >
                Limpar
              </button>
            )}
            <div className="flex rounded-lg border border-slate-700 overflow-hidden">
              {[['gpt', 'GPT'], ['ollama', 'Local']].map(([val, lbl]) => (
                <button
                  key={val}
                  onClick={() => setLlmModel(val)}
                  className={`px-3 py-1.5 text-xs font-mono transition-all duration-150 ${
                    llmModel === val
                      ? 'bg-red-600 text-white'
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

      {/* ── Área de mensagens ────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5">

        {/* Estado vazio — sugestões */}
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
              <div className="w-14 h-14 rounded-lg bg-gradient-to-br from-red-600/20 to-amber/20 border border-red-600/20 flex items-center justify-center text-2xl mb-4">
              💬
            </div>
            <p className="font-display font-bold text-white text-lg mb-1">
              Pergunte sobre o edital
            </p>
            <p className="text-gray-500 text-sm mb-8 max-w-sm">
              O assistente consulta os trechos relevantes do documento e responde com base no conteúdo real.
            </p>

            {/* Sugestões de perguntas */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-2xl w-full">
              {SUGESTOES.map((s, i) => (
                <button
                  key={i}
                  onClick={() => enviar(s)}
                  className="text-left px-4 py-3 rounded-lg border border-slate-700 bg-ink-50 hover:border-red-600/40 hover:bg-red-600/5 text-sm text-gray-400 hover:text-white font-body transition-all duration-150"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Mensagens */}
        {messages.map((msg, i) => (
          msg.role === 'user'
            ? <BubbleUser key={i} text={msg.content} />
            : <BubbleAssistant
                key={i}
                text={msg.content}
                sources={msg.sources}
                model={msg.model}
                loading={msg.loading}
              />
        ))}

        <div ref={bottomRef} />
      </div>

      {/* ── Input ───────────────────────────────────────────────────── */}
      <div className="flex-shrink-0 border-t border-slate-700 bg-ink-100 px-6 py-4">
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
              placeholder="Faça uma pergunta sobre o edital… (Enter para enviar)"
              rows={1}
              disabled={sending}
              className="input resize-none min-h-[44px] max-h-32 py-3 pr-4 leading-snug disabled:opacity-60"
              style={{ height: 'auto' }}
              onInput={e => {
                e.target.style.height = 'auto'
                e.target.style.height = Math.min(e.target.scrollHeight, 128) + 'px'
              }}
            />
          </div>
          <button
            onClick={() => enviar()}
            disabled={!input.trim() || sending}
            className="btn-primary px-5 py-3 flex items-center gap-2 disabled:opacity-40 flex-shrink-0"
          >
            {sending ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <span className="font-mono text-base leading-none">→</span>
            )}
            {!sending && <span>Enviar</span>}
          </button>
        </div>
        <p className="text-xs text-gray-600 font-mono mt-2 px-1">
          Modelo: <span className="text-gray-500">{llmModel === 'gpt' ? 'GPT-4o mini (OpenAI)' : 'Llama 3 (local)'}</span>
          {' · '}Enter para enviar · Shift+Enter para nova linha
        </p>
      </div>
    </div>
  )
}
