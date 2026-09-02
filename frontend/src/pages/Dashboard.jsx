import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BriefcaseBusiness, FileText, Search, Upload } from 'lucide-react'
import { documentsApi, downloadBlob, editaisApi, exportApi, opsApi } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { useMarket } from '../contexts/MarketContext'
import { useToast } from '../contexts/ToastContext'
import ActionCard from '../components/ui/ActionCard'
import EmptyState from '../components/ui/EmptyState'
import PageHeader from '../components/ui/PageHeader'
import ProgressBar from '../components/ui/ProgressBar'
import SectionCard from '../components/ui/SectionCard'
import EditalRow from '../components/ui/EditalRow'
import { EditalSkeleton } from '../components/ui/Skeleton'

const AI_FEATURES_ENABLED = import.meta.env.VITE_AI_FEATURES_ENABLED === '1'
const CRM_ENTRYPOINT = '/crm/'

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
  const [deleting,    setDeleting]    = useState(null)
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
      if (oRes.status === 'fulfilled') setOpsSummary(oRes.value.data)
      else setOpsSummary(null)
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

  const totalRequirements = useMemo(() => opsSummary?.editais?.total_requirements ?? editais.reduce((s, e) => s + (e.requirements || 0), 0), [editais, opsSummary])
  const jobs   = opsSummary?.jobs
  const crm    = opsSummary?.crm
  const nEditais = opsSummary?.editais?.total_editais ?? editais.length

  const hasOperationalSignal = (
    (jobs?.active_count ?? 0) > 0 ||
    (jobs?.stale_count ?? 0) > 0 ||
    (crm?.attention_required ?? 0) > 0 ||
    (crm?.upcoming_auctions_count ?? 0) > 0 ||
    signatureAlert?.count > 0
  )
  const hasActivity = nEditais > 0 || totalRequirements > 0 || (crm?.active_pipeline ?? 0) > 0 || hasOperationalSignal

  const primaryActions = [
    { key: 'upload', title: 'Analisar edital', description: 'Envie PDF ou JSON e transforme o edital em requisitos, riscos e itens acionaveis.', path: '/upload', cta: 'Enviar edital', enabled: isEditor, badge: 'Principal', badgeTone: 'blue', tone: 'blue' },
    { key: 'radar', title: 'Encontrar oportunidades', description: 'Busque editais aderentes antes de gastar tempo importando documentos.', path: '/radar', cta: 'Abrir radar', enabled: true, badge: 'Captação', badgeTone: 'emerald', tone: 'slate' },
    { key: 'crm', title: 'Acompanhar disputa', description: 'Organize funil, responsaveis, decisoes e proximas sessoes em um só lugar.', path: CRM_ENTRYPOINT, external: true, cta: 'Abrir CRM', enabled: true, badge: 'Gestão', badgeTone: 'slate', tone: 'slate' },
  ]

  const journeySteps = [
    { label: 'Captar', active: true },
    { label: 'Analisar', active: nEditais > 0 },
    { label: 'Disputar', active: (crm?.active_pipeline ?? 0) > 0 },
    { label: 'Acompanhar', active: hasOperationalSignal },
  ]

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-5 lg:p-8">

      <PageHeader
        eyebrow={new Date().toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' })}
        title={user?.tenant?.name || 'Portal'}
        description={nEditais > 0
          ? 'Continue de onde parou: acompanhe editais, oportunidades e proximas acoes comerciais sem precisar entrar em cada modulo.'
          : 'Comece pela acao que mais combina com o momento: enviar um edital para analise ou buscar oportunidades no radar.'}
        primaryAction={isEditor ? { label: 'Enviar edital', onClick: () => navigate('/upload') } : null}
        secondaryAction={{ label: 'Buscar oportunidades', onClick: () => navigate('/radar') }}
      >
        <div className="grid gap-3 md:grid-cols-4">
          {journeySteps.map((step, index) => (
            <div
              key={step.label}
              className={`rounded-lg border px-4 py-3 ${
                step.active
                  ? 'border-blue-200 bg-blue-50 text-blue-950 dark:border-blue-800 dark:bg-blue-950/30 dark:text-blue-100'
                  : 'border-slate-200 bg-slate-50 text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400'
              }`}
            >
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-current/60">Etapa {index + 1}</p>
              <p className="mt-1 text-sm font-semibold">{step.label}</p>
            </div>
          ))}
        </div>

        {hasActivity && (
          <div className="mt-6 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { label: 'Editais acompanhados', value: nEditais },
              { label: 'Pontos analisados', value: totalRequirements.toLocaleString('pt-BR') },
              { label: 'No pipeline', value: crm?.active_pipeline ?? 0 },
              { label: 'Pendencias', value: (jobs?.stale_count ?? 0) + (crm?.attention_required ?? 0) + (signatureAlert?.count ?? 0) },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-lg border border-slate-100 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-900">
                <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
                <p className="mt-1 text-xl font-bold text-slate-950 dark:text-white">{loading ? '—' : value}</p>
              </div>
            ))}
          </div>
        )}
      </PageHeader>

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
          <span className="text-sm font-semibold text-amber-900 dark:text-amber-200">Abrir assinatura</span>
          </div>
        </button>
      )}

      <div className="grid gap-3 lg:grid-cols-3">
        {primaryActions.filter((action) => action.enabled).map((action, index) => (
          <ActionCard
            key={action.key}
            onClick={() => action.external ? window.location.assign(action.path) : navigate(action.path)}
            title={action.title}
            description={action.description}
            cta={action.cta}
            badge={action.badge}
            badgeTone={action.badgeTone}
            tone={index === 0 ? action.tone : 'slate'}
            icon={
              action.key === 'upload' ? (
                <Upload className="h-5 w-5" />
              ) : action.key === 'radar' ? (
                <Search className="h-5 w-5" />
              ) : (
                <BriefcaseBusiness className="h-5 w-5" />
              )
            }
          />
        ))}
      </div>

      {/* ── Sinais operacionais ────────────────────────────────────────── */}
      {!loading && hasOperationalSignal && (
        <div className="grid gap-4 lg:grid-cols-2">

          {/* Fila de jobs */}
          <SectionCard
            title="Processamento"
            description="Apenas o que precisa de acompanhamento operacional."
            action={{ label: 'Ver tudo →', onClick: () => navigate('/jobs') }}
          >
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
                    <div className="ml-3 flex w-24 flex-shrink-0 items-center gap-2">
                      <ProgressBar value={job.progress_pct} className="flex-1" />
                      <span className="text-sm font-bold tabular-nums text-slate-600 dark:text-red-400">{job.progress_pct}%</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 dark:text-slate-500">Nenhum processamento em andamento.</p>
            )}
          </SectionCard>

          {/* CRM */}
          <SectionCard
            title="Disputas e CRM"
            description="Prazos, decisões e oportunidades pedindo atenção."
            action={{ label: 'Abrir →', onClick: () => window.location.assign(CRM_ENTRYPOINT) }}
          >
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
          </SectionCard>
        </div>
      )}

      {!loading && !hasOperationalSignal && (
        <SectionCard>
          <p className="text-sm font-semibold text-slate-950 dark:text-white">Sem pendencias por enquanto</p>
          <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">
            Quando houver processamento, assinatura, disputa proxima ou item do CRM pedindo atencao, tudo aparece aqui.
          </p>
        </SectionCard>
      )}

      {/* ── Editais ───────────────────────────────────────────────────── */}
      <SectionCard
        title={market.labels.source_document_plural_title}
        description={crmSync ? `CRM atualizado em ${formatDate(crmSync.builtAt)}` : 'Documentos enviados para análise e acompanhamento.'}
      >
        {loading ? (
          <div className="space-y-2">
            {[1,2,3].map(i => <EditalSkeleton key={i} />)}
          </div>
        ) : editais.length === 0 ? (
          <EmptyState
            title="Nenhum edital enviado ainda"
            description="Envie o primeiro edital para liberar analise, requisitos, matching, relatorios e acompanhamento da disputa."
            action={isEditor ? { label: market.labels.send_first_source_document, onClick: () => navigate('/upload') } : null}
            icon={<FileText className="h-5 w-5" />}
          />
        ) : (
          <div className="space-y-2">
            {editais.map(edital => (
              <EditalRow
                key={edital.id}
                onClick={() => navigate(`/editais/${edital.id}`)}
                edital={edital}
                onChat={() => navigate(`/editais/${edital.id}/chat`)}
                onAnalysis={() => navigate(`/editais/${edital.id}/analise-llm`)}
                onExportXlsx={(event) => handleExport(event, edital.id, 'xlsx')}
                onExportCsv={(event) => handleExport(event, edital.id, 'csv')}
                onDelete={(event) => handleDelete(event, edital)}
                exporting={exporting}
                deleting={deleting}
                aiEnabled={AI_FEATURES_ENABLED}
                isEditor={isEditor}
              />
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  )
}
