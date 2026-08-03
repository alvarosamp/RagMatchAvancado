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

// ── Utilitários ──────────────────────────────────────────────────────────────

const STATUS_CFG = {
  done:    { label: 'Concluído',    color: 'text-green-match', bg: 'bg-green-match/10 border-green-match/30' },
  running: { label: 'Processando',  color: 'text-red-400',  bg: 'bg-red-600/10 border-red-600/30'            },
  pending: { label: 'Aguardando',   color: 'text-amber',       bg: 'bg-amber/10 border-amber/30'            },
  failed:  { label: 'Erro',         color: 'text-red-fail',    bg: 'bg-red-fail/10 border-red-fail/30'      },
  unknown: { label: 'Sem info',     color: 'text-gray-500',    bg: 'bg-slate-border/20 border-slate-700' },
}

function StatusBadge({ status }) {
  const cfg = STATUS_CFG[status] || STATUS_CFG.unknown
  return (
    <span className={`inline-flex items-center text-xs font-mono px-2 py-0.5 rounded border ${cfg.bg} ${cfg.color}`}>
      {cfg.label}
    </span>
  )
}

function ProgressBar({ progress, status }) {
  const pct = status === 'done' ? 100 : (progress || 0)
  const bar = status === 'done' ? 'bg-green-match' : status === 'failed' ? 'bg-red-fail' : 'bg-red-600'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-border/30 rounded-full overflow-hidden">
        <div
          className={`h-full ${bar} rounded-full transition-all duration-500 ${status === 'running' ? 'animate-pulse' : ''}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[10px] font-mono text-gray-600 w-8 text-right">{pct}%</span>
    </div>
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
    <div className="card border border-red-600/20 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-display font-bold text-white text-sm">Importar planilha de editais</p>
          <p className="text-xs text-gray-500 font-mono mt-0.5">CSV ou Excel com os documentos a acompanhar</p>
        </div>
        <div className="flex gap-2">
          <button onClick={exportSample} className="btn-ghost text-xs py-1.5 px-3">
            ↓ Modelo CSV
          </button>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors text-lg leading-none px-2">×</button>
        </div>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={e => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => fileRef.current?.click()}
        className="border-2 border-dashed border-slate-700 rounded-lg p-8 text-center
                   cursor-pointer hover:border-red-600/40 hover:bg-red-600/3 transition-all"
      >
        <div className="text-3xl mb-2">📊</div>
        <p className="text-sm text-gray-400">
          Arraste seu arquivo ou{' '}
          <span className="text-red-400 font-medium">clique para selecionar</span>
        </p>
        <p className="text-xs text-gray-600 mt-1">Formatos aceitos: .csv, .xlsx, .xls</p>
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          className="hidden"
          onChange={e => parseFile(e.target.files[0])}
        />
      </div>

      {error && (
        <p className="text-xs text-red-fail font-mono">⚠️ {error}</p>
      )}

      {/* Preview da planilha */}
      {rows.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-gray-400 font-mono">
              {rows.length} registro{rows.length !== 1 ? 's' : ''} importado{rows.length !== 1 ? 's' : ''}
            </p>
            <button
              onClick={() => { setRows([]); setHeaders([]) }}
              className="text-xs text-gray-600 hover:text-red-fail font-mono transition-colors"
            >
              Limpar
            </button>
          </div>
          <div className="overflow-x-auto rounded-lg border border-slate-700 max-h-56">
            <table className="w-full text-xs font-mono">
              <thead className="bg-ink-100 border-b border-slate-700 sticky top-0">
                <tr>
                  <th className="px-3 py-2 text-left text-gray-600">#</th>
                  {headers.map(h => (
                    <th key={h} className="px-3 py-2 text-left text-gray-500 capitalize whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={i} className="border-b border-slate-700/20 hover:bg-slate-hover/20">
                    <td className="px-3 py-2 text-gray-600">{i + 1}</td>
                    {headers.map(h => (
                      <td key={h} className="px-3 py-2 text-gray-300 whitespace-nowrap max-w-[200px] truncate">
                        {row[h] || '—'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[10px] text-gray-600 font-mono mt-2">
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
    <div className="p-6 space-y-6 min-h-screen">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-display font-black text-2xl text-white">Controle de Editais</h1>
          <p className="text-sm text-gray-500 font-mono mt-1">
            Acompanhamento em tempo real do processamento dos documentos
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setShowImport(v => !v)}
            className={`btn-ghost text-sm px-4 py-2 flex items-center gap-2 ${showImport ? 'border-red-600/40 text-red-400' : ''}`}
          >
            <span>↑</span>
            <span>Importar planilha</span>
          </button>
          <button
            onClick={exportCsv}
            className="btn-ghost text-sm px-4 py-2 flex items-center gap-2"
          >
            <span>↓</span>
            <span>Exportar CSV</span>
          </button>
          <button
            onClick={() => fetchData(false)}
            className="btn-ghost text-sm px-3 py-2"
            title="Atualizar agora"
          >
            ↻
          </button>
        </div>
      </div>

      {/* Importar planilha */}
      {showImport && <ImportPanel onClose={() => setShowImport(false)} />}

      {/* Cards de status */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {[
          { key: 'all',     label: 'Total',        icon: '▦', accent: 'text-white'       },
          { key: 'done',    label: 'Concluídos',   icon: '✓', accent: 'text-green-match' },
          { key: 'running', label: 'Processando',  icon: '⟳', accent: 'text-red-400'  },
          { key: 'pending', label: 'Aguardando',   icon: '◌', accent: 'text-amber'       },
          { key: 'failed',  label: 'Com erro',     icon: '✕', accent: 'text-red-fail'    },
        ].map(({ key, label, icon, accent }) => (
          <button
            key={key}
            onClick={() => setFilterStatus(key)}
            className={`card p-4 text-left transition-all hover:border-red-600/30 cursor-pointer ${
              filterStatus === key ? 'border-red-600/40 bg-red-600/5' : ''
            }`}
          >
            <p className="text-xs text-gray-500 font-mono">{icon} {label}</p>
            <p className={`text-2xl font-display font-black mt-1 ${accent}`}>
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
          className="input flex-1 text-sm py-2"
        />
        {search && (
          <button
            onClick={() => setSearch('')}
            className="btn-ghost text-sm px-3 py-2"
          >
            Limpar
          </button>
        )}
      </div>

      {/* Tabela principal */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-ink-100 border-b border-slate-700">
              <tr>
                {[
                  'ID', 'Arquivo', 'Status', 'Progresso',
                  'Data Upload', 'Início', 'Fim', 'Duração', 'Ações'
                ].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-mono text-gray-500 uppercase tracking-wider whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-border/20">
              {loading ? (
                // Skeleton
                [...Array(5)].map((_, i) => (
                  <tr key={i}>
                    {[...Array(9)].map((_, j) => (
                      <td key={j} className="px-4 py-4">
                        <div className="h-3 rounded bg-slate-border/30 animate-pulse" style={{ width: `${40 + Math.random() * 40}%` }} />
                      </td>
                    ))}
                  </tr>
                ))
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-16 text-center">
                    <div className="text-4xl mb-3">📋</div>
                    <p className="text-sm text-gray-500 font-body">
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
                    className="hover:bg-slate-hover/20 transition-colors cursor-pointer"
                    onClick={() => navigate(`/editais/${row.id}`)}
                  >
                    {/* ID */}
                    <td className="px-4 py-3">
                      <span className="text-xs font-mono text-gray-500">#{row.id}</span>
                    </td>

                    {/* Arquivo */}
                    <td className="px-4 py-3 max-w-[220px]">
                      <p className="text-sm text-white font-body truncate">{row.filename}</p>
                      <p className="text-xs text-gray-600 font-mono mt-0.5">
                        {row.chunks} chunks · {row.requirements} req.
                      </p>
                    </td>

                    {/* Status */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <StatusBadge status={row.status} />
                    </td>

                    {/* Progresso */}
                    <td className="px-4 py-3 min-w-[120px]">
                      <ProgressBar progress={row.progress} status={row.status} />
                    </td>

                    {/* Data Upload */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className="text-xs font-mono text-gray-400">{fmt(row.parse_date)}</span>
                    </td>

                    {/* Início processamento */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className="text-xs font-mono text-gray-400">{fmt(row.job?.started_at)}</span>
                    </td>

                    {/* Fim processamento */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className="text-xs font-mono text-gray-400">{fmt(row.job?.finished_at)}</span>
                    </td>

                    {/* Duração */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className="text-xs font-mono text-gray-400">{fmtDur(row.job?.duration_seconds)}</span>
                    </td>

                    {/* Ações */}
                    <td className="px-4 py-3" onClick={e => e.stopPropagation()}>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => navigate(`/editais/${row.id}`)}
                          className="text-xs font-mono text-red-400 hover:text-white transition-colors
                                     px-2 py-1 rounded hover:bg-red-600/10"
                        >
                          Ver
                        </button>
                        <button
                          onClick={() => navigate(`/editais/${row.id}/chat`)}
                          className="text-xs font-mono text-gray-500 hover:text-white transition-colors
                                     px-2 py-1 rounded hover:bg-slate-hover"
                        >
                          Chat
                        </button>
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
          <div className="px-4 py-2.5 border-t border-slate-700/30 bg-ink-100 flex items-center justify-between">
            <p className="text-xs text-gray-600 font-mono">
              {filtered.length} registro{filtered.length !== 1 ? 's' : ''} exibido{filtered.length !== 1 ? 's' : ''}
            </p>
            <p className="text-xs text-gray-600 font-mono">
              ↻ Atualização automática a cada 5s
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
