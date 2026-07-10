/**
 * pages/AnalysisDashboard.jsx
 * ─────────────────────────────
 * Dashboard de BI dos editais/itens ingeridos via JSON (schema v7.3).
 * KPIs + blocos por categoria + listagem de editais, com toggle de
 * período (diário/semanal/mensal/anual) e atualização ao vivo (polling).
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { analysisApi } from '../api/client'

const PERIODS = [
  { key: 'day', label: 'Diário' },
  { key: 'week', label: 'Semanal' },
  { key: 'month', label: 'Mensal' },
  { key: 'year', label: 'Anual' },
]

const POLL_MS = 20_000

function KPICard({ label, value, accent }) {
  return (
    <div className="card flex flex-col gap-1">
      <p className="text-xs font-mono text-gray-500 uppercase tracking-widest">{label}</p>
      <p className={`font-display font-extrabold text-3xl ${accent || 'text-white'}`}>{value}</p>
    </div>
  )
}

function HBar({ label, value, max, colorClass = 'text-azure-glow' }) {
  const pctWidth = max > 0 ? (value / max) * 100 : 0
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="font-mono text-xs text-gray-300 truncate max-w-[160px]">{label}</span>
        <span className={`font-mono text-xs font-bold ${colorClass}`}>{value}</span>
      </div>
      <div className="h-1.5 bg-slate-border rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${colorClass.replace('text-', 'bg-')}`}
          style={{ width: `${pctWidth}%` }}
        />
      </div>
    </div>
  )
}

function formatMoney(value) {
  if (!value) return 'R$ 0,00'
  return Number(value).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

export default function AnalysisDashboard() {
  const navigate = useNavigate()
  const [period, setPeriod] = useState('month')
  const [dashboard, setDashboard] = useState(null)
  const [editais, setEditais] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [lastUpdated, setLastUpdated] = useState(null)
  const intervalRef = useRef(null)

  const fetchAll = useCallback(async (showSpinner) => {
    if (showSpinner) setLoading(true)
    setError('')
    try {
      const [dashRes, editaisRes] = await Promise.all([
        analysisApi.dashboard({ period }),
        analysisApi.editaisListagem(),
      ])
      setDashboard(dashRes.data)
      setEditais(editaisRes.data)
      setLastUpdated(new Date())
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao carregar dashboard.')
    } finally {
      if (showSpinner) setLoading(false)
    }
  }, [period])

  useEffect(() => {
    fetchAll(true)
    intervalRef.current = setInterval(() => fetchAll(false), POLL_MS)
    return () => clearInterval(intervalRef.current)
  }, [fetchAll])

  const kpis = dashboard?.kpis || {}
  const categories = dashboard?.categories || []

  return (
    <div className="p-6 space-y-6 min-h-screen">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <h1 className="font-display font-black text-2xl text-white">BI de Editais</h1>
          <p className="text-sm text-gray-500 font-mono mt-1">
            {lastUpdated ? `Atualizado às ${lastUpdated.toLocaleTimeString('pt-BR')}` : 'Carregando…'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => fetchAll(true)} className="btn-ghost text-xs px-3 py-2">
            ↻ Atualizar
          </button>
          <button onClick={() => navigate('/analise/upload')} className="btn-primary text-xs px-3 py-2">
            + Importar JSON
          </button>
        </div>
      </div>

      {/* Toggle de período */}
      <div className="flex gap-1 flex-wrap">
        {PERIODS.map((p) => (
          <button
            key={p.key}
            onClick={() => setPeriod(p.key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono border transition-all ${
              period === p.key
                ? 'bg-azure text-white border-azure'
                : 'text-gray-400 border-slate-border hover:text-white hover:bg-slate-hover'
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="px-4 py-3 rounded-lg bg-red-500/5 border border-red-500/20 text-xs text-red-400">
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-14 rounded-xl bg-slate-card border border-slate-border animate-pulse" />
          ))}
        </div>
      ) : (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <KPICard label="Editais selecionados" value={kpis.editais_selecionados ?? 0} />
            <KPICard label="Itens categorizados" value={kpis.itens_categorizados ?? 0} />
            <KPICard label="Unidades mapeadas" value={Math.round(kpis.unidades_mapeadas ?? 0)} />
            <KPICard label="Editais com risco" value={kpis.editais_com_risco ?? 0} accent="text-red-400" />
            <KPICard label="Com ME/EPP" value={kpis.editais_com_me_epp ?? 0} accent="text-amber" />
          </div>

          {/* Blocos por categoria */}
          {categories.length === 0 ? (
            <div className="card text-center py-14">
              <p className="text-sm text-gray-500">Nenhum item categorizado neste período. Importe um JSON para começar.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {categories.map((cat) => {
                const breakdownEntries = Object.entries(cat.breakdowns || {})
                return (
                  <div key={cat.categoria} className="card p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="font-display font-bold text-white">{cat.categoria}</h3>
                      <span className="text-xs font-mono text-gray-500">{cat.itens} itens</span>
                    </div>
                    <div className="grid grid-cols-2 gap-3 text-xs font-mono text-gray-400">
                      <span>Unidades: <span className="text-white">{Math.round(cat.unidades)}</span></span>
                      <span>Valor mapeado: <span className="text-white">{formatMoney(cat.valor_mapeado)}</span></span>
                    </div>
                    {breakdownEntries.map(([field, rows]) => {
                      if (!rows.length) return null
                      const max = Math.max(...rows.map((r) => r.unidades))
                      return (
                        <div key={field} className="space-y-1.5">
                          <p className="text-[10px] text-gray-500 font-mono uppercase tracking-wider">
                            {field.replace(/_/g, ' ')}
                          </p>
                          {rows.map((r) => (
                            <HBar key={r.valor} label={r.valor} value={r.unidades} max={max} />
                          ))}
                        </div>
                      )
                    })}
                  </div>
                )
              })}
            </div>
          )}

          {/* Listagem de editais */}
          <div className="space-y-2">
            <h3 className="font-display font-bold text-white">Editais</h3>
            {editais.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-10">Nenhum edital importado ainda.</p>
            ) : (
              editais.map((e) => (
                <button
                  key={e.id}
                  onClick={() => navigate(`/analise/documentos/${e.id}`)}
                  className="card w-full text-left p-4 hover:bg-slate-hover/20 transition-colors flex items-center justify-between gap-3"
                >
                  <div className="min-w-0">
                    <p className="text-sm text-white font-medium truncate">{e.orgao || e.source_name}</p>
                    <p className="text-xs text-gray-500 font-mono mt-0.5">
                      {e.numero_pregao} {e.uf ? `· ${e.uf}` : ''} {e.data_disputa ? `· ${e.data_disputa}` : ''}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {e.risco_identificado && e.risco_identificado !== 'Nenhum' && (
                      <span className="text-amber text-xs">⚠</span>
                    )}
                    <span className="text-[10px] font-mono text-gray-500">{e.items?.length ?? 0} itens</span>
                  </div>
                </button>
              ))
            )}
          </div>
        </>
      )}
    </div>
  )
}
