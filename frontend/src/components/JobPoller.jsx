/**
 * components/JobPoller.jsx
 * ─────────────────────────
 * Componente que faz polling automático de um job até ele terminar.
 * Usado após upload e após disparar matching.
 */

import { useEffect, useState, useRef } from 'react'
import { jobsApi } from '../api/client'

export default function JobPoller({ jobId, onDone, onFailed }) {
  const [job,     setJob]     = useState(null)
  const intervalRef           = useRef(null)

  useEffect(() => {
    if (!jobId) return

    const poll = async () => {
      try {
        const res = await jobsApi.get(jobId)
        setJob(res.data)

        if (res.data.status === 'done') {
          clearInterval(intervalRef.current)
          onDone?.(res.data)
        } else if (res.data.status === 'failed') {
          clearInterval(intervalRef.current)
          onFailed?.(res.data)
        }
      } catch (e) {
        clearInterval(intervalRef.current)
      }
    }

    poll() // imediato
    intervalRef.current = setInterval(poll, 2500)
    return () => clearInterval(intervalRef.current)
  }, [jobId])

  if (!job) return null

  const pct = Math.round((job.progress || 0) * 100)

  const labels = {
    pending: { text: 'Na fila…',        color: 'text-gray-400' },
    running: { text: 'Processando…',    color: 'text-azure-glow' },
    done:    { text: 'Concluído',       color: 'text-green-match' },
    failed:  { text: 'Falhou',          color: 'text-red-fail' },
  }
  const lbl = labels[job.status] || labels.pending

  return (
    <div className="card mt-4 animate-fade-up">
      <div className="flex items-center justify-between mb-3">
        <span className={`text-sm font-mono font-medium ${lbl.color}`}>
          {job.status === 'running' && (
            <span className="inline-flex gap-1 mr-2">
              {[0,1,2].map(i => (
                <span key={i} className="w-1.5 h-1.5 rounded-full bg-azure-glow animate-pulse-dot"
                      style={{ animationDelay: `${i * 0.2}s` }} />
              ))}
            </span>
          )}
          {lbl.text}
        </span>
        <span className="text-xs font-mono text-gray-500">{pct}%</span>
      </div>

      {/* Barra de progresso */}
      <div className="h-1 bg-slate-border rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            job.status === 'failed' ? 'bg-red-fail' :
            job.status === 'done'   ? 'bg-green-match' : 'bg-azure'
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {job.status === 'failed' && job.error_message && (
        <p className="mt-3 text-xs text-red-fail font-mono bg-red-dim/20 rounded-lg px-3 py-2">
          {job.error_message}
        </p>
      )}

      {job.status === 'done' && job.duration_seconds && (
        <p className="mt-2 text-xs text-gray-500 font-mono">
          concluído em {job.duration_seconds}s
        </p>
      )}
    </div>
  )
}
