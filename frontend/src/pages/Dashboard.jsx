import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { documentsApi, downloadBlob, editaisApi, exportApi, opsApi } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { useMarket } from '../contexts/MarketContext'
import { useToast } from '../contexts/ToastContext'

const AI_FEATURES_ENABLED = import.meta.env.VITE_AI_FEATURES_ENABLED === '1'

function formatDate(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

async function readCrmSync() {
  try {
    const r = await fetch(`/crm/tor-sync.json?ts=${Date.now()}`, { cache: 'no-store' })
    if (!r.ok) return null
    return await r.json()
  } catch { return null }
}

const SUITE_STEPS = [
  { key: 'radar', title: 'Radar de oportunidades', description: 'Encontre editais aderentes antes de importar para analise.', path: '/radar', cta: 'Buscar' },
  { key: 'alerts', title: 'Alertas operacionais', description: 'Acompanhe prazos, filas, atrasos e proximas sessoes.', path: '/controle', cta: 'Acompanhar' },
  { key: 'analysis', title: 'Analise IA do edital', description: 'Extraia requisitos, itens, riscos e perguntas do edital.', path: '/upload', cta: 'Analisar' },
  { key: 'matching', title: 'Matching tecnico', description: 'Compare requisitos com catalogo, datasheets e gaps.', path: '/inteligencia/datasheets', cta: 'Comparar' },
  { key: 'documents', title: 'Proposta e documentos', description: 'Transforme analises em relatorios e exportacoes.', path: '/relatorios', cta: 'Gerar' },
  { key: 'crm', title: 'CRM e pipeline', description: 'Controle decisao, responsaveis, disputa e resultado.', path: '/crm', cta: 'Abrir' },
]
const VISIBLE_SUITE_STEPS = AI_FEATURES_ENABLED
  ? SUITE_STEPS
  : SUITE_STEPS.filter((step) => !['analysis', 'matching'].includes(step.key))

function stepState(key, { nEditais, totalRequirements, jobs, crm }) {
  if (key === 'radar') return { label: 'Disponivel', tone: 'blue' }
  if (key === 'alerts') {
    const pending = (jobs?.active_count ?? 0) + (jobs?.stale_count ?? 0) + (crm?.upcoming_auctions_count ?? 0)
    return pending > 0 ? { label: `${pending} alertas`, tone: 'amber' } : { label: 'Sem pendencias', tone: 'emerald' }
  }
  if (key === 'analysis') return nEditais > 0 ? { label: `${nEditais} editais`, tone: 'emerald' } : { label: 'Importar edital', tone: 'slate' }
  if (key === 'matching') return totalRequirements > 0 ? { label: `${totalRequirements} requisitos`, tone: 'emerald' } : { label: 'Aguardando analise', tone: 'slate' }
  if (key === 'documents') return nEditais > 0 ? { label: 'Pronto para exportar', tone: 'blue' } : { label: 'Sem dados', tone: 'slate' }
  if (key === 'crm') return (crm?.active_pipeline ?? 0) > 0 ? { label: `${crm.active_pipeline} ativos`, tone: 'emerald' } : { label: 'Criar pipeline', tone: 'slate' }
  return { label: 'Disponivel', tone: 'slate' }
}

function stateClass(tone) {
  if (tone === 'emerald') return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300'
  if (tone === 'amber') return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300'
  if (tone === 'blue') return 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-300'
  return 'border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300'
}

export default function Dashboard() {
  const [editais,     setEditais]     = useState([])
  const [loading,     setLoading]     = useState(true)
  const [exporting,   setExporting]   = useState(null)
  const [deleting,    setDeleting]    = useState(null)
  const [apiOnline,   setApiOnline]   = useState(null)
  const [opsSummary,  setOpsSummary]  = useState(null)
  const [crmSync,     setCrmSync]     = useState(null)
  const [signatureAlert, setSignatureAlert] = useState(null)
  const { user, isEditor } = useAuth()
  const market = useMarket()
  const { toast, confirm } = useToast()
  const navigate           = useNavigate()

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      const [eRes, oRes, cRes] = await Promise.allSettled([
        editaisApi.list(), opsApi.summary(), readCrmSync(),
      ])
      const sRes = await documentsApi.signatureAlert().catch(() => null)
      if (!active) return
      const editalRows = eRes.status === 'fulfilled' && Array.isArray(eRes.value.data) ? eRes.value.data : []
      setEditais(editalRows)
      if (oRes.status === 'fulfilled') { setOpsSummary(oRes.value.data); setApiOnline(true) }
      else { setOpsSummary(null); setApiOnline(false) }
      setCrmSync(cRes.status === 'fulfilled' ? cRes.value : null)
      setSignatureAlert(sRes?.data || null)
      setLoading(false)
    }
    load()
    return () => { active = false }
  }, [])

  const handleExport = async (e, id, tipo) => {
    e.stopPropagation()
    setExporting(`${id}-${tipo}`)
    try {
      const r = await { xlsx: exportApi.xlsx, csv: exportApi.csv }[tipo](id)
      downloadBlob(r.data, `${market.labels.source_document}_${id}_resultado.${tipo}`)
      toast({ type: 'success', message: `${tipo.toUpperCase()} gerado.` })
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || `Erro ao exportar ${tipo.toUpperCase()}.` })
    } finally { setExporting(null) }
  }

  const handleDelete = async (e, edital) => {
    e.stopPropagation()
    const ok = await confirm(
      `Apagar "${edital.filename}"? O PDF, chunks, requisitos e resultados vinculados serao removidos.`,
      { title: market.labels.delete_source_document_title },
    )
    if (!ok) return
    setDeleting(edital.id)
    try {
      await editaisApi.remove(edital.id)
      setEditais((rows) => rows.filter((row) => row.id !== edital.id))
      toast({ type: 'success', message: market.labels.delete_source_document_success })
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Erro ao apagar edital.' })
    } finally {
      setDeleting(null)
    }
  }

  const totalChunks       = useMemo(() => opsSummary?.editais?.total_chunks       ?? editais.reduce((s, e) => s + (e.chunks || 0), 0),       [editais, opsSummary])
  const totalRequirements = useMemo(() => opsSummary?.editais?.total_requirements ?? editais.reduce((s, e) => s + (e.requirements || 0), 0), [editais, opsSummary])
  const jobs   = opsSummary?.jobs
  const crm    = opsSummary?.crm
  const nEditais = opsSummary?.editais?.total_editais ?? editais.length

  return (
    <div className="p-6 lg:p-8 space-y-6">

      {/* ── Cabeçalho ─────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white">
            {user?.tenant?.name || 'Portal'}
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            {new Date().toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {apiOnline !== null && (
            <span className={`flex items-center gap-1.5 text-xs font-mono px-2.5 py-1 rounded-full border ${
              apiOnline
                ? 'border-green-500/20 bg-green-500/10 text-green-600 dark:text-green-400'
                : 'border-yellow-500/20 bg-yellow-500/10 text-yellow-600 dark:text-yellow-400'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${apiOnline ? 'bg-green-500' : 'bg-yellow-500'}`} />
              {apiOnline ? 'API online' : 'API offline'}
            </span>
          )}
          {isEditor && (
            <button onClick={() => navigate('/upload')} className="btn-primary">
              {market.labels.upload_source_document}
            </button>
          )}
        </div>
      </div>

      {/* ── Números ───────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          { label: market.labels.source_document_plural_title, value: nEditais, action: () => navigate('/upload') },
          { label: 'Chunks',     value: totalChunks.toLocaleString('pt-BR') },
          { label: 'Requisitos', value: totalRequirements.toLocaleString('pt-BR') },
          { label: 'CRM ativos', value: crm?.active_pipeline ?? '—',      action: () => navigate('/crm') },
        ].map(({ label, value, action }) => (
          <button
            key={label}
            type="button"
            onClick={action}
            disabled={!action}
            className={`rounded-lg border p-4 text-left transition-colors
              border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800
              ${action ? 'hover:border-slate-300 dark:hover:bg-slate-700 cursor-pointer' : 'cursor-default'}`}
          >
            <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
            <p className="mt-2 text-2xl font-bold text-slate-900 dark:text-white">{loading ? '—' : value}</p>
          </button>
        ))}
      </div>

      {signatureAlert?.count > 0 && (
        <button
          type="button"
          onClick={() => navigate(signatureAlert.request?.id ? `/assinatura?request=${signatureAlert.request.id}` : '/assinatura')}
          className="w-full rounded-lg border border-amber-200 bg-amber-50 p-4 text-left transition-colors hover:bg-amber-100 dark:border-amber-800 dark:bg-amber-950/40 dark:hover:bg-amber-950/60"
        >
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm font-semibold text-amber-900 dark:text-amber-200">Voce tem {signatureAlert.count} documento(s) aguardando assinatura</p>
              <p className="mt-1 text-xs text-amber-800 dark:text-amber-300">
                {signatureAlert.request?.document?.title || 'Abra a seção de documentos para continuar o processo.'}
              </p>
            </div>
            <span className="text-sm font-semibold text-amber-900 dark:text-amber-200">Leve-me</span>
          </div>
        </button>
      )}

      <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-800">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm font-semibold text-slate-900 dark:text-white">Suite de licitacoes</p>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Os 6 modulos principais para o usuario nao precisar assinar ferramentas separadas.
            </p>
          </div>
          <button type="button" onClick={() => navigate('/suite')} className="btn-ghost">
            Ver suite completa
          </button>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {VISIBLE_SUITE_STEPS.map((step) => {
            const status = stepState(step.key, { nEditais, totalRequirements, jobs, crm })
            return (
              <button
                key={step.key}
                type="button"
                onClick={() => navigate(step.path)}
                className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-left transition-colors hover:border-blue-200 hover:bg-white dark:border-slate-700 dark:bg-slate-900 dark:hover:border-blue-800 dark:hover:bg-slate-800"
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm font-semibold text-slate-950 dark:text-white">{step.title}</p>
                  <span className={`shrink-0 rounded-md border px-2 py-1 text-[11px] font-semibold ${stateClass(status.tone)}`}>
                    {status.label}
                  </span>
                </div>
                <p className="mt-2 min-h-[40px] text-xs leading-5 text-slate-500 dark:text-slate-400">{step.description}</p>
                <p className="mt-3 text-xs font-semibold text-blue-600 dark:text-blue-300">{step.cta}</p>
              </button>
            )
          })}
        </div>
      </div>

      {/* ── Sinais operacionais ────────────────────────────────────────── */}
      {!loading && (
        <div className="grid gap-4 lg:grid-cols-2">

          {/* Fila de jobs */}
          <div className="rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800 p-5">
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm font-semibold text-slate-900 dark:text-white">Fila de processamento</p>
              <button onClick={() => navigate('/jobs')} className="text-xs text-slate-400 dark:text-slate-400 hover:text-slate-600 dark:hover:text-white">
                Ver tudo →
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3 mb-4">
              {[
                { label: 'Em andamento', value: jobs?.active_count ?? 0,  warn: (jobs?.active_count ?? 0) > 0 },
                { label: 'Atrasados',    value: jobs?.stale_count  ?? 0,  warn: (jobs?.stale_count  ?? 0) > 0 },
              ].map(({ label, value, warn }) => (
                <div key={label} className={`rounded-lg border p-3 ${
                  warn
                    ? 'border-yellow-500/20 bg-yellow-500/5 dark:bg-yellow-500/5'
                    : 'border-slate-100 bg-slate-50 dark:border-slate-700 dark:bg-slate-900'
                }`}>
                  <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
                  <p className={`mt-1 text-xl font-bold ${warn ? 'text-yellow-600 dark:text-yellow-400' : 'text-slate-900 dark:text-white'}`}>{value}</p>
                </div>
              ))}
            </div>
            {jobs?.active_jobs?.length ? (
              <div className="space-y-2">
                {jobs.active_jobs.map(job => (
                  <div key={job.id} className="flex items-center justify-between rounded-lg border border-slate-100 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-3 py-2">
                    <div className="min-w-0">
                      <p className="truncate text-xs font-medium text-slate-800 dark:text-white">{job.label}</p>
                      <p className="text-[11px] text-slate-400 dark:text-slate-400">{job.status}</p>
                    </div>
                    <span className="ml-3 text-sm font-bold text-slate-600 dark:text-red-400 flex-shrink-0">{job.progress_pct}%</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 dark:text-slate-500">Nenhum processamento em andamento.</p>
            )}
          </div>

          {/* CRM */}
          <div className="rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800 p-5">
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm font-semibold text-slate-900 dark:text-white">CRM comercial</p>
              <button onClick={() => navigate('/crm')} className="text-xs text-slate-400 dark:text-slate-400 hover:text-slate-600 dark:hover:text-white">
                Abrir →
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3 mb-4">
              {[
                { label: 'Atenção',  value: crm?.attention_required    ?? 0, warn: (crm?.attention_required    ?? 0) > 0 },
                { label: 'Disputas próximas', value: crm?.upcoming_auctions_count ?? 0, warn: (crm?.upcoming_auctions_count ?? 0) > 0 },
              ].map(({ label, value, warn }) => (
                <div key={label} className={`rounded-lg border p-3 ${
                  warn
                    ? 'border-red-500/20 bg-red-500/5'
                    : 'border-slate-100 bg-slate-50 dark:border-slate-700 dark:bg-slate-900'
                }`}>
                  <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
                  <p className={`mt-1 text-xl font-bold ${warn ? 'text-red-600 dark:text-red-400' : 'text-slate-900 dark:text-white'}`}>{value}</p>
                </div>
              ))}
            </div>
            {crm?.upcoming_auctions?.length ? (
              <div className="space-y-2">
                {crm.upcoming_auctions.map(n => (
                  <div key={n.id} className="rounded-lg border border-slate-100 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-3 py-2">
                    <p className="text-xs font-medium text-slate-800 dark:text-white truncate">{n.number || n.title || 'Sem número'}</p>
                    <p className="text-[11px] text-slate-400 dark:text-slate-400 mt-0.5">{n.organ_name || '—'} · {n.auction_date ? new Date(n.auction_date).toLocaleDateString('pt-BR') : 'sem data'}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 dark:text-slate-500">Nenhuma disputa nos próximos 7 dias.</p>
            )}
          </div>
        </div>
      )}

      {/* ── Editais ───────────────────────────────────────────────────── */}
      <div className="rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800 p-5">
        <div className="flex items-center justify-between mb-4">
          <p className="text-sm font-semibold text-slate-900 dark:text-white">{market.labels.source_document_plural_title}</p>
          {crmSync && (
            <p className="text-xs text-slate-400 dark:text-slate-500">
              CRM em {formatDate(crmSync.builtAt)}
            </p>
          )}
        </div>

        {loading ? (
          <div className="space-y-2">
            {[1,2,3].map(i => <div key={i} className="h-14 rounded-lg bg-slate-100 dark:bg-slate-900 animate-pulse" />)}
          </div>
        ) : editais.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-200 dark:border-slate-700 py-12 text-center">
            <p className="text-sm text-slate-400 dark:text-slate-400">{market.labels.empty_source_documents}</p>
            {isEditor && (
              <button onClick={() => navigate('/upload')} className="btn-primary mt-4">
                {market.labels.send_first_source_document}
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            {editais.map(edital => (
              <div
                key={edital.id}
                onClick={() => navigate(`/editais/${edital.id}`)}
                className="flex items-center gap-4 rounded-lg border border-slate-100 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-4 py-3 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
              >
                <div className="flex-shrink-0 w-8 h-8 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 grid place-items-center">
                  <span className="text-[9px] font-bold text-slate-400 dark:text-slate-400">PDF</span>
                </div>

                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-900 dark:text-white truncate">{edital.filename}</p>
                  <p className="text-xs text-slate-400 dark:text-slate-400 mt-0.5">
                    {edital.chunks || 0} chunks · {edital.requirements || 0} requisitos
                    {edital.parsed_at && ` · ${formatDate(edital.parsed_at)}`}
                  </p>
                </div>

                <div className="flex items-center gap-1.5 flex-shrink-0" onClick={e => e.stopPropagation()}>
                  {AI_FEATURES_ENABLED && (
                    <>
                      <button onClick={() => navigate(`/editais/${edital.id}/chat`)}
                        className="px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-[11px] font-mono text-slate-500 dark:text-slate-300 hover:text-slate-800 dark:hover:text-white hover:bg-white dark:hover:bg-slate-700 transition-colors">
                        Chat
                      </button>
                      <button onClick={() => navigate(`/editais/${edital.id}/analise-llm`)}
                        className="px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-[11px] font-mono text-slate-500 dark:text-slate-300 hover:text-slate-800 dark:hover:text-white hover:bg-white dark:hover:bg-slate-700 transition-colors">
                        Análise
                      </button>
                    </>
                  )}
                  {['xlsx','csv'].map(tipo => (
                    <button key={tipo} onClick={e => handleExport(e, edital.id, tipo)}
                      disabled={Boolean(exporting)}
                      className="px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-[11px] font-mono text-slate-400 dark:text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-white dark:hover:bg-slate-700 transition-colors disabled:opacity-40">
                      {exporting === `${edital.id}-${tipo}` ? '…' : tipo.toUpperCase()}
                    </button>
                  ))}
                  {isEditor && (
                    <button onClick={e => handleDelete(e, edital)}
                      disabled={deleting === edital.id}
                      className="px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-[11px] font-mono text-slate-400 dark:text-slate-400 hover:text-red-700 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-950/40 transition-colors disabled:opacity-40">
                      {deleting === edital.id ? '...' : 'Apagar'}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
