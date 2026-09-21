import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { jobsApi } from '../api/client'
import { useToast } from '../contexts/ToastContext'
import { formatBrasiliaDateTime } from '../utils/datetime'

const isCancelled = (job) =>
  job.status === 'failed' && (
    job.failure_code === 'cancelled' || String(job.error_message || '').toLowerCase().startsWith('cancelado pelo usu')
  )

const isDeadLetter = (job) =>
  job.status === 'failed' && !isCancelled(job) && Number(job.attempt_count || 0) >= Number(job.max_attempts || 3)

const STATUS_CFG = {
  pending: { label: 'Aguardando', cls: 'badge-pending', barCls: 'bg-gray-500' },
  running: { label: 'Processando', cls: 'badge-atende', barCls: 'bg-red-600' },
  done: { label: 'Concluido', cls: 'badge-atende', barCls: 'bg-green-match' },
  failed: { label: 'Falhou', cls: 'badge-falhou', barCls: 'bg-red-fail' },
  cancelled: { label: 'Cancelado', cls: 'badge-pending', barCls: 'bg-gray-500' },
}

const TYPE_LABELS = {
  upload_edital: 'Upload / OCR',
  run_matching: 'Matching',
  crm_notice_match: 'CRM Match',
}

const FAILURE_LABELS = {
  timeout: 'Tempo esgotado',
  dependency_unavailable: 'Dependencia indisponivel',
  execution_error: 'Erro de execucao',
  feature_disabled: 'Recurso desabilitado',
  worker_interrupted: 'Worker interrompido',
  cancelled: 'Cancelado',
  unknown: 'Falha nao classificada',
}

const FILTERS = [
  { key: 'all', label: 'Todos' },
  { key: 'running', label: 'Rodando' },
  { key: 'done', label: 'Concluidos' },
  { key: 'failed', label: 'Falhos' },
  { key: 'dead_letter', label: 'Esgotados' },
]

const jobLabel = (job) =>
  job?.payload?.filename || job?.result?.filename || `${job?.job_type || 'job'} ${job?.id?.slice(0, 8) || ''}`

export default function Jobs() {
  const [jobs, setJobs] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [cancelling, setCancelling] = useState(null)
  const [retrying, setRetrying] = useState(null)
  const navigate = useNavigate()
  const { toast, confirm } = useToast()

  const load = async () => {
    const params = filter === 'dead_letter'
      ? { status: 'failed', dead_letter: true, limit: 100 }
      : filter !== 'all' ? { status: filter } : {}
    const [jobsResult, summaryResult] = await Promise.allSettled([
      jobsApi.list(params),
      jobsApi.summary(),
    ])

    if (jobsResult.status === 'fulfilled') {
      setJobs(jobsResult.value.data || [])
    }
    if (summaryResult.status === 'fulfilled') {
      setSummary(summaryResult.value.data || null)
    }
    setLoading(false)
  }

  useEffect(() => {
    setLoading(true)
    load()
  }, [filter])

  useEffect(() => {
    const hasActive = jobs.some((job) => job.status === 'pending' || job.status === 'running')
    if (!hasActive) return
    const timer = setInterval(load, 3000)
    return () => clearInterval(timer)
  }, [jobs, filter])

  const filteredJobs = useMemo(() => {
    const term = search.trim().toLowerCase()
    if (!term) return jobs

    return jobs.filter((job) => {
      const haystack = [
        job.id,
        job.job_type,
        job.status,
        job.failure_code,
        job.correlation_id,
        job.payload?.filename,
        job.result?.filename,
        job.result?.edital_id,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return haystack.includes(term)
    })
  }, [jobs, search])

  const handleCancel = async (event, jobId) => {
    event.stopPropagation()
    const ok = await confirm('Cancelar este job? A operacao nao podera ser desfeita.', {
      title: 'Cancelar job',
    })
    if (!ok) return

    setCancelling(jobId)
    try {
      await jobsApi.cancel(jobId)
      toast({ type: 'success', message: 'Job cancelado com sucesso.' })
      load()
    } catch (error) {
      const message = error.response?.data?.detail || 'Nao foi possivel cancelar o job.'
      toast({ type: 'error', title: 'Erro ao cancelar', message })
    } finally {
      setCancelling(null)
    }
  }

  const handleRetry = async (event, jobId) => {
    event.stopPropagation()
    const ok = await confirm('Reprocessar este job? Uma nova tentativa sera registrada no mesmo historico.', {
      title: 'Reprocessar job',
    })
    if (!ok) return

    setRetrying(jobId)
    try {
      await jobsApi.retry(jobId)
      toast({ type: 'success', message: 'Job reenfileirado com sucesso.' })
      await load()
    } catch (error) {
      const message = error.response?.data?.detail || 'Nao foi possivel reprocessar o job.'
      toast({ type: 'error', title: 'Erro ao reprocessar', message })
    } finally {
      setRetrying(null)
    }
  }

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm text-gray-400 mb-1">Fila de processamento</p>
          <h1 className="text-2xl font-semibold text-white">Jobs</h1>
        </div>
        <button onClick={load} className="btn-ghost text-xs px-3 py-2">
          Atualizar
        </button>
      </div>

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex gap-2 flex-wrap">
          {FILTERS.map((item) => (
            <button
              key={item.key}
              onClick={() => setFilter(item.key)}
              className={`px-4 py-1.5 rounded-lg text-xs font-body font-semibold transition-all duration-150 ${
                filter === item.key
                  ? 'bg-red-600 text-white'
                  : 'text-gray-400 border border-slate-700 hover:text-white'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Buscar por arquivo, ID ou tipo..."
          className="input max-w-md text-sm py-2"
        />
      </div>

      {!loading && summary && (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <SummaryCard
            label="Ativos"
            value={summary.active_count || 0}
            sub={`${summary.status_counts?.running || 0} rodando e ${summary.status_counts?.pending || 0} aguardando`}
          />
          <SummaryCard
            label="Falhas 24h"
            value={summary.failed_last_24h || 0}
            sub="incidentes recentes na fila"
          />
          <SummaryCard
            label="Travados"
            value={summary.stale_count || 0}
            sub="jobs ha mais de 20 min em execucao"
          />
          <SummaryCard
            label="Duracao media"
            value={summary.avg_duration_seconds ? `${Math.round(summary.avg_duration_seconds)}s` : '-'}
            sub="media dos jobs concluidos"
          />
          <SummaryCard
            label="Esgotados"
            value={summary.dead_letter_count || 0}
            sub="exigem revisao ou reprocessamento"
          />
        </div>
      )}

      {!loading && summary?.alerts?.length > 0 && (
        <div className="space-y-2">
          {summary.alerts.map((alert) => (
            <div
              key={alert.code}
              className={`rounded-lg border px-4 py-3 text-sm ${
                alert.severity === 'critical'
                  ? 'border-red-fail/30 bg-red-fail/10 text-red-200'
                  : 'border-amber-400/30 bg-amber-400/10 text-amber-100'
              }`}
            >
              <span className="font-semibold">{alert.severity === 'critical' ? 'Incidente critico: ' : 'Atencao: '}</span>
              {alert.message}
            </div>
          ))}
        </div>
      )}

      {!loading && summary?.recent_failures?.length > 0 && (
        <div className="card">
          <div>
            <p className="text-xs font-body font-semibold tracking-wide text-gray-500">Falhas recentes</p>
            <p className="mt-1 text-sm text-gray-400">Ultimos erros detectados pela fila de processamento.</p>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {summary.recent_failures.map((item) => (
              <div key={item.id} className="rounded-lg border border-red-fail/20 bg-red-fail/5 px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-white">{item.label}</p>
                    <p className="mt-1 text-xs font-body font-semibold tracking-wide text-red-fail">
                      {TYPE_LABELS[item.job_type] || item.job_type}
                    </p>
                    <p className="mt-1 text-[11px] text-gray-500">
                      {FAILURE_LABELS[item.failure_code] || item.failure_code}
                      {item.dead_letter ? ' · tentativas esgotadas' : ''}
                    </p>
                  </div>
                  <span className="text-xs font-body text-gray-500">
                    {formatBrasiliaDateTime(item.finished_at, '-')}
                  </span>
                </div>
                <p className="mt-2 text-xs text-gray-300">{item.error_message || 'Erro nao informado.'}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((item) => (
            <div key={item} className="h-16 bg-slate-800 rounded-lg border border-slate-700 animate-pulse" />
          ))}
        </div>
      ) : filteredJobs.length === 0 ? (
        <div className="card text-center py-16 text-gray-500">
          <p className="font-body text-sm">Nenhum job encontrado para o filtro atual.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filteredJobs.map((job, index) => {
            const cancelled = isCancelled(job)
            const cfgKey = cancelled ? 'cancelled' : job.status
            const cfg = STATUS_CFG[cfgKey] || STATUS_CFG.pending
            const pct = Math.round((job.progress || 0) * 100)
            const canCancel = job.status === 'pending' || job.status === 'running'
            const canRetry = job.status === 'failed' && !cancelled && ['run_matching', 'crm_notice_match'].includes(job.job_type)
            const deadLetter = isDeadLetter(job)

            return (
              <div
                key={job.id}
                onClick={() => job.result?.edital_id && navigate(`/editais/${job.result.edital_id}`)}
                className={`card py-4 flex items-center gap-4 animate-fade-up transition-all duration-200 ${
                  job.result?.edital_id ? 'cursor-pointer hover:border-red-600/40 hover:bg-slate-hover' : ''
                } ${cancelled ? 'opacity-60' : ''}`}
                style={{ animationDelay: `${index * 40}ms` }}
              >
                <div className="w-44 flex-shrink-0">
                  <p className="text-xs font-body font-semibold text-gray-500">{TYPE_LABELS[job.job_type] || job.job_type}</p>
                  <p className="mt-1 truncate text-xs text-gray-600">{jobLabel(job)}</p>
                </div>

                <div className="w-36 flex-shrink-0">
                  <p className="text-xs text-gray-400">{job.id.slice(0, 8)}...</p>
                  <p className="text-xs text-gray-600">
                    {formatBrasiliaDateTime(job.created_at, '-')}
                  </p>
                </div>

                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1 gap-3">
                    <span className={cfg.cls}>{cfg.label}</span>
                    {job.status === 'running' && (
                      <span className="text-xs font-body font-semibold text-red-400">{pct}%</span>
                    )}
                    {job.duration_seconds && (
                      <span className="text-xs font-body text-gray-600">{job.duration_seconds}s</span>
                    )}
                  </div>
                  {(job.status === 'running' || job.status === 'done') && (
                    <div className="h-0.5 bg-slate-border rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${cfg.barCls}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  )}
                  {job.error_message && !cancelled && (
                    <p className="text-xs text-red-fail font-body mt-1 truncate">{job.error_message}</p>
                  )}
                  {job.failure_code && !cancelled && (
                    <p className="mt-1 text-[11px] text-gray-500">
                      {FAILURE_LABELS[job.failure_code] || job.failure_code}
                      {' · tentativa '}{job.attempt_count || 0}/{job.max_attempts || 3}
                      {deadLetter ? ' · esgotado' : ''}
                    </p>
                  )}
                  {job.result?.edital_id && (
                    <p className="text-xs text-gray-500 font-body mt-1">edital #{job.result.edital_id}</p>
                  )}
                </div>

                <div className="flex flex-shrink-0 items-center gap-2">
                  {canRetry && (
                    <button
                      onClick={(event) => handleRetry(event, job.id)}
                      disabled={retrying === job.id}
                      className="px-3 py-1 rounded-lg text-xs font-body font-semibold border border-amber-400/40 text-amber-300 hover:bg-amber-400/10 transition-all duration-150 disabled:opacity-40"
                    >
                      {retrying === job.id ? '...' : 'Reprocessar'}
                    </button>
                  )}
                  {canCancel && (
                    <button
                      onClick={(event) => handleCancel(event, job.id)}
                      disabled={cancelling === job.id}
                      className="px-3 py-1 rounded-lg text-xs font-body font-semibold border border-red-fail/40 text-red-fail hover:bg-red-fail/10 transition-all duration-150 disabled:opacity-40"
                    >
                      {cancelling === job.id ? '...' : 'Cancelar'}
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function SummaryCard({ label, value, sub }) {
  return (
    <div className="card">
      <p className="text-xs font-body font-semibold tracking-wide text-gray-500">{label}</p>
      <p className="mt-2 font-display text-3xl font-black text-white">{value}</p>
      <p className="mt-1 text-xs text-gray-500">{sub}</p>
    </div>
  )
}
