/**
 * pages/Controle.jsx
 * ───────────────────
 * Painel de controle de editais para o time.
 * Mostra todos os documentos com status, progresso, timestamps e duração.
 * Permite importar planilha CSV/Excel com lista de documentos para acompanhar.
 */

import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { editaisApi, jobsApi } from '../api/client'

const AI_FEATURES_ENABLED = import.meta.env.VITE_AI_FEATURES_ENABLED === '1'

// ── Utilitários ──────────────────────────────────────────────────────────────

const STATUS_CFG = {
  done:    { label: 'Concluído',   color: 'text-emerald-700 dark:text-emerald-300', bg: 'bg-emerald-50 border-emerald-200 dark:bg-emerald-950/40 dark:border-emerald-800' },
  running: { label: 'Processando', color: 'text-blue-700 dark:text-blue-300',       bg: 'bg-blue-50 border-blue-200 dark:bg-blue-950/30 dark:border-blue-800'           },
  pending: { label: 'Aguardando',  color: 'text-amber-700 dark:text-amber-300',     bg: 'bg-amber-50 border-amber-200 dark:bg-amber-950/40 dark:border-amber-800'       },
  failed:  { label: 'Erro',        color: 'text-red-700 dark:text-red-300',         bg: 'bg-red-50 border-red-200 dark:bg-red-950/40 dark:border-red-800'               },
  unknown: { label: 'Sem info',    color: 'text-slate-600 dark:text-slate-400',     bg: 'bg-slate-100 border-slate-200 dark:bg-slate-800 dark:border-slate-700'         },
}

function StatusBadge({ status }) {
  const cfg = STATUS_CFG[status] || STATUS_CFG.unknown
  return (
    <span className={`inline-flex items-center rounded-md border px-2.5 py-1 text-xs font-semibold ${cfg.bg} ${cfg.color}`}>
      {cfg.label}
    </span>
  )
}

function ProgressBar({ progress, status }) {
  const pct = status === 'done' ? 100 : (progress || 0)
  const bar = status === 'done'
    ? 'bg-emerald-500'
    : status === 'failed'
      ? 'bg-red-500'
      : 'bg-blue-500'
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
        <div
          className={`h-full rounded-full transition-all duration-500 ${bar} ${status === 'running' ? 'animate-pulse' : ''}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-8 text-right text-[10px] font-mono text-slate-500 dark:text-slate-400">{pct}%</span>
    </div>
  )
}

function EditalMobileCard({ row, navigate }) {
  return (
    <article
      className="cursor-pointer rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition-colors hover:border-blue-200 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-blue-800"
      onClick={() => navigate(`/editais/${row.id}`)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900 dark:text-white">{row.filename}</p>
          <p className="mt-1 font-mono text-xs text-slate-500 dark:text-slate-400">#{row.id} · {row.chunks} chunks · {row.requirements} req.</p>
        </div>
        <StatusBadge status={row.status} />
      </div>
      <div className="mt-4">
        <ProgressBar progress={row.progress} status={row.status} />
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-xs">
        <div>
          <dt className="text-slate-400 dark:text-slate-500">Upload</dt>
          <dd className="mt-1 font-mono text-slate-600 dark:text-slate-300">{fmt(row.parse_date)}</dd>
        </div>
        <div>
          <dt className="text-slate-400 dark:text-slate-500">Duração</dt>
          <dd className="mt-1 font-mono text-slate-600 dark:text-slate-300">{fmtDur(row.job?.duration_seconds)}</dd>
        </div>
        <div>
          <dt className="text-slate-400 dark:text-slate-500">Início</dt>
          <dd className="mt-1 font-mono text-slate-600 dark:text-slate-300">{fmt(row.job?.started_at)}</dd>
        </div>
        <div>
          <dt className="text-slate-400 dark:text-slate-500">Fim</dt>
          <dd className="mt-1 font-mono text-slate-600 dark:text-slate-300">{fmt(row.job?.finished_at)}</dd>
        </div>
      </dl>
      <div className="mt-4 flex gap-2 border-t border-slate-100 pt-3 dark:border-slate-700" onClick={(event) => event.stopPropagation()}>
        <button onClick={() => navigate(`/editais/${row.id}`)} className="rounded px-2 py-1 text-xs font-medium text-brand hover:bg-blue-50 dark:text-brand-light dark:hover:bg-blue-950/30">Ver edital</button>
        {AI_FEATURES_ENABLED && <button onClick={() => navigate(`/editais/${row.id}/chat`)} className="rounded px-2 py-1 text-xs font-medium text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700">Chat</button>}
      </div>
    </article>
  )
}


function fmt(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

function fmtDur(secs) {
  if (secs == null) return '—'
  if (secs < 60)   return `${secs}s`
  if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`
  return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`
}

// ── Import CSV ───────────────────────────────────────────────────────────────

function ImportPanel({ onClose }) {
  const [rows,    setRows]    = useState([])
  const [headers, setHeaders] = useState([])
  const [error,   setError]   = useState(null)
  const fileRef = useRef(null)

  const parseFile = (file) => {
    if (!file) return
    setError(null)
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const text = e.target.result
        const lines = text.split('\n').map(l => l.trim()).filter(Boolean)
        if (lines.length < 2) { setError('Arquivo vazio ou sem dados.'); return }

        const hdrs = lines[0].split(/[,;]/).map(h => h.replace(/^"|"$/g, '').trim())
        const parsed = lines.slice(1).map(line => {
          const cols = line.split(/[,;]/).map(c => c.replace(/^"|"$/g, '').trim())
          return Object.fromEntries(hdrs.map((h, i) => [h, cols[i] || '']))
        })
        setHeaders(hdrs)
        setRows(parsed)
      } catch {
        setError('Falha ao ler o arquivo. Verifique se é um CSV válido.')
      }
    }
    reader.readAsText(file, 'UTF-8')
  }

  const handleDrop = (e) => {
    e.preventDefault()
    parseFile(e.dataTransfer.files[0])
  }

  const exportSample = () => {
    const sample = 'nome_documento,id_pncp,orgao,data_prevista\n' +
      '"Edital Exemplo 001",123456/2025,"Prefeitura Municipal",2025-06-01\n' +
      '"Edital Exemplo 002",789012/2025,"Governo do Estado",2025-06-15'
    const blob = new Blob([sample], { type: 'text/csv' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url; a.download = 'modelo_importacao.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-slate-950 dark:text-white">Importar planilha de editais</p>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">CSV ou Excel com os documentos a acompanhar</p>
        </div>
        <div className="flex gap-2">
          <button onClick={exportSample} className="btn-ghost text-xs py-1.5 px-3">
            ↓ Modelo CSV
          </button>
          <button
            onClick={onClose}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-500 transition-colors hover:border-slate-300 hover:text-slate-700 dark:border-slate-700 dark:text-slate-400 dark:hover:text-white"
          >
            ×
          </button>
        </div>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={e => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => fileRef.current?.click()}
        className="cursor-pointer rounded-lg border-2 border-dashed border-slate-300 p-8 text-center transition-colors hover:border-brand hover:bg-blue-50/50 dark:border-slate-700 dark:hover:border-brand-light dark:hover:bg-brand/5"
      >
        <div className="text-3xl mb-2">📊</div>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          Arraste seu arquivo ou{' '}
          <span className="font-medium text-brand dark:text-brand-light">clique para selecionar</span>
        </p>
        <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">Formatos aceitos: .csv, .xlsx, .xls</p>
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          className="hidden"
          onChange={e => parseFile(e.target.files[0])}
        />
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 dark:border-red-800 dark:bg-red-950/40">
          <span className="text-sm text-red-700 dark:text-red-300">⚠️ {error}</span>
        </div>
      )}

      {/* Preview da planilha */}
      {rows.length > 0 && (
        <div>
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {rows.length} registro{rows.length !== 1 ? 's' : ''} importado{rows.length !== 1 ? 's' : ''}
            </p>
            <button
              onClick={() => { setRows([]); setHeaders([]) }}
              className="text-xs text-slate-400 transition-colors hover:text-red-600 dark:text-slate-500 dark:hover:text-red-400"
            >
              Limpar
            </button>
          </div>
          <div className="max-h-56 overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700">
            <table className="w-full text-xs">
              <thead className="sticky top-0 border-b border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-900">
                <tr>
                  <th className="px-3 py-2 text-left text-slate-500 dark:text-slate-400">#</th>
                  {headers.map(h => (
                    <th key={h} className="whitespace-nowrap px-3 py-2 text-left capitalize text-slate-500 dark:text-slate-400">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {rows.map((row, i) => (
                  <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <td className="px-3 py-2 text-slate-400 dark:text-slate-500">{i + 1}</td>
                    {headers.map(h => (
                      <td key={h} className="max-w-[200px] truncate whitespace-nowrap px-3 py-2 text-slate-700 dark:text-slate-300">
                        {row[h] || '—'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[10px] text-slate-400 dark:text-slate-500">
            Os documentos acima são apenas para referência. Para processar, faça upload dos PDFs em Novo Edital.
          </p>
        </div>
      )}
    </div>
  )
}

// ── Page principal ───────────────────────────────────────────────────────────

export default function Controle() {
  const [editais,     setEditais]     = useState([])
  const [jobs,        setJobs]        = useState([])
  const [loading,     setLoading]     = useState(true)
  const [filterStatus, setFilterStatus] = useState('all')
  const [search,      setSearch]      = useState('')
  const [showImport,  setShowImport]  = useState(false)

  const intervalRef = useRef(null)
  const navigate    = useNavigate()

  const fetchData = async (initial = false) => {
    if (initial) setLoading(true)
    try {
      const [eRes, jRes] = await Promise.all([
        editaisApi.list(),
        jobsApi.list(),
      ])
      setEditais(Array.isArray(eRes.data) ? eRes.data : [])
      setJobs(Array.isArray(jRes.data) ? jRes.data : [])
    } catch {
      // silent refresh fail
    } finally {
      if (initial) setLoading(false)
    }
  }

  useEffect(() => {
    fetchData(true)
    intervalRef.current = setInterval(() => fetchData(false), 5_000)
    return () => clearInterval(intervalRef.current)
  }, [])

  // Junta edital com seu job mais recente
  // job.progress vem da API como float 0.0–1.0, converte para 0–100
  const rows = editais.map(e => {
    const eJobs = jobs.filter(
      j => j.result?.edital_id === e.id || j.edital_id === e.id
    )
    const latest = eJobs.sort(
      (a, b) => new Date(b.created_at) - new Date(a.created_at)
    )[0]
    const rawProgress = latest?.progress || 0
    const progress = latest?.status === 'done'
      ? 100
      : rawProgress > 1
        ? Math.round(rawProgress)           // já é 0-100
        : Math.round(rawProgress * 100)     // era 0.0-1.0
    return {
      ...e,
      job:      latest || null,
      status:   latest?.status || 'unknown',
      progress,
    }
  })

  const counts = {
    all:     rows.length,
    done:    rows.filter(r => r.status === 'done').length,
    running: rows.filter(r => r.status === 'running').length,
    pending: rows.filter(r => r.status === 'pending').length,
    failed:  rows.filter(r => r.status === 'failed').length,
  }

  const filtered = rows
    .filter(r => filterStatus === 'all' || r.status === filterStatus)
    .filter(r =>
      !search ||
      r.filename?.toLowerCase().includes(search.toLowerCase()) ||
      String(r.id).includes(search)
    )

  const exportCsv = () => {
    const hdrs = ['ID', 'Arquivo', 'Chunks', 'Requisitos', 'Status', 'Progresso',
                  'Upload', 'Início Processamento', 'Fim Processamento', 'Duração']
    const lines = [
      hdrs.join(','),
      ...filtered.map(r => [
        r.id,
        `"${r.filename || ''}"`,
        r.chunks || 0,
        r.requirements || 0,
        r.status,
        r.progress + '%',
        fmt(r.parse_date),
        fmt(r.job?.started_at),
        fmt(r.job?.finished_at),
        fmtDur(r.job?.duration_seconds),
      ].join(','))
    ]
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url
    a.download = `controle_editais_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen space-y-6 p-6 lg:p-8">

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Controle de Editais</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Acompanhamento em tempo real do processamento dos documentos
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setShowImport(v => !v)}
            className={`btn-ghost flex items-center gap-2 px-4 py-2 text-sm ${showImport ? 'border-brand bg-blue-50 text-brand dark:border-brand-light dark:bg-blue-950/30 dark:text-brand-light' : ''}`}
          >
            <span>↑</span>
            <span>Importar planilha</span>
          </button>
          <button
            onClick={exportCsv}
            className="btn-ghost flex items-center gap-2 px-4 py-2 text-sm"
          >
            <span>↓</span>
            <span>Exportar CSV</span>
          </button>
          <button
            onClick={() => fetchData(false)}
            className="btn-ghost px-3 py-2 text-sm"
            title="Atualizar agora"
          >
            ↻
          </button>
        </div>
      </div>

      {/* Importar planilha */}
      {showImport && <ImportPanel onClose={() => setShowImport(false)} />}

      {/* Cards de status */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {[
          { key: 'all',     label: 'Total',       icon: '▦', accent: 'text-slate-900 dark:text-white'            },
          { key: 'done',    label: 'Concluídos',  icon: '✓', accent: 'text-emerald-600 dark:text-emerald-400'    },
          { key: 'running', label: 'Processando', icon: '⟳', accent: 'text-blue-600 dark:text-blue-400'          },
          { key: 'pending', label: 'Aguardando',  icon: '◌', accent: 'text-amber-600 dark:text-amber-400'        },
          { key: 'failed',  label: 'Com erro',    icon: '✕', accent: 'text-red-600 dark:text-red-400'            },
        ].map(({ key, label, icon, accent }) => (
          <button
            key={key}
            onClick={() => setFilterStatus(key)}
            className={`rounded-lg border p-4 text-left transition-colors ${
              filterStatus === key
                ? 'border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950/30'
                : 'border-slate-200 bg-white hover:border-slate-300 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-slate-600'
            }`}
          >
            <p className="text-xs text-slate-500 dark:text-slate-400">{icon} {label}</p>
            <p className={`mt-1 text-2xl font-bold ${accent}`}>
              {loading ? '—' : counts[key]}
            </p>
          </button>
        ))}
      </div>

      {/* Barra de busca */}
      <div className="flex gap-3">
        <input
          type="text"
          placeholder="Buscar por nome do arquivo ou ID…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="input flex-1 py-2 text-sm"
        />
        {search && (
          <button
            onClick={() => setSearch('')}
            className="btn-ghost px-3 py-2 text-sm"
          >
            Limpar
          </button>
        )}
      </div>

      {/* Lista de cartões no mobile */}
      <section className="space-y-3 md:hidden" aria-label="Editais">
        {loading ? [...Array(4)].map((_, index) => (
          <div key={index} className="h-48 animate-pulse rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800" />
        )) : filtered.length === 0 ? (
          <div className="rounded-lg border border-slate-200 bg-white px-4 py-16 text-center dark:border-slate-700 dark:bg-slate-800">
            <div className="mb-3 text-4xl">📋</div>
            <p className="text-sm text-slate-500 dark:text-slate-400">{search || filterStatus !== 'all' ? 'Nenhum edital encontrado com este filtro.' : 'Nenhum edital processado ainda. Faça upload em Novo Edital.'}</p>
          </div>
        ) : filtered.map((row) => <EditalMobileCard key={row.id} row={row} navigate={navigate} />)}
      </section>

      {/* Tabela principal */}
      <div className="hidden overflow-hidden rounded-lg border border-slate-200 bg-white md:block dark:border-slate-700 dark:bg-slate-800">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-900">
              <tr>
                {[
                  'ID', 'Arquivo', 'Status', 'Progresso',
                  'Data Upload', 'Início', 'Fim', 'Duração', 'Ações'
                ].map(h => (
                  <th key={h} className="whitespace-nowrap px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {loading ? (
                // Skeleton
                [...Array(5)].map((_, i) => (
                  <tr key={i}>
                    {[...Array(9)].map((_, j) => (
                      <td key={j} className="px-4 py-4">
                        <div className="h-3 animate-pulse rounded bg-slate-200 dark:bg-slate-700" style={{ width: `${40 + Math.random() * 40}%` }} />
                      </td>
                    ))}
                  </tr>
                ))
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-16 text-center">
                    <div className="text-4xl mb-3">📋</div>
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      {search || filterStatus !== 'all'
                        ? 'Nenhum edital encontrado com este filtro.'
                        : 'Nenhum edital processado ainda. Faça upload em Novo Edital.'}
                    </p>
                  </td>
                </tr>
              ) : (
                filtered.map(row => (
                  <tr
                    key={row.id}
                    className="cursor-pointer transition-colors hover:bg-slate-50 dark:hover:bg-slate-700/50"
                    onClick={() => navigate(`/editais/${row.id}`)}
                  >
                    {/* ID */}
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-slate-400 dark:text-slate-500">#{row.id}</span>
                    </td>

                    {/* Arquivo */}
                    <td className="max-w-[220px] px-4 py-3">
                      <p className="truncate text-sm font-medium text-slate-900 dark:text-white">{row.filename}</p>
                      <p className="mt-0.5 font-mono text-xs text-slate-500 dark:text-slate-400">
                        {row.chunks} chunks · {row.requirements} req.
                      </p>
                    </td>

                    {/* Status */}
                    <td className="whitespace-nowrap px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>

                    {/* Progresso */}
                    <td className="min-w-[120px] px-4 py-3">
                      <ProgressBar progress={row.progress} status={row.status} />
                    </td>

                    {/* Data Upload */}
                    <td className="whitespace-nowrap px-4 py-3">
                      <span className="font-mono text-xs text-slate-500 dark:text-slate-400">{fmt(row.parse_date)}</span>
                    </td>

                    {/* Início processamento */}
                    <td className="whitespace-nowrap px-4 py-3">
                      <span className="font-mono text-xs text-slate-500 dark:text-slate-400">{fmt(row.job?.started_at)}</span>
                    </td>

                    {/* Fim processamento */}
                    <td className="whitespace-nowrap px-4 py-3">
                      <span className="font-mono text-xs text-slate-500 dark:text-slate-400">{fmt(row.job?.finished_at)}</span>
                    </td>

                    {/* Duração */}
                    <td className="whitespace-nowrap px-4 py-3">
                      <span className="font-mono text-xs text-slate-500 dark:text-slate-400">{fmtDur(row.job?.duration_seconds)}</span>
                    </td>

                    {/* Ações */}
                    <td className="px-4 py-3" onClick={e => e.stopPropagation()}>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => navigate(`/editais/${row.id}`)}
                          className="rounded px-2 py-1 text-xs font-medium text-brand transition-colors hover:bg-blue-50 hover:text-brand-dark dark:text-brand-light dark:hover:bg-blue-950/30"
                        >
                          Ver
                        </button>
                        {AI_FEATURES_ENABLED && (
                          <button
                            onClick={() => navigate(`/editais/${row.id}/chat`)}
                            className="rounded px-2 py-1 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800 dark:text-slate-400 dark:hover:bg-slate-700 dark:hover:text-white"
                          >
                            Chat
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Footer da tabela */}
        {!loading && filtered.length > 0 && (
          <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-4 py-2.5 dark:border-slate-700 dark:bg-slate-900">
            <p className="font-mono text-xs text-slate-500 dark:text-slate-400">
              {filtered.length} registro{filtered.length !== 1 ? 's' : ''} exibido{filtered.length !== 1 ? 's' : ''}
            </p>
            <p className="font-mono text-xs text-slate-400 dark:text-slate-500">
              ↻ Atualização automática a cada 5s
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
