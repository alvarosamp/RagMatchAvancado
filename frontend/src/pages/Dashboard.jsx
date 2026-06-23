import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { downloadBlob, editaisApi, exportApi, opsApi } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'

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

export default function Dashboard() {
  const [editais,     setEditais]     = useState([])
  const [loading,     setLoading]     = useState(true)
  const [exporting,   setExporting]   = useState(null)
  const [apiOnline,   setApiOnline]   = useState(null)
  const [opsSummary,  setOpsSummary]  = useState(null)
  const [crmSync,     setCrmSync]     = useState(null)
  const { user, isEditor } = useAuth()
  const { toast }          = useToast()
  const navigate           = useNavigate()

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      const [eRes, oRes, cRes] = await Promise.allSettled([
        editaisApi.list(), opsApi.summary(), readCrmSync(),
      ])
      if (!active) return
      setEditais(eRes.status === 'fulfilled' ? eRes.value.data || [] : [])
      if (oRes.status === 'fulfilled') { setOpsSummary(oRes.value.data); setApiOnline(true) }
      else { setOpsSummary(null); setApiOnline(false) }
      setCrmSync(cRes.status === 'fulfilled' ? cRes.value : null)
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
      downloadBlob(r.data, `edital_${id}_resultado.${tipo}`)
      toast({ type: 'success', message: `${tipo.toUpperCase()} gerado.` })
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || `Erro ao exportar ${tipo.toUpperCase()}.` })
    } finally { setExporting(null) }
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
          <h1 className="text-xl font-bold text-stone-900 dark:text-white">
            {user?.tenant?.name || 'Portal'}
          </h1>
          <p className="text-sm text-stone-500 dark:text-gray-500 mt-0.5">
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
              Enviar edital
            </button>
          )}
        </div>
      </div>

      {/* ── Números ───────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          { label: 'Editais',    value: nEditais,                         action: () => navigate('/upload') },
          { label: 'Chunks',     value: totalChunks.toLocaleString('pt-BR') },
          { label: 'Requisitos', value: totalRequirements.toLocaleString('pt-BR') },
          { label: 'CRM ativos', value: crm?.active_pipeline ?? '—',      action: () => navigate('/crm') },
        ].map(({ label, value, action }) => (
          <button
            key={label}
            type="button"
            onClick={action}
            disabled={!action}
            className={`rounded-xl border p-4 text-left transition-colors
              border-stone-200 bg-white dark:border-slate-border dark:bg-slate-card
              ${action ? 'hover:border-stone-300 dark:hover:bg-slate-hover cursor-pointer' : 'cursor-default'}`}
          >
            <p className="text-xs text-stone-500 dark:text-gray-500">{label}</p>
            <p className="mt-2 text-2xl font-bold text-stone-900 dark:text-white">{loading ? '—' : value}</p>
          </button>
        ))}
      </div>

      {/* ── Sinais operacionais ────────────────────────────────────────── */}
      {!loading && (
        <div className="grid gap-4 lg:grid-cols-2">

          {/* Fila de jobs */}
          <div className="rounded-xl border border-stone-200 bg-white dark:border-slate-border dark:bg-slate-card p-5">
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm font-semibold text-stone-900 dark:text-white">Fila de processamento</p>
              <button onClick={() => navigate('/jobs')} className="text-xs text-stone-400 dark:text-gray-500 hover:text-stone-600 dark:hover:text-white">
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
                    : 'border-stone-100 bg-stone-50 dark:border-slate-border dark:bg-ink-50'
                }`}>
                  <p className="text-xs text-stone-500 dark:text-gray-500">{label}</p>
                  <p className={`mt-1 text-xl font-bold ${warn ? 'text-yellow-600 dark:text-yellow-400' : 'text-stone-900 dark:text-white'}`}>{value}</p>
                </div>
              ))}
            </div>
            {jobs?.active_jobs?.length ? (
              <div className="space-y-2">
                {jobs.active_jobs.map(job => (
                  <div key={job.id} className="flex items-center justify-between rounded-lg border border-stone-100 dark:border-slate-border bg-stone-50 dark:bg-ink-50 px-3 py-2">
                    <div className="min-w-0">
                      <p className="truncate text-xs font-medium text-stone-800 dark:text-white">{job.label}</p>
                      <p className="text-[11px] text-stone-400 dark:text-gray-500">{job.status}</p>
                    </div>
                    <span className="ml-3 text-sm font-bold text-stone-600 dark:text-azure-glow flex-shrink-0">{job.progress_pct}%</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-stone-400 dark:text-gray-600">Nenhum processamento em andamento.</p>
            )}
          </div>

          {/* CRM */}
          <div className="rounded-xl border border-stone-200 bg-white dark:border-slate-border dark:bg-slate-card p-5">
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm font-semibold text-stone-900 dark:text-white">CRM comercial</p>
              <button onClick={() => navigate('/crm')} className="text-xs text-stone-400 dark:text-gray-500 hover:text-stone-600 dark:hover:text-white">
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
                    : 'border-stone-100 bg-stone-50 dark:border-slate-border dark:bg-ink-50'
                }`}>
                  <p className="text-xs text-stone-500 dark:text-gray-500">{label}</p>
                  <p className={`mt-1 text-xl font-bold ${warn ? 'text-red-600 dark:text-red-400' : 'text-stone-900 dark:text-white'}`}>{value}</p>
                </div>
              ))}
            </div>
            {crm?.upcoming_auctions?.length ? (
              <div className="space-y-2">
                {crm.upcoming_auctions.map(n => (
                  <div key={n.id} className="rounded-lg border border-stone-100 dark:border-slate-border bg-stone-50 dark:bg-ink-50 px-3 py-2">
                    <p className="text-xs font-medium text-stone-800 dark:text-white truncate">{n.number || n.title || 'Sem número'}</p>
                    <p className="text-[11px] text-stone-400 dark:text-gray-500 mt-0.5">{n.organ_name || '—'} · {n.auction_date ? new Date(n.auction_date).toLocaleDateString('pt-BR') : 'sem data'}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-stone-400 dark:text-gray-600">Nenhuma disputa nos próximos 7 dias.</p>
            )}
          </div>
        </div>
      )}

      {/* ── Editais ───────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-stone-200 bg-white dark:border-slate-border dark:bg-slate-card p-5">
        <div className="flex items-center justify-between mb-4">
          <p className="text-sm font-semibold text-stone-900 dark:text-white">Editais</p>
          {crmSync && (
            <p className="text-xs text-stone-400 dark:text-gray-600">
              CRM em {formatDate(crmSync.builtAt)}
            </p>
          )}
        </div>

        {loading ? (
          <div className="space-y-2">
            {[1,2,3].map(i => <div key={i} className="h-14 rounded-lg bg-stone-100 dark:bg-ink-50 animate-pulse" />)}
          </div>
        ) : editais.length === 0 ? (
          <div className="rounded-lg border border-dashed border-stone-200 dark:border-slate-border py-12 text-center">
            <p className="text-sm text-stone-400 dark:text-gray-500">Nenhum edital enviado ainda.</p>
            {isEditor && (
              <button onClick={() => navigate('/upload')} className="btn-primary mt-4">
                Enviar primeiro edital
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            {editais.map(edital => (
              <div
                key={edital.id}
                onClick={() => navigate(`/editais/${edital.id}`)}
                className="flex items-center gap-4 rounded-lg border border-stone-100 dark:border-slate-border bg-stone-50 dark:bg-ink-50 px-4 py-3 cursor-pointer hover:bg-stone-100 dark:hover:bg-slate-hover transition-colors"
              >
                <div className="flex-shrink-0 w-8 h-8 rounded-lg border border-stone-200 dark:border-slate-border bg-white dark:bg-ink-100 grid place-items-center">
                  <span className="text-[9px] font-bold text-stone-400 dark:text-gray-500">PDF</span>
                </div>

                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-stone-900 dark:text-white truncate">{edital.filename}</p>
                  <p className="text-xs text-stone-400 dark:text-gray-500 mt-0.5">
                    {edital.chunks || 0} chunks · {edital.requirements || 0} requisitos
                    {edital.parsed_at && ` · ${formatDate(edital.parsed_at)}`}
                  </p>
                </div>

                <div className="flex items-center gap-1.5 flex-shrink-0" onClick={e => e.stopPropagation()}>
                  <button onClick={() => navigate(`/editais/${edital.id}/chat`)}
                    className="px-2.5 py-1.5 rounded-lg border border-stone-200 dark:border-slate-border text-[11px] font-mono text-stone-500 dark:text-gray-400 hover:text-stone-800 dark:hover:text-white hover:bg-white dark:hover:bg-ink-100 transition-colors">
                    Chat
                  </button>
                  <button onClick={() => navigate(`/editais/${edital.id}/analise-llm`)}
                    className="px-2.5 py-1.5 rounded-lg border border-stone-200 dark:border-slate-border text-[11px] font-mono text-stone-500 dark:text-gray-400 hover:text-stone-800 dark:hover:text-white hover:bg-white dark:hover:bg-ink-100 transition-colors">
                    Análise
                  </button>
                  {['xlsx','csv'].map(tipo => (
                    <button key={tipo} onClick={e => handleExport(e, edital.id, tipo)}
                      disabled={Boolean(exporting)}
                      className="px-2.5 py-1.5 rounded-lg border border-stone-200 dark:border-slate-border text-[11px] font-mono text-stone-400 dark:text-gray-500 hover:text-stone-700 dark:hover:text-white hover:bg-white dark:hover:bg-ink-100 transition-colors disabled:opacity-40">
                      {exporting === `${edital.id}-${tipo}` ? '…' : tipo.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
