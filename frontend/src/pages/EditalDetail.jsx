/**
 * pages/EditalDetail.jsx
 * ───────────────────────
 * Resultados de matching + acesso ao chat RAG do edital.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { editaisApi, exportApi, downloadBlob } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'

const STATUS_CFG = {
  atende:     { label: 'Atende',      cls: 'badge-atende',    dot: 'bg-green-match' },
  nao_atende: { label: 'Não atende',  cls: 'badge-falhou',    dot: 'bg-red-fail'    },
  verificar:  { label: 'Verificar',   cls: 'badge-verificar', dot: 'bg-yellow-warn' },
}

const LOCK_TTL_MS = 45_000
const LOCK_HEARTBEAT_MS = 12_000

function getTabId() {
  const current = sessionStorage.getItem('edital_detail_tab_id')
  if (current) return current
  const next = `tab-${Date.now()}-${Math.random().toString(36).slice(2)}`
  sessionStorage.setItem('edital_detail_tab_id', next)
  return next
}

function isLockActive(lock) {
  return lock && Date.now() - Number(lock.updatedAt || 0) < LOCK_TTL_MS
}

function readLock(key) {
  try {
    return JSON.parse(localStorage.getItem(key) || 'null')
  } catch {
    return null
  }
}

function writeLock(key, lock) {
  localStorage.setItem(key, JSON.stringify(lock))
}

function useEditalLock(editalId, user) {
  const [tabId] = useState(() => getTabId())
  const [state, setState] = useState({ active: false, owned_by_me: false, blocked: false, lock: null })
  const lockKey = useMemo(() => `tor_edital_lock_${editalId}`, [editalId])
  const ownerName = user?.full_name || user?.email || 'Usuario'
  const ownerRole = user?.role || 'viewer'

  const makeLock = useCallback(() => ({
    editalId,
    tabId,
    ownerName,
    ownerRole,
    updatedAt: Date.now(),
  }), [editalId, ownerName, ownerRole, tabId])

  const refresh = useCallback(() => {
    return editaisApi.heartbeatLock(editalId, tabId)
      .then((res) => setState(res.data))
      .catch(() => {
        const current = readLock(lockKey)
        if (!isLockActive(current) || current?.tabId === tabId) {
          const next = makeLock()
          writeLock(lockKey, next)
          setState({ active: true, owned_by_me: true, blocked: false, lock: { ...next, owner_name: next.ownerName } })
          return
        }
        setState({ active: true, owned_by_me: false, blocked: true, lock: { ...current, owner_name: current.ownerName } })
      })
  }, [editalId, lockKey, makeLock, tabId])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, LOCK_HEARTBEAT_MS)
    const onStorage = (event) => {
      if (event.key !== lockKey) return
      const current = readLock(lockKey)
      if (!isLockActive(current)) {
        setState({ active: false, owned_by_me: false, blocked: false, lock: null })
      } else {
        setState({
          active: true,
          owned_by_me: current?.tabId === tabId,
          blocked: current?.tabId !== tabId,
          lock: { ...current, owner_name: current.ownerName },
        })
      }
    }
    window.addEventListener('storage', onStorage)

    return () => {
      clearInterval(interval)
      window.removeEventListener('storage', onStorage)
      editaisApi.releaseLock(editalId, tabId).catch(() => {})
      const current = readLock(lockKey)
      if (current?.tabId === tabId) localStorage.removeItem(lockKey)
    }
  }, [editalId, lockKey, refresh, tabId])

  return {
    lock: state.lock,
    ownedByMe: state.owned_by_me,
    blocked: state.blocked,
    claim: refresh,
  }
}

function CollaborationTag({ lockState }) {
  const { lock, ownedByMe, blocked, claim } = lockState
  if (blocked) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="font-semibold">Documento em uso por {lock?.owner_name || lock?.ownerName || 'outro usuario'}</p>
            <p className="mt-1 text-xs">As acoes principais foram bloqueadas para evitar duas pessoas trabalhando no mesmo edital.</p>
          </div>
          <button type="button" onClick={claim} className="btn-ghost">Verificar novamente</button>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
      <span className="font-semibold">{ownedByMe ? 'Voce esta neste edital' : 'Edital livre'}</span>
      <span className="ml-2 text-xs">Monitoramento ativo para evitar conflito de trabalho.</span>
    </div>
  )
}

export default function EditalDetail() {
  const { id }                    = useParams()
  const navigate                  = useNavigate()
  const { user }                  = useAuth()
  const { toast }                 = useToast()
  const [results,   setResults]   = useState([])
  const [loading,   setLoading]   = useState(true)
  const [selected,  setSelected]  = useState(null)
  const [exporting, setExporting] = useState(null)
  const lockState                 = useEditalLock(id, user)

  useEffect(() => {
    editaisApi.results(id)
      .then(r => {
        const byProduct = {}
        for (const row of r.data.results) {
          if (!byProduct[row.product]) byProduct[row.product] = { product: row.product, rows: [] }
          byProduct[row.product].rows.push(row)
        }
        const produtos = Object.values(byProduct).map(p => {
          const scores = p.rows.map(r => r.score || 0)
          const avg    = scores.reduce((a, b) => a + b, 0) / (scores.length || 1)
          return { ...p, avgScore: avg }
        }).sort((a, b) => b.avgScore - a.avgScore)

        setResults(produtos)
        if (produtos[0]) setSelected(produtos[0].product)
      })
      .finally(() => setLoading(false))
  }, [id])

  const handleExport = async (tipo) => {
    if (lockState.blocked) {
      toast({ type: 'error', message: 'Este edital esta em uso por outro usuario.' })
      return
    }
    setExporting(tipo)
    try {
      const fn  = { xlsx: exportApi.xlsx, pdf: exportApi.pdf, csv: exportApi.csv }[tipo]
      const res = await fn(id)
      downloadBlob(res.data, `edital_${id}_resultado.${tipo}`)
      toast({ type: 'success', message: `Exportação ${tipo.toUpperCase()} concluída.` })
    } catch (err) {
      toast({
        type:    'error',
        title:   'Erro ao exportar',
        message: err.response?.data?.detail || `Não foi possível exportar como ${tipo.toUpperCase()}.`,
      })
    } finally {
      setExporting(null)
    }
  }

  const selectedData = results.find(p => p.product === selected)

  if (loading) return (
    <div className="p-8">
      <div className="animate-pulse space-y-4">
        <div className="h-8 bg-slate-border rounded w-64" />
        <div className="h-4 bg-slate-border rounded w-48" />
        <div className="grid grid-cols-3 gap-4 mt-6">
          {[1,2,3].map(i => <div key={i} className="h-24 bg-slate-800 rounded-lg border border-slate-700" />)}
        </div>
      </div>
    </div>
  )

  return (
    <div className="p-8">

      {/* ── Header ──────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <button
              onClick={() => navigate('/dashboard')}
              className="text-xs font-mono text-gray-500 hover:text-red-400 transition-colors"
            >
              ← Dashboard
            </button>
            <span className="text-gray-600 text-xs">/</span>
            <p className="text-xs font-mono text-gray-500">Edital #{id}</p>
          </div>
          <h1 className="font-display font-black text-3xl text-white">Resultados</h1>
          <p className="text-gray-400 text-sm mt-1">{results.length} produtos analisados</p>
        </div>

        {/* Ações do header */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Análise LLM */}
          <button
            disabled={lockState.blocked}
            onClick={() => navigate(`/editais/${id}/analise-llm`)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-amber/30 bg-amber/10 hover:border-amber/60 text-amber font-body text-sm transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <span>🤖</span>
            Análise LLM
          </button>

          {/* Chat RAG — destaque */}
          <button
            disabled={lockState.blocked}
            onClick={() => navigate(`/editais/${id}/chat`)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-red-600/20 to-amber/20 border border-red-600/30 hover:border-red-600/60 text-red-400 font-body text-sm transition-all duration-200 hover:shadow-lg hover:shadow-red-600/10 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <span>💬</span>
            Perguntar ao edital
          </button>

          <button
            onClick={() => navigate('/assinatura')}
            className="btn-ghost text-xs px-3 py-2"
          >
            Assinatura
          </button>

          {/* Exportar */}
          {[['xlsx','XLS ↓'], ['csv','CSV ↓']].map(([tipo, label]) => (
            <button
              key={tipo}
              disabled={!!exporting || lockState.blocked}
              onClick={() => handleExport(tipo)}
              className="btn-ghost text-xs px-3 py-2 disabled:opacity-40"
            >
              {exporting === tipo ? '…' : label}
            </button>
          ))}
        </div>
      </div>

      <div className="mb-6">
        <CollaborationTag lockState={lockState} />
      </div>

      <div className="grid grid-cols-12 gap-6">

        {/* ── Ranking lateral ──────────────────────────────────────── */}
        <div className="col-span-4 space-y-2">
          <p className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-3">
            Ranking de Produtos
          </p>
          {results.length === 0 ? (
            <div className="card text-center py-12 text-gray-500 text-sm">
              Nenhum resultado ainda.<br />Execute o matching primeiro.
            </div>
          ) : (
            results.map((p, i) => {
              const pct        = Math.round(p.avgScore * 100)
              const isSelected = selected === p.product
              return (
                <button
                  key={p.product}
                  disabled={lockState.blocked}
                  onClick={() => setSelected(p.product)}
                  className={`w-full text-left card py-3.5 px-4 transition-all duration-200
                    ${isSelected
                      ? 'border-red-600/50 bg-red-600/5 shadow-sm shadow-red-600/10'
                      : 'hover:border-slate-700/80 hover:bg-slate-hover'
                    } disabled:cursor-not-allowed disabled:opacity-60`}
                >
                  <div className="flex items-center gap-3">
                    <span className={`font-display font-bold text-lg w-6 flex-shrink-0 ${i === 0 ? 'text-amber' : 'text-gray-600'}`}>
                      {i + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className={`font-mono text-sm font-medium truncate ${isSelected ? 'text-red-400' : 'text-white'}`}>
                        {p.product}
                      </p>
                      <div className="mt-1.5 h-1 bg-slate-border rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-700 ${pct >= 75 ? 'bg-green-match' : pct >= 45 ? 'bg-yellow-warn' : 'bg-red-fail'}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                    <span className={`font-mono text-xs font-bold flex-shrink-0 ${pct >= 75 ? 'text-green-match' : pct >= 45 ? 'text-yellow-warn' : 'text-red-fail'}`}>
                      {pct}%
                    </span>
                  </div>
                </button>
              )
            })
          )}
        </div>

        {/* ── Detalhes do produto selecionado ──────────────────────── */}
        <div className="col-span-8">
          {selectedData ? (
            <>
              <div className="flex items-center justify-between mb-5">
                <div>
                  <p className="font-display font-bold text-xl text-white">{selectedData.product}</p>
                  <p className="text-xs text-gray-500 font-mono mt-0.5">{selectedData.rows.length} requisito{selectedData.rows.length !== 1 ? 's' : ''} avaliado{selectedData.rows.length !== 1 ? 's' : ''}</p>
                </div>
                <div className="text-right">
                  <span className="font-mono text-3xl font-black text-red-400">
                    {Math.round(selectedData.avgScore * 100)}%
                  </span>
                  <p className="text-xs text-gray-500 font-mono">compatibilidade</p>
                </div>
              </div>

              {/* Barra de progresso geral */}
              <div className="h-1.5 bg-slate-border rounded-full overflow-hidden mb-5">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-red-600 to-amber transition-all duration-1000"
                  style={{ width: `${Math.round(selectedData.avgScore * 100)}%` }}
                />
              </div>

              <div className="space-y-2">
                {selectedData.rows.map((row, i) => {
                  const cfg = STATUS_CFG[row.status] || STATUS_CFG.verificar
                  const pct = Math.round((row.score || 0) * 100)
                  return (
                    <div
                      key={i}
                      className="card py-4 animate-fade-up"
                      style={{ animationDelay: `${i * 40}ms` }}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3">
                          <div className={`w-2 h-2 rounded-full flex-shrink-0 ${cfg.dot}`} />
                          <p className="font-mono text-sm text-white font-medium">{row.attribute}</p>
                        </div>
                        <span className={cfg.cls}>{cfg.label}</span>
                      </div>

                      <div className="h-0.5 bg-slate-border rounded-full overflow-hidden mb-3">
                        <div
                          className={`h-full rounded-full transition-all duration-700 ${
                            row.status === 'atende'     ? 'bg-green-match' :
                            row.status === 'verificar'  ? 'bg-yellow-warn' : 'bg-red-fail'
                          }`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>

                      {row.reasoning && (
                        <p className="text-xs text-gray-500 font-body leading-relaxed">{row.reasoning}</p>
                      )}
                    </div>
                  )
                })}
              </div>
            </>
          ) : (
            <div className="card h-64 flex flex-col items-center justify-center gap-3 text-gray-500">
              <span className="text-3xl">📊</span>
              <p className="text-sm">Selecione um produto no ranking</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
