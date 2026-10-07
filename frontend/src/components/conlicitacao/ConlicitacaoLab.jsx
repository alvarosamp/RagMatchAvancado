import { useEffect, useMemo, useRef, useState } from 'react'
import { Download, MessageSquareText, Play, RefreshCw, Route, Search, Square, Table2 } from 'lucide-react'

import { conlicitacaoApi } from '../../api/client'
import { useToast } from '../../contexts/ToastContext'
import SectionCard from '../ui/SectionCard'

const TABS = [
  { key: 'bulletins', label: 'Boletins', icon: Table2 },
  { key: 'trace', label: 'Rastrear licitação', icon: Route },
  { key: 'chat', label: 'Chat monitorado', icon: MessageSquareText },
]

export function apiError(error, fallback) {
  const detail = error.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join('; ')
  return fallback
}

function money(value) {
  if (!value) return '—'
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(value))
}

function dateTime(value) {
  if (!value) return '—'
  const parsed = new Date(String(value).replace(' -', '-').replace(' ', 'T'))
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString('pt-BR')
}

function Field({ label, children }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 break-words text-sm font-medium text-slate-800 dark:text-slate-100">{children || '—'}</dd>
    </div>
  )
}

function Latency({ ms }) {
  if (ms == null) return null
  const tone = ms > 10_000 ? 'text-rose-600' : ms > 3_000 ? 'text-amber-600' : 'text-emerald-600'
  return <span className={`text-xs font-medium ${tone}`}>{(ms / 1000).toFixed(1)} s</span>
}

function useDownload() {
  const { toast } = useToast()
  const [downloading, setDownloading] = useState('')
  const download = async (bulletinId, tenderId, doc) => {
    const key = `${bulletinId}-${tenderId}-${doc.index}`
    setDownloading(key)
    try {
      const response = await conlicitacaoApi.labDocument(bulletinId, tenderId, doc.index)
      const url = URL.createObjectURL(response.data)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = doc.filename
      anchor.click()
      URL.revokeObjectURL(url)
      toast({ type: 'success', title: 'Documento baixado', message: `${doc.filename} · ${(response.data.size / 1024).toFixed(0)} KB` })
    } catch (error) {
      let message = 'Não foi possível baixar o documento.'
      if (error.response?.data instanceof Blob) {
        try { message = JSON.parse(await error.response.data.text()).detail || message } catch { /* corpo não-JSON */ }
      }
      toast({ type: 'error', title: 'Download', message })
    } finally {
      setDownloading('')
    }
  }
  return { download, downloading }
}

function TenderCard({ tender, bulletinId, onTrace }) {
  const { download, downloading } = useDownload()
  const orgao = tender.orgao || {}
  return (
    <article className="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold text-blue-700 dark:text-blue-300">
            Nº ConLicitação {tender.id} · {tender.edital || 'sem edital'}
          </p>
          <p className="mt-1 text-sm text-slate-800 dark:text-slate-100">{tender.objeto}</p>
        </div>
        <div className="flex flex-wrap gap-1">
          <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-semibold dark:bg-slate-900">{tender.situacao || '—'}</span>
          {tender.has_electronic_trading && <span className="rounded-full bg-emerald-100 px-2 py-1 text-[11px] font-semibold text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">chat monitorável</span>}
        </div>
      </div>
      <dl className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Órgão">{orgao.nome}</Field>
        <Field label="Local">{[orgao.cidade, orgao.uf].filter(Boolean).join(' / ')}</Field>
        <Field label="UASG">{orgao.codigo}</Field>
        <Field label="Valor estimado">{money(tender.valor_estimado)}</Field>
        <Field label="Abertura">{dateTime(tender.datahora_abertura)}</Field>
        <Field label="Documento">{dateTime(tender.datahora_documento)}</Field>
        <Field label="Prazo">{dateTime(tender.datahora_prazo)}</Field>
        <Field label="Processo">{tender.processo}</Field>
      </dl>
      {(tender.item || tender.observacao) && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs font-medium text-blue-700 dark:text-blue-300">Itens e observações</summary>
          {tender.item && <pre className="mt-2 whitespace-pre-wrap text-xs text-slate-700 dark:text-slate-300">{tender.item}</pre>}
          {tender.observacao && <pre className="mt-2 whitespace-pre-wrap text-xs text-slate-500">{tender.observacao}</pre>}
        </details>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {(tender.documentos || []).map((doc) => (
          <button key={doc.index} type="button" className="btn-ghost flex items-center gap-1 text-xs" disabled={Boolean(downloading)} onClick={() => download(bulletinId, tender.id, doc)}>
            {downloading === `${bulletinId}-${tender.id}-${doc.index}` ? <RefreshCw size={13} className="animate-spin" /> : <Download size={13} />}
            {doc.filename}
          </button>
        ))}
        {!tender.documentos?.length && <span className="text-xs text-slate-400">Sem documento na API</span>}
        {onTrace && <button type="button" className="btn-ghost text-xs" onClick={() => onTrace(tender.id)}>Rastrear</button>}
      </div>
    </article>
  )
}

function FollowUpCard({ item }) {
  const analysis = item.analise || {}
  return (
    <article className="rounded-xl border border-violet-200 p-4 dark:border-violet-900">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold text-violet-700 dark:text-violet-300">
          Acompanhamento {item.id} · licitação {item.licitacao_id} · {item.edital || '—'}
        </p>
        <div className="flex flex-wrap gap-1">
          {(analysis.kinds || []).map((kind) => <span key={kind} className="rounded bg-violet-100 px-2 py-0.5 text-[11px] text-violet-800 dark:bg-violet-950/40 dark:text-violet-200">{kind}</span>)}
        </div>
      </div>
      <p className="mt-1 text-xs text-slate-500">{item.orgao?.nome} · {item.orgao?.cidade}/{item.orgao?.uf} · fonte {item.data_fonte || '—'}</p>
      <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-xs text-slate-700 dark:text-slate-300">{item.sintese}</pre>
      {(analysis.companies?.length > 0 || analysis.max_value) && (
        <p className="mt-2 rounded bg-emerald-50 px-2 py-1 text-xs text-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200">
          Extraído: {analysis.companies?.join(', ') || 'empresa não identificada'}
          {analysis.cnpjs?.length > 0 && ` · CNPJ ${analysis.cnpjs.join(', ')}`}
          {analysis.max_value && ` · ${money(analysis.max_value)}`}
        </p>
      )}
    </article>
  )
}

function QualityTable({ title, rates }) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold text-slate-600 dark:text-slate-300">{title}</p>
      <table className="w-full text-xs">
        <tbody>
          {Object.entries(rates).map(([field, rate]) => (
            <tr key={field} className="border-t border-slate-100 dark:border-slate-700">
              <td className="py-1 pr-2 font-mono">{field}</td>
              <td className="w-28 py-1">
                <div className="h-1.5 rounded bg-slate-100 dark:bg-slate-700">
                  <div className="h-1.5 rounded bg-blue-600" style={{ width: `${rate.pct}%` }} />
                </div>
              </td>
              <td className="py-1 pl-2 text-right tabular-nums">{rate.pct}% <span className="text-slate-400">({rate.filled}/{rate.total})</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function BulletinsTab({ onTrace }) {
  const { toast } = useToast()
  const [filters, setFilters] = useState(null)
  const [filterId, setFilterId] = useState('')
  const [bulletins, setBulletins] = useState(null)
  const [bulletin, setBulletin] = useState(null)
  const [busy, setBusy] = useState('')
  const [query, setQuery] = useState('')
  const [view, setView] = useState('licitacoes')

  const run = async (key, fn) => {
    setBusy(key)
    try { await fn() } catch (error) {
      toast({ type: 'error', title: 'ConLicitação', message: apiError(error, 'Falha na consulta.') })
    } finally { setBusy('') }
  }

  const loadFilters = () => run('filters', async () => {
    const { data } = await conlicitacaoApi.labFilters()
    setFilters(data)
    const first = data.data.filtros?.[0]?.id
    if (first) {
      setFilterId(String(first))
      const response = await conlicitacaoApi.labBulletins(first, { per_page: 30 })
      setBulletins(response.data)
    }
  })

  const loadBulletins = (id) => run('bulletins', async () => {
    setFilterId(String(id))
    const { data } = await conlicitacaoApi.labBulletins(id, { per_page: 30 })
    setBulletins(data)
  })

  const openBulletin = (id) => run(`bulletin-${id}`, async () => {
    const { data } = await conlicitacaoApi.labBulletin(id)
    setBulletin({ ...data, id })
  })

  const filtered = useMemo(() => {
    if (!bulletin) return { licitacoes: [], acompanhamentos: [] }
    const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean)
    const match = (row) => !terms.length || terms.every((term) => JSON.stringify(row).toLowerCase().includes(term))
    return {
      licitacoes: bulletin.data.licitacoes.filter(match),
      acompanhamentos: bulletin.data.acompanhamentos.filter(match),
    }
  }, [bulletin, query])

  const quality = bulletin?.data.qualidade

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="btn-primary flex items-center gap-2" disabled={Boolean(busy)} onClick={loadFilters}>
          {busy === 'filters' ? <RefreshCw size={15} className="animate-spin" /> : <Search size={15} />} Carregar filtros e boletins
        </button>
        {filters && <span className="text-xs text-slate-500">Cliente: {filters.data.cliente?.razao_social} ({filters.data.cliente?.id}) · <Latency ms={filters.latency_ms} /></span>}
      </div>

      {filters && (
        <div className="flex flex-wrap gap-2">
          {filters.data.filtros.map((item) => (
            <button key={item.id} type="button" onClick={() => loadBulletins(item.id)} className={`rounded-lg border px-3 py-2 text-left text-xs ${String(item.id) === filterId ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30' : 'border-slate-200 dark:border-slate-700'}`}>
              <span className="block font-semibold">{item.descricao} · #{item.id}</span>
              <span className="text-slate-500">
                Turnos: {Object.entries(item.periodos || {}).filter(([, on]) => on).map(([name]) => name).join(', ') || '—'}
                {' · '}último boletim {item.ultimo_boletim?.numero_edicao} em {dateTime(item.ultimo_boletim?.datahora_fechamento)}
              </span>
            </button>
          ))}
        </div>
      )}

      {bulletins && (
        <div className="max-h-64 overflow-auto rounded-lg border border-slate-200 dark:border-slate-700">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-slate-50 text-left dark:bg-slate-900">
              <tr><th className="p-2">Edição</th><th className="p-2">ID</th><th className="p-2">Fechamento</th><th className="p-2" /></tr>
            </thead>
            <tbody>
              {bulletins.data.boletins.map((row) => (
                <tr key={row.id} className={`border-t border-slate-100 dark:border-slate-800 ${bulletin?.id === row.id ? 'bg-blue-50 dark:bg-blue-950/30' : ''}`}>
                  <td className="p-2">{row.numero_edicao}</td>
                  <td className="p-2 font-mono">{row.id}</td>
                  <td className="p-2">{dateTime(row.datahora_fechamento)}</td>
                  <td className="p-2 text-right">
                    <button type="button" className="btn-ghost text-xs" disabled={Boolean(busy)} onClick={() => openBulletin(row.id)}>
                      {busy === `bulletin-${row.id}` ? 'Abrindo...' : 'Abrir'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="p-2 text-[11px] text-slate-500">Total de boletins do filtro: {bulletins.data.filtro?.total_boletins ?? '—'} · <Latency ms={bulletins.latency_ms} /></p>
        </div>
      )}

      {bulletin && quality && (
        <>
          <div className="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold">
                Boletim {bulletin.data.boletim?.numero_edicao} · {bulletin.data.licitacoes.length} licitações · {bulletin.data.acompanhamentos.length} acompanhamentos
              </p>
              <span className="text-xs text-slate-500">Tempo de resposta: <Latency ms={bulletin.latency_ms} /> · Soma dos valores estimados: {money(quality.total_estimated_value)}</span>
            </div>
            <div className="mt-4 grid gap-6 lg:grid-cols-2">
              <QualityTable title="Preenchimento — licitações" rates={quality.tenders} />
              <div className="space-y-4">
                <QualityTable title="Preenchimento — acompanhamentos" rates={quality.follow_ups} />
                <p className="text-xs text-slate-600 dark:text-slate-300"><b>Situação:</b> {quality.situacao.map(([k, v]) => `${k} (${v})`).join(' · ')}</p>
                <p className="text-xs text-slate-600 dark:text-slate-300"><b>UF:</b> {quality.uf.map(([k, v]) => `${k} (${v})`).join(' · ')}</p>
                <p className="text-xs text-slate-600 dark:text-slate-300"><b>Tipos de acompanhamento:</b> {quality.follow_up_kinds.map(([k, v]) => `${k} (${v})`).join(' · ') || '—'}</p>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <input className="input max-w-sm" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filtrar: switch, telecom, MT, informática..." />
            {['licitacoes', 'acompanhamentos'].map((key) => (
              <button key={key} type="button" onClick={() => setView(key)} className={view === key ? 'btn-primary text-xs' : 'btn-ghost text-xs'}>
                {key === 'licitacoes' ? `Licitações (${filtered.licitacoes.length})` : `Acompanhamentos (${filtered.acompanhamentos.length})`}
              </button>
            ))}
          </div>
          <div className="space-y-3">
            {view === 'licitacoes'
              ? filtered.licitacoes.map((tender) => <TenderCard key={tender.id} tender={tender} bulletinId={bulletin.id} onTrace={onTrace} />)
              : filtered.acompanhamentos.map((item) => <FollowUpCard key={item.id} item={item} />)}
          </div>
        </>
      )}
    </div>
  )
}

function TraceTab({ initialId, users, onWatchChat }) {
  const { toast, confirm } = useToast()
  const [biddingId, setBiddingId] = useState(initialId || '')
  const [maxBulletins, setMaxBulletins] = useState(15)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState('')
  const [userId, setUserId] = useState('')

  useEffect(() => { if (initialId) setBiddingId(String(initialId)) }, [initialId])
  useEffect(() => { if (!userId && users?.length) setUserId(String(users[0].id)) }, [users, userId])

  const trace = async () => {
    const id = Number(biddingId)
    if (!Number.isInteger(id) || id <= 0) return
    setBusy('trace')
    setResult(null)
    try {
      const { data } = await conlicitacaoApi.labTrace(id, maxBulletins)
      setResult(data)
    } catch (error) {
      toast({ type: 'error', title: 'Rastreio', message: apiError(error, 'Falha ao rastrear a licitação.') })
    } finally { setBusy('') }
  }

  const toggleMonitoring = async (start) => {
    const id = Number(biddingId)
    const verb = start ? 'Ativar' : 'Desativar'
    if (!await confirm(`${verb} o monitoramento de chat da licitação ${id} para o usuário ConLicitação ${userId}? Isso altera a sua conta na ConLicitação.`, { title: `${verb} monitoramento` })) return
    setBusy('monitor')
    try {
      if (start) await conlicitacaoApi.startMonitoring(id, Number(userId))
      else await conlicitacaoApi.stopMonitoring(id, Number(userId))
      toast({ type: 'success', title: 'Monitoramento', message: start ? 'Ativado. Pode levar alguns minutos para as mensagens aparecerem.' : 'Desativado.' })
      await trace()
    } catch (error) {
      toast({ type: 'error', title: 'Monitoramento', message: apiError(error, 'A ConLicitação recusou a operação.') })
    } finally { setBusy('') }
  }

  const data = result?.data
  const latest = data?.appearances?.at(-1)

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <label className="flex-1 text-xs font-medium text-slate-600 dark:text-slate-300">
          Nº ConLicitação
          <input className="input mt-1.5" type="number" min="1" value={biddingId} onChange={(event) => setBiddingId(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && trace()} placeholder="Ex.: 19399420" />
        </label>
        <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
          Boletins a varrer
          <select className="input mt-1.5" value={maxBulletins} onChange={(event) => setMaxBulletins(Number(event.target.value))}>
            {[6, 15, 30, 60].map((value) => <option key={value} value={value}>{value} (~{Math.round(value / 3)} dias)</option>)}
          </select>
        </label>
        <button type="button" className="btn-primary flex items-center gap-2" disabled={Boolean(busy)} onClick={trace}>
          {busy === 'trace' ? <RefreshCw size={15} className="animate-spin" /> : <Route size={15} />}
          {busy === 'trace' ? 'Varrendo boletins...' : 'Rastrear'}
        </button>
      </div>
      <p className="text-xs text-slate-500">A API não tem busca por número: a VPS lê os boletins recentes (3 em paralelo) e monta o histórico da licitação e dos acompanhamentos ligados a ela.</p>

      {data && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 p-4 text-xs dark:border-slate-700">
            <p className={`text-sm font-semibold ${data.found ? 'text-emerald-700 dark:text-emerald-300' : 'text-rose-700 dark:text-rose-300'}`}>
              {data.found ? `Encontrada em ${data.appearances.length} boletim(ns) e ${data.follow_ups.length} acompanhamento(s)` : 'Não encontrada nos boletins varridos'}
            </p>
            <p className="mt-1 text-slate-500">
              {data.bulletins_scanned}/{data.bulletins_requested} boletins lidos até {dateTime(data.oldest_bulletin_scanned)} · tempo total <Latency ms={data.elapsed_ms} /> · boletim mais lento <Latency ms={data.bulletin_latency_ms.max} />
              {data.errors.length > 0 && <span className="text-rose-600"> · {data.errors.length} boletim(ns) falharam</span>}
            </p>
          </div>

          {latest && <TenderCard tender={latest.licitacao} bulletinId={latest.bulletin_id} />}

          {data.appearances.length > 0 && (
            <SectionCard title="Linha do tempo nos boletins" description="O mesmo Nº ConLicitação reaparece quando há atualização. As mudanças entre boletins mostram o que a API realmente acompanha.">
              <ol className="space-y-2 text-xs">
                {data.appearances.map((item) => (
                  <li key={item.bulletin_id} className="rounded-lg border border-slate-200 p-3 dark:border-slate-700">
                    <p className="font-semibold">Boletim {item.bulletin_number} · {dateTime(item.bulletin_closed_at)} · situação {item.licitacao.situacao || '—'}</p>
                    {item.changes?.length > 0 && (
                      <ul className="mt-1 space-y-0.5 text-slate-600 dark:text-slate-300">
                        {item.changes.map((change) => <li key={change.field}><span className="font-mono">{change.field}</span>: {String(change.before ?? '—').slice(0, 80)} → <b>{String(change.after ?? '—').slice(0, 80)}</b></li>)}
                      </ul>
                    )}
                    {item.changes && !item.changes.length && <p className="mt-1 text-slate-500">Sem mudança nos campos acompanhados.</p>}
                  </li>
                ))}
              </ol>
            </SectionCard>
          )}

          {data.follow_ups.length > 0 && (
            <div className="space-y-3">{data.follow_ups.map((item) => <FollowUpCard key={`${item.bulletin_id}-${item.id}`} item={item} />)}</div>
          )}

          <SectionCard title="Monitoramento de chat" description="Disponível quando a licitação é eletrônica em portal suportado (has_electronic_trading).">
            {data.monitored ? (
              <div className="space-y-2 text-xs">
                <p className="font-semibold text-emerald-700 dark:text-emerald-300">Monitorada · {data.monitored.trading_situation || 'situação ainda não informada'} · portal {data.monitored.source_id} · sala {data.monitored.trading_id}</p>
                <p>Última mensagem: {dateTime(data.monitored.last_message_time)} · lotes: {data.monitored.lots?.length || 0} · por {data.monitored.monitored_by?.map((user) => user.nome).join(', ')}</p>
                <button type="button" className="btn-primary text-xs" onClick={() => onWatchChat(Number(biddingId))}>Abrir chat ao vivo</button>
              </div>
            ) : (
              <p className="text-xs text-slate-500">Esta licitação ainda não está monitorada na sua conta.</p>
            )}
            <div className="mt-3 flex flex-wrap items-end gap-2">
              <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
                Usuário ConLicitação
                <select className="input mt-1.5" value={userId} onChange={(event) => setUserId(event.target.value)}>
                  {(users || []).map((user) => <option key={user.id} value={user.id}>{user.nome} ({user.id})</option>)}
                </select>
              </label>
              <button type="button" className="btn-primary flex items-center gap-1 text-xs" disabled={!userId || Boolean(busy)} onClick={() => toggleMonitoring(true)}><Play size={13} /> Ativar monitoramento</button>
              <button type="button" className="btn-ghost flex items-center gap-1 text-xs" disabled={!userId || Boolean(busy) || !data.monitored} onClick={() => toggleMonitoring(false)}><Square size={13} /> Desativar</button>
            </div>
          </SectionCard>
        </div>
      )}
    </div>
  )
}

function ChatTab({ watchId }) {
  const { toast } = useToast()
  const [monitored, setMonitored] = useState(null)
  const [selected, setSelected] = useState(watchId || null)
  const [messages, setMessages] = useState([])
  const [meta, setMeta] = useState(null)
  const [auto, setAuto] = useState(false)
  const [loading, setLoading] = useState(false)
  const seen = useRef(new Map())
  const primed = useRef(false)

  useEffect(() => { if (watchId) setSelected(watchId) }, [watchId])

  const loadMonitored = async () => {
    try {
      const { data } = await conlicitacaoApi.labMonitored({ per_page: 50 })
      setMonitored(data)
    } catch (error) {
      toast({ type: 'error', title: 'Monitoradas', message: apiError(error, 'Falha ao listar licitações monitoradas.') })
    }
  }

  useEffect(() => { loadMonitored() }, [])

  const loadMessages = async (biddingId = selected) => {
    if (!biddingId) return
    setLoading(true)
    try {
      const { data } = await conlicitacaoApi.labMessages(biddingId, { per_page: 100 })
      const now = Date.now()
      // A primeira leitura só registra o histórico; depois, ids novos são
      // destacados e o atraso de detecção é medido.
      const initial = !primed.current
      primed.current = true
      const rows = (data.data.trading_messages || []).map((message) => {
        if (!seen.current.has(message.id)) seen.current.set(message.id, { at: now, initial })
        return { ...message, firstSeen: seen.current.get(message.id) }
      })
      rows.sort((a, b) => String(b.message_time).localeCompare(String(a.message_time)))
      setMessages(rows)
      setMeta({ latency: data.latency_ms, pagination: data.data.pagination, at: new Date() })
    } catch (error) {
      toast({ type: 'error', title: 'Mensagens', message: apiError(error, 'Falha ao ler o chat.') })
    } finally { setLoading(false) }
  }

  useEffect(() => {
    seen.current = new Map()
    primed.current = false
    setMessages([])
    loadMessages(selected)
  }, [selected])

  useEffect(() => {
    if (!auto || !selected) return undefined
    const timer = setInterval(() => loadMessages(selected), 30_000)
    return () => clearInterval(timer)
  }, [auto, selected])

  const list = monitored?.data?.electronics_trading || []

  return (
    <div className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold text-slate-600 dark:text-slate-300">Licitações monitoradas ({monitored?.data?.total_entries ?? '…'})</p>
          <button type="button" className="btn-ghost text-xs" onClick={loadMonitored}>Atualizar</button>
        </div>
        {monitored?.data?.monitored_source_id_list && <p className="text-[11px] text-slate-500">Portais suportados: {monitored.data.monitored_source_id_list.join(', ')}</p>}
        {list.map((row) => (
          <button key={row.id} type="button" onClick={() => setSelected(row.bidding_id)} className={`w-full rounded-lg border p-3 text-left text-xs ${selected === row.bidding_id ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30' : 'border-slate-200 dark:border-slate-700'}`}>
            <span className="block font-semibold">{row.bidding?.edital || row.edital || '—'} · Nº {row.bidding_id}</span>
            <span className="block text-slate-500">{row.bidding?.public_body?.nome}</span>
            <span className="block">{row.trading_situation || row.bidding?.bidding_grouping?.descricao || 'sem situação'} · última msg {dateTime(row.last_message_time)}</span>
            {row.have_new_messages && <span className="mt-1 inline-block rounded bg-amber-100 px-1.5 text-amber-800">mensagens novas</span>}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-semibold">{selected ? `Chat da licitação ${selected}` : 'Selecione uma licitação'}</p>
          <button type="button" className="btn-ghost flex items-center gap-1 text-xs" disabled={!selected || loading} onClick={() => loadMessages()}>
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Verificar agora
          </button>
          <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={auto} onChange={(event) => setAuto(event.target.checked)} /> Atualizar a cada 30 s</label>
        </div>
        {meta && <p className="text-[11px] text-slate-500">{meta.pagination?.total_entries ?? messages.length} mensagens · resposta <Latency ms={meta.latency} /> · verificado {meta.at.toLocaleTimeString('pt-BR')}</p>}
        <ol className="max-h-[32rem] space-y-2 overflow-auto">
          {messages.map((message) => {
            const fresh = message.firstSeen && !message.firstSeen.initial
            const delay = fresh ? Math.round((message.firstSeen.at - new Date(message.message_time).getTime()) / 1000) : null
            return (
              <li key={message.id} className={`rounded-lg border p-3 text-xs ${fresh ? 'border-amber-400 bg-amber-50 dark:bg-amber-950/30' : 'border-slate-200 dark:border-slate-700'}`}>
                <p className="font-semibold">{message.message_holder} <span className="font-normal text-slate-500">· {dateTime(message.message_time)}{message.lot != null && ` · lote ${message.lot}`}</span></p>
                <p className="mt-1 whitespace-pre-wrap">{message.message_highlight}</p>
                {delay != null && <p className="mt-1 text-[11px] text-amber-700">Nova · detectada {delay}s após a hora da mensagem</p>}
              </li>
            )
          })}
          {selected && !messages.length && !loading && <li className="text-xs text-slate-500">Nenhuma mensagem ainda.</li>}
        </ol>
      </div>
    </div>
  )
}

export default function ConlicitacaoLab({ enabled }) {
  const [tab, setTab] = useState('bulletins')
  const [traceId, setTraceId] = useState('')
  const [watchId, setWatchId] = useState(null)
  const [users, setUsers] = useState(null)

  useEffect(() => {
    if (!enabled) return
    conlicitacaoApi.labUsers().then(({ data }) => setUsers(data.data.users || [])).catch(() => setUsers([]))
  }, [enabled])

  if (!enabled) return null

  return (
    <SectionCard title="Avaliação da API (dados reais)" description="Consultas somente leitura feitas pela VPS. Os valores aparecem só para administradores; os links assinados dos documentos nunca saem do servidor.">
      <div className="mb-4 flex flex-wrap gap-2 border-b border-slate-200 pb-3 dark:border-slate-700">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button key={key} type="button" onClick={() => setTab(key)} className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold ${tab === key ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700'}`}>
            <Icon size={14} /> {label}
          </button>
        ))}
        {users && <span className="ml-auto self-center text-[11px] text-slate-500">Usuários ConLicitação: {users.map((user) => `${user.nome} (${user.id})`).join(', ') || '—'}</span>}
      </div>
      <div className={tab === 'bulletins' ? '' : 'hidden'}><BulletinsTab onTrace={(id) => { setTraceId(String(id)); setTab('trace') }} /></div>
      <div className={tab === 'trace' ? '' : 'hidden'}><TraceTab initialId={traceId} users={users} onWatchChat={(id) => { setWatchId(id); setTab('chat') }} /></div>
      {tab === 'chat' && <ChatTab watchId={watchId} />}
    </SectionCard>
  )
}
