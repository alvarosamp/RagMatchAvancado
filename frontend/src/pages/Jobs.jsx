/**
 * pages/Jobs.jsx
 * ───────────────
 * Lista todos os jobs do tenant com status em tempo real.
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { jobsApi } from '../api/client'

const STATUS_CFG = {
  pending: { label: '⏳ Aguardando', cls: 'badge-pending', barCls: 'bg-gray-500' },
  running: { label: '🔄 Processando', cls: 'badge-atende',  barCls: 'bg-azure'    },
  done:    { label: '✅ Concluído',   cls: 'badge-atende',  barCls: 'bg-green-match' },
  failed:  { label: '❌ Falhou',      cls: 'badge-falhou',  barCls: 'bg-red-fail'  },
}

const TYPE_LABELS = {
  upload_edital: 'Upload / OCR',
  run_matching:  'Matching',
}

export default function Jobs() {
  const [jobs,    setJobs]    = useState([])
  const [loading, setLoading] = useState(true)
  const [filter,  setFilter]  = useState('all')
  const navigate              = useNavigate()

  const load = () => {
    const params = filter !== 'all' ? { status: filter } : {}
    jobsApi.list(params)
      .then(r => setJobs(r.data))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    setLoading(true); load()
  }, [filter])

  // Polling: atualiza automaticamente se há jobs em execução
  useEffect(() => {
    const hasActive = jobs.some(j => j.status === 'pending' || j.status === 'running')
    if (!hasActive) return
    const t = setInterval(load, 3000)
    return () => clearInterval(t)
  }, [jobs, filter])

  const filters = [
    { key: 'all',     label: 'Todos' },
    { key: 'running', label: 'Rodando' },
    { key: 'done',    label: 'Concluídos' },
    { key: 'failed',  label: 'Falhos' },
  ]

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <p className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-1">Orquestrador</p>
          <h1 className="font-display font-bold text-3xl text-white">Jobs</h1>
        </div>
        <button onClick={load} className="btn-ghost text-xs px-3 py-2">↻ Atualizar</button>
      </div>

      {/* Filtros */}
      <div className="flex gap-2 mb-6">
        {filters.map(f => (
          <button key={f.key} onClick={() => setFilter(f.key)}
            className={`px-4 py-1.5 rounded-lg text-xs font-mono transition-all duration-150
              ${filter === f.key ? 'bg-azure text-white' : 'text-gray-400 border border-slate-border hover:text-white'}`}>
            {f.label}
          </button>
        ))}
      </div>

      {/* Lista */}
      {loading ? (
        <div className="space-y-3">
          {[1,2,3].map(i => <div key={i} className="h-16 bg-slate-card rounded-xl border border-slate-border animate-pulse" />)}
        </div>
      ) : jobs.length === 0 ? (
        <div className="card text-center py-16 text-gray-500">
          <p className="font-mono text-sm">Nenhum job encontrado.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {jobs.map((job, i) => {
            const cfg = STATUS_CFG[job.status] || STATUS_CFG.pending
            const pct = Math.round((job.progress || 0) * 100)
            return (
              <div
                key={job.id}
                onClick={() => job.result?.edital_id && navigate(`/editais/${job.result.edital_id}`)}
                className={`card py-4 flex items-center gap-4 animate-fade-up transition-all duration-200
                  ${job.result?.edital_id ? 'cursor-pointer hover:border-azure/40 hover:bg-slate-hover' : ''}`}
                style={{ animationDelay: `${i * 40}ms` }}
              >
                {/* Tipo */}
                <div className="w-28 flex-shrink-0">
                  <p className="text-xs font-mono text-gray-500">{TYPE_LABELS[job.job_type] || job.job_type}</p>
                </div>

                {/* ID + data */}
                <div className="w-36 flex-shrink-0">
                  <p className="font-mono text-xs text-gray-400">{job.id.slice(0, 8)}…</p>
                  <p className="font-mono text-xs text-gray-600">
                    {job.created_at ? new Date(job.created_at).toLocaleString('pt-BR') : '—'}
                  </p>
                </div>

                {/* Barra de progresso */}
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className={cfg.cls}>{cfg.label}</span>
                    {job.status === 'running' && (
                      <span className="text-xs font-mono text-azure-glow">{pct}%</span>
                    )}
                    {job.duration_seconds && (
                      <span className="text-xs font-mono text-gray-600">{job.duration_seconds}s</span>
                    )}
                  </div>
                  {(job.status === 'running' || job.status === 'done') && (
                    <div className="h-0.5 bg-slate-border rounded-full overflow-hidden">
                      <div className={`h-full rounded-full transition-all duration-500 ${cfg.barCls}`}
                           style={{ width: `${pct}%` }} />
                    </div>
                  )}
                  {job.error_message && (
                    <p className="text-xs text-red-fail font-mono mt-1 truncate">{job.error_message}</p>
                  )}
                  {job.result?.edital_id && (
                    <p className="text-xs text-gray-500 font-mono mt-1">→ edital #{job.result.edital_id}</p>
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
