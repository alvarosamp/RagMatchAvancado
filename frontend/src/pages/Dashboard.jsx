import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, FileText, Search, Upload, AlertTriangle, Clock, TrendingUp, Zap } from 'lucide-react'
import { documentsApi, editaisApi, opsApi } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { useMarket } from '../contexts/MarketContext'
import { useToast } from '../contexts/ToastContext'
import EmptyState from '../components/ui/EmptyState'
import { formatBrasiliaDate, formatBrasiliaDateTime } from '../utils/datetime'

const CRM_ENTRYPOINT = '/crm/'

async function readCrmSync() {
  try {
    const r = await fetch(`/crm/tor-sync.json?ts=${Date.now()}`, { cache: 'no-store' })
    if (!r.ok) return null
    return await r.json()
  } catch { return null }
}

function BigStat({ value, label, sub, accent, loading }) {
  return (
    <div className="flex flex-col gap-1">
      <p className={`text-5xl font-bold tabular-nums leading-none tracking-tight ${accent || 'text-slate-950 dark:text-white'}`}>
        {loading ? <span className="inline-block h-10 w-16 animate-pulse rounded bg-slate-200 dark:bg-slate-700" /> : value}
      </p>
      <p className="text-sm font-medium text-slate-700 dark:text-slate-300">{label}</p>
      {sub && <p className="text-xs text-slate-500 dark:text-slate-400">{sub}</p>}
    </div>
  )
}

function AlertBanner({ count, label, onClick, tone = 'amber' }) {
  const colors = {
    amber: 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-200',
    red: 'border-red-300 bg-red-50 text-red-900 dark:border-red-700 dark:bg-red-950/30 dark:text-red-200',
  }
  return (
    <button
      type="button"
      onClick={onClick}
      className={`group flex w-full items-center justify-between rounded-xl border px-5 py-4 text-left transition-opacity hover:opacity-90 ${colors[tone]}`}
    >
      <div className="flex items-center gap-3">
        <AlertTriangle className="h-4 w-4 flex-shrink-0" />
        <p className="text-sm font-semibold">{count} {label}</p>
      </div>
      <ArrowRight className="h-4 w-4 opacity-60 transition-transform group-hover:translate-x-0.5" />
    </button>
  )
}

function ActionPill({ icon, label, description, onClick, primary }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`group flex items-start gap-4 rounded-xl border p-5 text-left transition-all hover:shadow-sm ${
        primary
          ? 'border-blue-200 bg-blue-50 hover:border-blue-300 dark:border-blue-800 dark:bg-blue-950/30 dark:hover:border-blue-700'
          : 'border-slate-200 bg-white hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-600'
      }`}
    >
      <div className={`mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg ${
        primary ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
      }`}>
        {icon}
      </div>
      <div className="min-w-0">
        <p className={`text-sm font-semibold ${primary ? 'text-blue-900 dark:text-blue-200' : 'text-slate-950 dark:text-white'}`}>{label}</p>
        <p className={`mt-0.5 text-xs leading-5 ${primary ? 'text-blue-700 dark:text-blue-300' : 'text-slate-500 dark:text-slate-400'}`}>{description}</p>
      </div>
      <ArrowRight className="ml-auto mt-1 h-4 w-4 flex-shrink-0 text-slate-400 opacity-0 transition-all group-hover:translate-x-0.5 group-hover:opacity-100" />
    </button>
  )
}

function EditalCard({ edital, onClick }) {
  const hasDescription = edital.object_description || edital.description || edital.objeto
  const description = hasDescription?.slice(0, 120)

  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex w-full items-start gap-4 rounded-xl border border-slate-200 bg-white px-5 py-4 text-left transition-all hover:border-slate-300 hover:shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-600"
    >
      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800">
        <FileText className="h-4 w-4 text-slate-500 dark:text-slate-400" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-slate-950 dark:text-white">{edital.filename || edital.numero_pregao || `Edital #${edital.id}`}</p>
        {description ? (
          <p className="mt-0.5 text-xs leading-5 text-slate-500 dark:text-slate-400 line-clamp-2">{description}</p>
        ) : (
          <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">{edital.requirements ? `${edital.requirements} pontos analisados` : 'Processando...'}</p>
        )}
      </div>
      <div className="ml-2 flex-shrink-0 text-right">
        {edital.requirements > 0 && (
          <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">{edital.requirements}</p>
        )}
        <p className="text-[11px] text-slate-400 dark:text-slate-500">{edital.created_at ? formatBrasiliaDate(edital.created_at) : ''}</p>
      </div>
    </button>
  )
}

export default function Dashboard() {
  const [editais, setEditais] = useState([])
  const [loading, setLoading] = useState(true)
  const [opsSummary, setOpsSummary] = useState(null)
  const [crmSync, setCrmSync] = useState(null)
  const [signatureAlert, setSignatureAlert] = useState(null)
  const { user, isEditor } = useAuth()
  const market = useMarket()
  const { toast } = useToast()
  const navigate = useNavigate()

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

  const jobs = opsSummary?.jobs
  const crm = opsSummary?.crm
  const nEditais = opsSummary?.editais?.total_editais ?? editais.length
  const totalRequirements = useMemo(
    () => opsSummary?.editais?.total_requirements ?? editais.reduce((s, e) => s + (e.requirements || 0), 0),
    [editais, opsSummary]
  )

  const totalAlerts = (jobs?.stale_count ?? 0) + (crm?.attention_required ?? 0) + (signatureAlert?.count ?? 0)
  const hasActivity = nEditais > 0 || totalRequirements > 0 || (crm?.active_pipeline ?? 0) > 0

  const weekday = new Date().toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' })

  return (
    <div className="mx-auto max-w-4xl space-y-8 p-5 lg:p-8">

      {/* ── Cabeçalho narrativo ─────────────────────────────────────────── */}
      <section>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">{weekday}</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 dark:text-white">
          {user?.tenant?.name ? `Olá, ${user.tenant.name.split(' ')[0]}` : 'Bom dia'}
        </h1>
        <p className="mt-2 text-base leading-7 text-slate-600 dark:text-slate-400">
          {hasActivity
            ? nEditais > 0
              ? `Você tem ${nEditais} ${nEditais > 1 ? 'editais' : 'edital'} acompanhado${nEditais > 1 ? 's' : ''} e ${(crm?.active_pipeline ?? 0)} no pipeline ativo.`
              : 'Tudo pronto. Busque oportunidades ou envie um edital para começar.'
            : 'Comece buscando oportunidades no radar ou enviando um edital para análise.'}
        </p>
      </section>

      {/* ── Alertas críticos ────────────────────────────────────────────── */}
      {!loading && totalAlerts > 0 && (
        <section className="space-y-2">
          {signatureAlert?.count > 0 && (
            <AlertBanner
              count={signatureAlert.count}
              label={`documento${signatureAlert.count > 1 ? 's' : ''} aguardando assinatura`}
              onClick={() => navigate(signatureAlert.request?.id ? `/assinatura?request=${signatureAlert.request.id}` : '/assinatura')}
              tone="amber"
            />
          )}
          {(crm?.attention_required ?? 0) > 0 && (
            <AlertBanner
              count={crm.attention_required}
              label={`disputa${crm.attention_required > 1 ? 's' : ''} pedindo atenção`}
              onClick={() => window.location.assign(CRM_ENTRYPOINT)}
              tone="red"
            />
          )}
          {(jobs?.stale_count ?? 0) > 0 && (
            <AlertBanner
              count={jobs.stale_count}
              label={`processamento${jobs.stale_count > 1 ? 's' : ''} travado${jobs.stale_count > 1 ? 's' : ''}`}
              onClick={() => navigate('/jobs')}
              tone="amber"
            />
          )}
        </section>
      )}

      {/* ── Números de contexto ─────────────────────────────────────────── */}
      {!loading && hasActivity && (
        <section className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900">
          <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
            <BigStat value={nEditais} label="Editais" sub="acompanhados" />
            <BigStat value={totalRequirements.toLocaleString('pt-BR')} label="Pontos" sub="analisados" />
            <BigStat value={crm?.active_pipeline ?? 0} label="No pipeline" sub="em andamento" accent={(crm?.active_pipeline ?? 0) > 0 ? 'text-blue-600 dark:text-blue-400' : undefined} />
            <BigStat value={crm?.upcoming_auctions_count ?? 0} label="Disputas" sub="nos próximos 7 dias" accent={(crm?.upcoming_auctions_count ?? 0) > 0 ? 'text-amber-600 dark:text-amber-400' : undefined} />
          </div>
          {crmSync && (
            <p className="mt-4 border-t border-slate-100 pt-3 text-xs text-slate-400 dark:border-slate-700 dark:text-slate-500">
              CRM atualizado em {formatBrasiliaDateTime(crmSync.builtAt)}
            </p>
          )}
        </section>
      )}

      {/* ── Próximas disputas ───────────────────────────────────────────── */}
      {!loading && (crm?.upcoming_auctions?.length ?? 0) > 0 && (
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-950 dark:text-white">Próximas disputas</h2>
            <button onClick={() => window.location.assign(CRM_ENTRYPOINT)} className="text-xs font-semibold text-blue-600 hover:underline dark:text-blue-400">
              Ver todas →
            </button>
          </div>
          <div className="space-y-2">
            {crm.upcoming_auctions.slice(0, 3).map(n => (
              <button
                key={n.id}
                onClick={() => window.location.assign(CRM_ENTRYPOINT)}
                className="group flex w-full items-center gap-4 rounded-xl border border-slate-200 bg-white px-5 py-3 text-left transition-all hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-600"
              >
                <Clock className="h-4 w-4 flex-shrink-0 text-amber-500" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-950 dark:text-white">{n.number || n.title || 'Sem número'}</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">{n.organ_name || '—'}</p>
                </div>
                <p className="flex-shrink-0 text-xs font-semibold text-amber-600 dark:text-amber-400">
                  {n.auction_date ? formatBrasiliaDate(n.auction_date) : 'sem data'}
                </p>
              </button>
            ))}
          </div>
        </section>
      )}

      {/* ── Ações principais ────────────────────────────────────────────── */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-950 dark:text-white">O que fazer agora</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {isEditor && (
            <ActionPill
              icon={<Upload className="h-4 w-4" />}
              label="Analisar edital"
              description="Envie PDF e transforme em requisitos, riscos e ações."
              onClick={() => navigate('/upload')}
              primary
            />
          )}
          <ActionPill
            icon={<Search className="h-4 w-4" />}
            label="Buscar oportunidades"
            description="Encontre editais aderentes antes de gastar tempo."
            onClick={() => navigate('/radar')}
          />
          <ActionPill
            icon={<TrendingUp className="h-4 w-4" />}
            label="Ver pipeline"
            description="Organize funil, responsáveis e próximas sessões."
            onClick={() => window.location.assign(CRM_ENTRYPOINT)}
          />
        </div>
      </section>

      {/* ── Editais recentes ────────────────────────────────────────────── */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-950 dark:text-white">
            {market.labels.source_document_plural_title || 'Editais'}
          </h2>
          {editais.length > 5 && (
            <button onClick={() => navigate('/analise/dashboard')} className="text-xs font-semibold text-blue-600 hover:underline dark:text-blue-400">
              Ver todos →
            </button>
          )}
        </div>

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-16 animate-pulse rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900" />
            ))}
          </div>
        ) : editais.length === 0 ? (
          <EmptyState
            title="Nenhum edital enviado ainda"
            description="Envie o primeiro edital para liberar análise, requisitos, matching e acompanhamento."
            action={isEditor ? { label: market.labels.send_first_source_document || 'Enviar edital', onClick: () => navigate('/upload') } : null}
            icon={<FileText className="h-5 w-5" />}
          />
        ) : (
          <div className="space-y-2">
            {editais.slice(0, 6).map(edital => (
              <EditalCard
                key={edital.id}
                edital={edital}
                onClick={() => navigate(`/editais/${edital.id}`)}
              />
            ))}
          </div>
        )}
      </section>

    </div>
  )
}
