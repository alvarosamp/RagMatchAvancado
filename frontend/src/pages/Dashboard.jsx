import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { downloadBlob, editaisApi, exportApi, opsApi } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'

function formatSyncDate(value) {
  if (!value) return 'aguardando primeira sincronizacao'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'aguardando primeira sincronizacao'
  return date.toLocaleString('pt-BR')
}

function StatusChip({ label, tone = 'neutral' }) {
  const tones = {
    success: 'border-green-match/30 bg-green-match/10 text-green-match',
    warning: 'border-yellow-warn/30 bg-yellow-warn/10 text-yellow-warn',
    neutral: 'border-slate-border bg-ink-50 text-gray-400',
  }

  return (
    <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-mono uppercase tracking-[0.2em] ${tones[tone]}`}>
      <span className={`h-2 w-2 rounded-full ${tone === 'success' ? 'bg-green-match' : tone === 'warning' ? 'bg-yellow-warn' : 'bg-gray-500'}`} />
      {label}
    </span>
  )
}

function renderModuleIcon(badge) {
  const props = { className: "h-5 w-5 stroke-current", fill: "none", stroke: "currentColor", strokeWidth: "2" };
  switch (badge) {
    case 'RAG':
      return (
        <svg {...props} viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
          <line x1="10" y1="9" x2="8" y2="9" />
        </svg>
      );
    case 'PN':
      return (
        <svg {...props} viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      );
    case 'CRM':
      return (
        <svg {...props} viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
          <path d="M12 11v6" />
          <path d="M9 14h6" />
        </svg>
      );
    case 'OPS':
      return (
        <svg {...props} viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
      );
    default:
      return badge;
  }
}

function StatCard({ label, value, sub, tone = 'azure' }) {
  const tones = {
    azure: 'from-azure/14 to-azure/5 border-azure/20',
    green: 'from-green-match/14 to-green-match/5 border-green-match/20',
    yellow: 'from-yellow-warn/14 to-yellow-warn/5 border-yellow-warn/20',
    slate: 'from-white/8 to-white/[0.02] border-slate-border',
  }

  return (
    <div className={`rounded-[24px] border bg-gradient-to-br p-5 ${tones[tone]}`}>
      <p className="text-xs font-semibold tracking-wide text-gray-400">{label}</p>
      <p className="mt-3 font-display text-3xl font-black text-white">{value}</p>
      <p className="mt-2 text-sm text-gray-400">{sub}</p>
    </div>
  )
}

function SignalCard({ label, value, sub, tone = 'neutral' }) {
  const tones = {
    success: 'border-green-match/20 bg-green-match/10 text-green-match',
    warning: 'border-yellow-warn/20 bg-yellow-warn/10 text-yellow-warn',
    danger: 'border-red-fail/20 bg-red-fail/10 text-red-fail',
    neutral: 'border-slate-border bg-ink-50 text-gray-300',
  }

  return (
    <div className={`rounded-[22px] border p-4 ${tones[tone]}`}>
      <p className="text-xs font-semibold tracking-wide text-gray-400">{label}</p>
      <p className="mt-3 font-display text-3xl font-black text-white">{value}</p>
      <p className="mt-2 text-sm text-gray-400">{sub}</p>
    </div>
  )
}

function ModuleCard({ badge, title, description, meta, onClick, actionLabel }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group rounded-[24px] border border-slate-border bg-slate-card/95 p-5 text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-azure/30 hover:bg-slate-hover"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="grid h-12 w-12 place-items-center rounded-2xl border border-azure/20 bg-azure/10 text-azure-glow">
          {renderModuleIcon(badge)}
        </div>
        <span className="text-xs font-semibold tracking-wide text-gray-500 group-hover:text-azure-glow">
          {actionLabel}
        </span>
      </div>
      <h3 className="mt-4 font-display text-xl font-bold text-white">{title}</h3>
      <p className="mt-2 text-sm leading-7 text-gray-400">{description}</p>
      <p className="mt-4 text-xs font-semibold tracking-wide text-gray-500">{meta}</p>
    </button>
  )
}

async function readCrmSync() {
  try {
    const response = await fetch(`/crm/tor-sync.json?ts=${Date.now()}`, { cache: 'no-store' })
    if (!response.ok) return null
    return await response.json()
  } catch {
    return null
  }
}

export default function Dashboard() {
  const [editais, setEditais] = useState([])
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(null)
  const [apiOnline, setApiOnline] = useState(null)
  const [opsSummary, setOpsSummary] = useState(null)
  const [crmSync, setCrmSync] = useState(null)
  const { user, isEditor } = useAuth()
  const { toast } = useToast()
  const navigate = useNavigate()

  useEffect(() => {
    let active = true

    async function loadDashboard() {
      setLoading(true)
      const [editaisResult, opsResult, crmResult] = await Promise.allSettled([
        editaisApi.list(),
        opsApi.summary(),
        readCrmSync(),
      ])

      if (!active) return

      if (editaisResult.status === 'fulfilled') {
        setEditais(editaisResult.value.data || [])
      } else {
        setEditais([])
      }

      if (opsResult.status === 'fulfilled') {
        setOpsSummary(opsResult.value.data || null)
        setApiOnline(true)
      } else {
        setOpsSummary(null)
        setApiOnline(false)
      }
      setCrmSync(crmResult.status === 'fulfilled' ? crmResult.value : null)
      setLoading(false)
    }

    loadDashboard()
    return () => {
      active = false
    }
  }, [])

  const handleExport = async (event, id, tipo) => {
    event.stopPropagation()
    setExporting(`${id}-${tipo}`)

    try {
      const exporter = { xlsx: exportApi.xlsx, csv: exportApi.csv }[tipo]
      const response = await exporter(id)
      downloadBlob(response.data, `edital_${id}_resultado.${tipo}`)
      toast({ type: 'success', message: `${tipo.toUpperCase()} gerado com sucesso.` })
    } catch (error) {
      toast({
        type: 'error',
        title: 'Falha ao exportar',
        message: error.response?.data?.detail || `Nao foi possivel exportar o edital em ${tipo.toUpperCase()}.`,
      })
    } finally {
      setExporting(null)
    }
  }

  const totalChunks = useMemo(
    () => opsSummary?.editais?.total_chunks ?? editais.reduce((sum, edital) => sum + (edital.chunks || 0), 0),
    [editais, opsSummary]
  )
  const totalRequirements = useMemo(
    () => opsSummary?.editais?.total_requirements ?? editais.reduce((sum, edital) => sum + (edital.requirements || 0), 0),
    [editais, opsSummary]
  )
  const jobsSummary = opsSummary?.jobs
  const crmSummary = opsSummary?.crm

  return (
    <div className="p-6 lg:p-8 space-y-8">
      <section className="relative overflow-hidden rounded-[30px] border border-slate-border bg-gradient-to-br from-ink-100 via-[#150b0b] to-[#2a1010] p-6 lg:p-8">
        <div className="absolute inset-0 opacity-80" style={{ backgroundImage: 'radial-gradient(circle at top right, rgba(248,113,113,0.18), transparent 34%), radial-gradient(circle at bottom left, rgba(220,38,38,0.12), transparent 36%)' }} />
        <div className="relative flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-[11px] font-mono uppercase tracking-[0.34em] text-gray-500">
              {user?.tenant?.name || 'Tor Tecnologias'}
            </p>
            <h1 className="mt-3 font-display text-3xl font-black text-white lg:text-5xl">
              Operacao de licitacoes, analise inteligente e CRM comercial em um unico portal
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-gray-300 lg:text-base">
              O site principal agora pode centralizar upload, analise, importacao PNCP, fila de jobs e o CRM do Bid Buddy em uma rota integrada pronta para publicacao.
            </p>

            <div className="mt-6 flex flex-wrap gap-3">
              <StatusChip label={apiOnline ? 'api online' : 'api indisponivel'} tone={apiOnline ? 'success' : 'warning'} />
              <StatusChip label={crmSync ? 'crm sincronizado' : 'crm aguardando sync'} tone={crmSync ? 'success' : 'warning'} />
              <StatusChip label={`ultima sync ${formatSyncDate(crmSync?.builtAt)}`} />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:w-[340px]">
            {isEditor && (
              <button onClick={() => navigate('/upload')} className="btn-primary h-14">
                Novo edital
              </button>
            )}
            <button onClick={() => navigate('/crm')} className="btn-ghost h-14">
              Abrir CRM integrado
            </button>
            <div className="rounded-2xl border border-slate-border bg-black/20 px-4 py-4 sm:col-span-2">
              <p className="text-[11px] font-mono uppercase tracking-[0.28em] text-gray-500">Ambiente</p>
              <p className="mt-2 text-sm font-semibold text-white">Portal operacional da Tor</p>
              <p className="mt-1 text-xs leading-6 text-gray-500">
                Upload, fila, analise de editais e CRM comercial dentro da mesma experiencia.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <ModuleCard
          badge="RAG"
          title="Pipeline de editais"
          description="Upload, OCR, indexacao e matching dos documentos principais."
          meta="entrada operacional"
          actionLabel="abrir"
          onClick={() => navigate('/upload')}
        />
        <ModuleCard
          badge="PN"
          title="Busca no PNCP"
          description="Importe novas oportunidades sem sair do portal principal."
          meta="captacao publica"
          actionLabel="buscar"
          onClick={() => navigate('/pncp')}
        />
        <ModuleCard
          badge="CRM"
          title="Licita CRM"
          description="Painel comercial do Bid Buddy embarcado no site da Tor."
          meta={crmSync ? `sync ${formatSyncDate(crmSync.builtAt)}` : 'sync pendente'}
          actionLabel="integrado"
          onClick={() => navigate('/crm')}
        />
        <ModuleCard
          badge="OPS"
          title="Jobs e analise"
          description="Monitore filas, processamento e indicadores de performance."
          meta="camada de operacao"
          actionLabel="acompanhar"
          onClick={() => navigate('/jobs')}
        />
      </section>

      {!loading && (
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Editais" value={opsSummary?.editais?.total_editais ?? editais.length} sub="documentos registrados no ambiente" tone="azure" />
          <StatCard label="Chunks" value={totalChunks.toLocaleString('pt-BR')} sub="fragmentos indexados para busca" tone="yellow" />
          <StatCard label="Requisitos" value={totalRequirements.toLocaleString('pt-BR')} sub="criterios estruturados no sistema" tone="green" />
          <StatCard
            label="CRM"
            value={crmSummary ? `${crmSummary.active_pipeline || 0} ativos` : crmSync ? 'Pronto' : 'Pendente'}
            sub={crmSummary ? `${crmSummary.attention_required || 0} pontos de atencao no funil comercial` : crmSync ? `sincronizado em ${formatSyncDate(crmSync.builtAt)}` : 'aguardando a primeira publicacao em /crm/'}
            tone="slate"
          />
        </section>
      )}

      {!loading && (
        <section className="grid gap-4 xl:grid-cols-[1.08fr_0.92fr]">
          <div className="rounded-[28px] border border-slate-border bg-slate-card/95 p-6">
            <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
              <div>
                <p className="text-[11px] font-mono uppercase tracking-[0.28em] text-gray-500">Radar operacional</p>
                <h2 className="mt-2 font-display text-2xl font-bold text-white">Saude do fluxo em tempo real</h2>
                <p className="mt-2 text-sm text-gray-400">
                  Acompanhe gargalos de processamento e pontos de atencao no CRM sem sair do portal.
                </p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => navigate('/jobs')} className="btn-ghost">
                  Ver jobs
                </button>
                <button onClick={() => navigate('/crm')} className="btn-ghost">
                  Abrir CRM
                </button>
              </div>
            </div>

            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <SignalCard
                label="Jobs ativos"
                value={jobsSummary?.active_count ?? 0}
                sub={`${jobsSummary?.status_counts?.running ?? 0} rodando agora e ${jobsSummary?.status_counts?.pending ?? 0} aguardando fila`}
                tone={(jobsSummary?.active_count ?? 0) > 0 ? 'warning' : 'success'}
              />
              <SignalCard
                label="Fila travada"
                value={jobsSummary?.stale_count ?? 0}
                sub="jobs executando ha mais de 20 minutos"
                tone={(jobsSummary?.stale_count ?? 0) > 0 ? 'danger' : 'success'}
              />
              <SignalCard
                label="CRM em atencao"
                value={crmSummary?.attention_required ?? 0}
                sub="pregoes vencidos ou prazos de pos-disputa estourados"
                tone={(crmSummary?.attention_required ?? 0) > 0 ? 'danger' : 'success'}
              />
              <SignalCard
                label="Pregoes proximos"
                value={crmSummary?.upcoming_auctions_count ?? 0}
                sub="disputas previstas para os proximos 7 dias"
                tone={(crmSummary?.upcoming_auctions_count ?? 0) > 0 ? 'warning' : 'neutral'}
              />
            </div>
          </div>

          <div className="rounded-[28px] border border-slate-border bg-slate-card/95 p-6">
            <div>
              <p className="text-[11px] font-mono uppercase tracking-[0.28em] text-gray-500">Prioridades</p>
              <h2 className="mt-2 font-display text-2xl font-bold text-white">O que merece olhar agora</h2>
            </div>

            <div className="mt-6 space-y-6">
              <div>
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-white">Jobs em andamento</p>
                  <button onClick={() => navigate('/jobs')} className="text-xs font-mono uppercase tracking-[0.2em] text-azure-glow">
                    abrir fila
                  </button>
                </div>
                {jobsSummary?.active_jobs?.length ? (
                  <div className="mt-3 space-y-3">
                    {jobsSummary.active_jobs.map((job) => (
                      <div key={job.id} className="rounded-2xl border border-slate-border bg-ink-50 px-4 py-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-white">{job.label}</p>
                            <p className="mt-1 text-xs font-mono uppercase tracking-[0.18em] text-gray-500">
                              {job.job_type} | {job.status}
                            </p>
                          </div>
                          <span className="text-sm font-bold text-azure-glow">{job.progress_pct}%</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-gray-500">Nenhum job ativo no momento.</p>
                )}
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-white">Pregoes proximos</p>
                  <button onClick={() => navigate('/crm')} className="text-xs font-mono uppercase tracking-[0.2em] text-azure-glow">
                    abrir crm
                  </button>
                </div>
                {crmSummary?.upcoming_auctions?.length ? (
                  <div className="mt-3 space-y-3">
                    {crmSummary.upcoming_auctions.map((notice) => (
                      <div key={notice.id} className="rounded-2xl border border-slate-border bg-ink-50 px-4 py-3">
                        <p className="text-sm font-semibold text-white">{notice.number || notice.title || 'Licitacao sem numero'}</p>
                        <p className="mt-1 text-xs text-gray-400">{notice.organ_name || 'Orgao nao informado'}</p>
                        <p className="mt-2 text-xs font-mono uppercase tracking-[0.18em] text-yellow-warn">
                          {notice.auction_date ? new Date(notice.auction_date).toLocaleString('pt-BR') : 'sem data'}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-gray-500">Nenhum pregao previsto para os proximos dias.</p>
                )}
              </div>
            </div>
          </div>
        </section>
      )}

      <section className="rounded-[28px] border border-slate-border bg-slate-card/95 p-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-[11px] font-mono uppercase tracking-[0.28em] text-gray-500">Base ativa</p>
            <h2 className="mt-2 font-display text-2xl font-bold text-white">Editais processados</h2>
            <p className="mt-2 text-sm text-gray-400">
              Consulte os ultimos documentos, abra o chat RAG e exporte os resultados.
            </p>
          </div>
          {crmSync && (
            <div className="rounded-2xl border border-slate-border bg-ink-50 px-4 py-3 text-sm text-gray-300">
              CRM publicado a partir do commit <span className="font-mono text-white">{crmSync.sourceCommit?.slice(0, 7) || 'local'}</span>
            </div>
          )}
        </div>

        {loading ? (
          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {[1, 2, 3].map((item) => (
              <div key={item} className="h-56 animate-pulse rounded-[24px] border border-slate-border bg-ink-50" />
            ))}
          </div>
        ) : editais.length === 0 ? (
          <div className="mt-8 grid place-items-center rounded-[24px] border border-dashed border-slate-border bg-ink-50 px-6 py-16 text-center">
            <div>
              <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl border border-dashed border-slate-border text-sm font-mono text-gray-500">
                PDF
              </div>
              <p className="mt-5 font-display text-xl font-bold text-white">Nenhum edital enviado ainda</p>
              <p className="mt-2 text-sm text-gray-500">Envie um PDF para iniciar a indexacao e destravar o restante do fluxo.</p>
              {isEditor && (
                <button onClick={() => navigate('/upload')} className="btn-primary mt-6">
                  Enviar primeiro edital
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {editais.map((edital, index) => (
              <div
                key={edital.id}
                onClick={() => navigate(`/editais/${edital.id}`)}
                className="group flex cursor-pointer flex-col rounded-[24px] border border-slate-border bg-ink-50/70 p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-azure/30 hover:bg-slate-hover"
                style={{ animationDelay: `${index * 60}ms` }}
              >
                <div className="flex items-start gap-3">
                  <div className="grid h-12 w-12 flex-shrink-0 place-items-center rounded-2xl border border-azure/20 bg-azure/10 text-xs font-mono font-bold text-azure-glow">
                    PDF
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-white group-hover:text-azure-glow">{edital.filename}</p>
                    <p className="mt-1 text-xs font-mono text-gray-500">
                      {edital.parsed_at ? new Date(edital.parsed_at).toLocaleDateString('pt-BR') : 'sem data de processamento'}
                    </p>
                  </div>
                </div>

                <div className="mt-5 grid grid-cols-2 gap-3">
                  <div className="rounded-2xl border border-slate-border bg-black/20 p-3">
                    <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-gray-500">chunks</p>
                    <p className="mt-2 text-xl font-bold text-white">{edital.chunks || 0}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-border bg-black/20 p-3">
                    <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-gray-500">requisitos</p>
                    <p className="mt-2 text-xl font-bold text-white">{edital.requirements || 0}</p>
                  </div>
                </div>

                <div className="mt-5 flex flex-wrap gap-2 border-t border-slate-border pt-4" onClick={(event) => event.stopPropagation()}>
                  <button
                    onClick={() => navigate(`/editais/${edital.id}/chat`)}
                    className="rounded-xl border border-azure/30 px-3 py-2 text-xs font-mono uppercase tracking-[0.18em] text-azure-glow transition-colors hover:border-azure/60 hover:bg-azure/10"
                  >
                    Chat
                  </button>
                  <button
                    onClick={() => navigate(`/editais/${edital.id}/analise-llm`)}
                    className="rounded-xl border border-yellow-warn/30 px-3 py-2 text-xs font-mono uppercase tracking-[0.18em] text-yellow-warn transition-colors hover:border-yellow-warn/60 hover:bg-yellow-warn/10"
                  >
                    LLM
                  </button>
                  <div className="ml-auto flex gap-2">
                    {[
                      ['xlsx', 'XLS'],
                      ['csv', 'CSV'],
                    ].map(([tipo, label]) => (
                      <button
                        key={tipo}
                        onClick={(event) => handleExport(event, edital.id, tipo)}
                        disabled={Boolean(exporting)}
                        className="rounded-xl border border-slate-border px-3 py-2 text-xs font-mono uppercase tracking-[0.18em] text-gray-400 transition-colors hover:border-azure/30 hover:text-white disabled:opacity-40"
                      >
                        {exporting === `${edital.id}-${tipo}` ? '...' : label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
