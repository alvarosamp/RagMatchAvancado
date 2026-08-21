import { useEffect, useMemo, useState } from 'react'
import { bidRobotApi } from '../api/client'

const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })

const portals = [
  { value: 'COMPRAS_GOV', label: 'Compras.gov.br' },
  { value: 'BLL', label: 'BLL' },
  { value: 'BNC', label: 'BNC' },
]

function portalLabel(value) {
  return portals.find((portal) => portal.value === value)?.label || value
}

const emptyForm = {
  portal: 'COMPRAS_GOV',
  process_number: '',
  entity: '',
  dispute_at: '',
  mode: 'assistido',
  lots: [{
    number: '1',
    description: '',
    quantity: 1,
    unit_cost: 0,
    current_best_bid: '',
    decrement: 0.01,
    minimum_margin_percent: 8,
    maximum_total_bid: '',
  }],
}

function numeric(value) {
  if (value === '' || value == null) return undefined
  return Number(value)
}

export default function BidRobot() {
  const [sessions, setSessions] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const selected = useMemo(() => sessions.find((session) => session.id === selectedId) || sessions[0], [sessions, selectedId])

  const load = async () => {
    const { data } = await bidRobotApi.listSessions()
    setSessions(data)
    if (!selectedId && data.length) setSelectedId(data[0].id)
  }

  useEffect(() => {
    load().catch(() => setError('Nao foi possivel carregar as sessoes de lances.'))
  }, [])

  const updateLot = (index, key, value) => {
    setForm((current) => ({
      ...current,
      lots: current.lots.map((lot, lotIndex) => lotIndex === index ? { ...lot, [key]: value } : lot),
    }))
  }

  const createSession = async (event) => {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      const payload = {
        ...form,
        dispute_at: form.dispute_at || null,
        lots: form.lots.map((lot) => ({
          ...lot,
          quantity: numeric(lot.quantity),
          unit_cost: numeric(lot.unit_cost),
          current_best_bid: numeric(lot.current_best_bid),
          decrement: numeric(lot.decrement),
          minimum_margin_percent: numeric(lot.minimum_margin_percent),
          maximum_total_bid: numeric(lot.maximum_total_bid),
        })),
      }
      const { data } = await bidRobotApi.createSession(payload)
      setSessions((current) => [data, ...current])
      setSelectedId(data.id)
      setForm(emptyForm)
    } catch {
      setError('Revise os dados da sessao. Processo, orgao e ao menos um lote sao obrigatorios.')
    } finally {
      setLoading(false)
    }
  }

  const updateMarket = async (sessionId, lotId, value) => {
    if (!value) return
    const { data } = await bidRobotApi.updateMarketBid(sessionId, lotId, Number(value))
    setSessions((current) => current.map((item) => item.id === data.id ? data : item))
  }

  const confirmBid = async (sessionId, lot) => {
    const bidValue = lot.recommendation?.suggested_bid
    if (!bidValue) return
    const { data } = await bidRobotApi.confirmBid(sessionId, lot.id, bidValue, 'manual')
    setSessions((current) => current.map((item) => item.id === data.id ? data : item))
  }

  const autoBid = async (sessionId, lot) => {
    setError('')
    try {
      const { data } = await bidRobotApi.autoBid(sessionId, lot.id, false)
      setSessions((current) => current.map((item) => item.id === data.id ? data : item))
    } catch (err) {
      setError(err.response?.data?.detail || 'Nao foi possivel enviar o lance automatico.')
    }
  }

  const addChatMessage = async (sessionId, message) => {
    if (!message) return
    const { data } = await bidRobotApi.addChatMessage(sessionId, message)
    setSessions((current) => current.map((item) => item.id === data.id ? data : item))
  }

  const syncPortal = async (sessionId, lot, portalSessionUrl) => {
    setError('')
    try {
      const { data } = await bidRobotApi.syncPortal(sessionId, lot.id, portalSessionUrl)
      setSessions((current) => current.map((item) => item.id === data.id ? data : item))
    } catch (err) {
      setError(err.response?.data?.detail || 'Nao foi possivel sincronizar com o portal.')
    }
  }

  return (
    <div className="space-y-6 p-6 lg:p-8">
      <section className="border-b border-slate-200 pb-5 dark:border-slate-700">
        <p className="text-xs font-semibold uppercase tracking-wide text-blue-600 dark:text-blue-300">Compras.gov.br, BLL e BNC</p>
        <h1 className="mt-2 text-2xl font-bold text-slate-950 dark:text-white">Robo de lances assistido</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500 dark:text-slate-400">
          Calcule o proximo lance, preserve margem minima e mantenha historico de auditoria. No modo autorizado, o robo aciona o adaptador configurado para enviar o lance automaticamente.
        </p>
      </section>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

      <section className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
        <form onSubmit={createSession} className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-800">
          <h2 className="text-base font-semibold text-slate-950 dark:text-white">Nova sessao</h2>
          <div className="mt-4 grid gap-3">
            <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Portal
              <select value={form.portal} onChange={(event) => setForm({ ...form, portal: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 dark:border-slate-600 dark:bg-slate-900">
                {portals.map((portal) => <option key={portal.value} value={portal.value}>{portal.label}</option>)}
              </select>
            </label>
            <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Processo
              <input value={form.process_number} onChange={(event) => setForm({ ...form, process_number: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-900" />
            </label>
            <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Orgao
              <input value={form.entity} onChange={(event) => setForm({ ...form, entity: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-900" />
            </label>
            <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Data da disputa
              <input type="datetime-local" value={form.dispute_at} onChange={(event) => setForm({ ...form, dispute_at: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-900" />
            </label>
            <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Modo
              <select value={form.mode} onChange={(event) => setForm({ ...form, mode: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 dark:border-slate-600 dark:bg-slate-900">
                <option value="assistido">Assistido: recomendar e registrar</option>
                <option value="autorizado">Autorizado: permitir envio automatico</option>
              </select>
            </label>
          </div>

          {form.lots.map((lot, index) => (
            <div key={index} className="mt-5 rounded-lg border border-slate-200 p-4 dark:border-slate-700">
              <div className="grid grid-cols-2 gap-3">
                <NumberInput label="Lote" value={lot.number} onChange={(value) => updateLot(index, 'number', value)} />
                <NumberInput label="Quantidade" type="number" value={lot.quantity} onChange={(value) => updateLot(index, 'quantity', value)} />
                <NumberInput label="Custo unitario" type="number" value={lot.unit_cost} onChange={(value) => updateLot(index, 'unit_cost', value)} />
                <NumberInput label="Menor lance" type="number" value={lot.current_best_bid} onChange={(value) => updateLot(index, 'current_best_bid', value)} />
                <NumberInput label="Decremento" type="number" value={lot.decrement} onChange={(value) => updateLot(index, 'decrement', value)} />
                <NumberInput label="Margem minima %" type="number" value={lot.minimum_margin_percent} onChange={(value) => updateLot(index, 'minimum_margin_percent', value)} />
              </div>
              <label className="mt-3 block text-sm font-medium text-slate-700 dark:text-slate-300">Descricao
                <textarea value={lot.description} onChange={(event) => updateLot(index, 'description', event.target.value)} rows={2} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-900" />
              </label>
            </div>
          ))}
          <button type="submit" disabled={loading} className="btn-primary mt-5 w-full">{loading ? 'Criando...' : 'Criar sessao'}</button>
        </form>

        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {sessions.map((session) => (
              <button key={session.id} type="button" onClick={() => setSelectedId(session.id)} className={`rounded-lg border px-3 py-2 text-sm font-semibold ${selected?.id === session.id ? 'border-blue-500 bg-blue-50 text-blue-900 dark:bg-blue-950/40 dark:text-blue-200' : 'border-slate-200 bg-white text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'}`}>
                {portalLabel(session.portal)} {session.process_number}
              </button>
            ))}
          </div>

          {!selected ? (
            <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">Cadastre uma sessao para iniciar.</div>
          ) : (
            <section className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-800">
              <div className="flex flex-col gap-2 border-b border-slate-200 pb-4 dark:border-slate-700 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{portalLabel(selected.portal)} | {selected.status}</p>
                  <h2 className="text-lg font-bold text-slate-950 dark:text-white">{selected.process_number}</h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400">{selected.entity}</p>
                </div>
                <span className={`rounded-lg border px-3 py-2 text-xs font-semibold ${selected.mode === 'autorizado' ? 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200' : 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200'}`}>
                  {selected.mode === 'autorizado' ? 'Envio automatico autorizado' : 'Confirmacao manual ativa'}
                </span>
              </div>
              <div className="mt-5 grid gap-4">
                {selected.lots.map((lot) => <LotPanel key={lot.id} session={selected} lot={lot} onMarket={updateMarket} onConfirm={confirmBid} onAutoBid={autoBid} onSync={syncPortal} />)}
              </div>
              <ChatLog session={selected} onSend={addChatMessage} />
              <div className="mt-6">
                <h3 className="text-sm font-semibold text-slate-950 dark:text-white">Auditoria</h3>
                <div className="mt-3 space-y-2">
                  {selected.events.map((event) => (
                    <div key={event.id} className="rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700">
                      <p className="font-medium text-slate-800 dark:text-slate-200">{event.message}</p>
                      <p className="text-xs text-slate-400">{new Date(event.created_at).toLocaleString('pt-BR')}</p>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          )}
        </div>
      </section>
    </div>
  )
}

function NumberInput({ label, value, onChange, type = 'text' }) {
  return (
    <label className="text-sm font-medium text-slate-700 dark:text-slate-300">{label}
      <input type={type} min={type === 'number' ? '0' : undefined} step={type === 'number' ? '0.01' : undefined} value={value} onChange={(event) => onChange(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-900" />
    </label>
  )
}

function LotPanel({ session, lot, onMarket, onConfirm, onAutoBid, onSync }) {
  const [marketBid, setMarketBid] = useState(lot.current_best_bid || '')
  const [portalUrl, setPortalUrl] = useState('')
  const rec = lot.recommendation
  const canSyncPortal = session.portal === 'BLL' || session.portal === 'BNC'

  return (
    <article className="rounded-lg border border-slate-200 p-4 dark:border-slate-700">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-600 dark:text-blue-300">Lote {lot.number}</p>
          <h3 className="mt-1 text-base font-semibold text-slate-950 dark:text-white">{lot.description || 'Sem descricao'}</h3>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Piso {money.format(rec.floor_bid)} | custo {money.format(rec.cost_total)} | margem estimada {rec.estimated_margin_percent ?? '-'}%</p>
        </div>
        <div className="text-left lg:text-right">
          <p className="text-xs text-slate-500">Proximo lance</p>
          <p className={`text-2xl font-bold ${rec.can_bid ? 'text-emerald-600 dark:text-emerald-300' : 'text-red-600 dark:text-red-300'}`}>{rec.suggested_bid ? money.format(rec.suggested_bid) : 'Parar'}</p>
        </div>
      </div>
      <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600 dark:bg-slate-900/60 dark:text-slate-300">{rec.reason}</p>
      <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto_auto_auto]">
        <input type="number" min="0" step="0.01" value={marketBid} onChange={(event) => setMarketBid(event.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-900" placeholder="Menor lance visto no portal" />
        <button type="button" onClick={() => onMarket(session.id, lot.id, marketBid)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700">Atualizar</button>
        <button type="button" disabled={!rec.can_bid || !rec.suggested_bid} onClick={() => onConfirm(session.id, lot)} className="btn-primary disabled:cursor-not-allowed disabled:opacity-50">Registrar lance</button>
        {session.mode === 'autorizado' && (
          <button type="button" disabled={!rec.can_bid || !rec.suggested_bid} onClick={() => onAutoBid(session.id, lot)} className="rounded-lg border border-emerald-500 bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50">Enviar automatico</button>
        )}
      </div>
      {canSyncPortal && (
        <div className="mt-3 grid gap-3 border-t border-dashed border-slate-200 pt-3 dark:border-slate-700 md:grid-cols-[1fr_auto]">
          <input value={portalUrl} onChange={(event) => setPortalUrl(event.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900" placeholder={`URL da sessao no ${session.portal} (requer ${session.portal}_PORTAL_USER/PASSWORD no .env)`} />
          <button type="button" onClick={() => onSync(session.id, lot, portalUrl)} disabled={!portalUrl} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700">Sincronizar do portal</button>
        </div>
      )}
    </article>
  )
}

function ChatLog({ session, onSend }) {
  const [message, setMessage] = useState('')
  const chatEvents = session.events.filter((event) => event.type === 'chat_message')

  const send = () => {
    if (!message.trim()) return
    onSend(session.id, message.trim())
    setMessage('')
  }

  return (
    <div className="mt-6 rounded-lg border border-slate-200 p-4 dark:border-slate-700">
      <h3 className="text-sm font-semibold text-slate-950 dark:text-white">Chat e avisos do pregao</h3>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Registre aqui as mensagens do pregoeiro e eventos da disputa (rodada, suspensao, pedido de anexo) conforme aparecem no portal.</p>
      <div className="mt-3 flex gap-2">
        <input
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          onKeyDown={(event) => event.key === 'Enter' && send()}
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900"
          placeholder="Colar mensagem do pregoeiro ou evento da disputa"
        />
        <button type="button" onClick={send} disabled={!message.trim()} className="btn-primary disabled:cursor-not-allowed disabled:opacity-50">Registrar</button>
      </div>
      <div className="mt-3 max-h-64 space-y-2 overflow-y-auto">
        {chatEvents.length === 0 && <p className="text-sm text-slate-400">Nenhuma mensagem registrada ainda.</p>}
        {chatEvents.map((event) => (
          <div key={event.id} className="rounded-lg bg-slate-50 px-3 py-2 text-sm dark:bg-slate-900/60">
            <p className="text-slate-700 dark:text-slate-200">{event.message}</p>
            <p className="text-xs text-slate-400">{new Date(event.created_at).toLocaleString('pt-BR')} {event.payload?.source === 'portal_sync' ? '· sincronizado do portal' : '· manual'}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
