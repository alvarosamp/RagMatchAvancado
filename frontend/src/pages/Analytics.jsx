/**
 * pages/Analytics.jsx
 * ────────────────────
 * Dashboard de análise de dados dos produtos.
 * Gráficos: ranking, distribuição de scores, gaps, evolução temporal.
 */

import { useEffect, useState, useCallback } from 'react'
import api from '../api/client'

// ── Hooks de dados ────────────────────────────────────────────────────────────

function useAnalytics() {
  const [data,    setData]    = useState({ overview: null, produtos: [], requisitos: [], evolucao: [], distribuicao: null })
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [ov, pr, re, ev, di] = await Promise.all([
        api.get('/analytics/overview'),
        api.get('/analytics/produtos'),
        api.get('/analytics/requisitos'),
        api.get('/analytics/evolucao'),
        api.get('/analytics/distribuicao'),
      ])
      setData({ overview: ov.data, produtos: pr.data, requisitos: re.data, evolucao: ev.data, distribuicao: di.data })
    } catch (e) {
      setError('Erro ao carregar dados de análise.')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])
  return { ...data, loading, error, reload: load }
}

// ── Utilitários ───────────────────────────────────────────────────────────────

const pct    = (v) => `${Math.round((v || 0) * 100)}%`
const round2 = (v) => ((v || 0) * 100).toFixed(1)

function scoreColor(score) {
  if (score >= 0.75) return 'text-green-match'
  if (score >= 0.45) return 'text-yellow-warn'
  return 'text-red-fail'
}
function scoreBarColor(score) {
  if (score >= 0.75) return 'bg-green-match'
  if (score >= 0.45) return 'bg-yellow-warn'
  return 'bg-red-fail'
}
function bucketColor(i) {
  if (i >= 7) return 'bg-green-match'
  if (i >= 4) return 'bg-yellow-warn'
  return 'bg-red-fail/70'
}

// ── Componentes de gráfico ───────────────────────────────────────────────────

function KPICard({ label, value, sub, accent }) {
  return (
    <div className="card flex flex-col gap-1 animate-fade-up">
      <p className="text-xs font-mono text-gray-500 uppercase tracking-widest">{label}</p>
      <p className={`font-display font-extrabold text-3xl ${accent || 'text-white'}`}>{value}</p>
      {sub && <p className="text-xs text-gray-500 font-body">{sub}</p>}
    </div>
  )
}

/** Barra horizontal com label e percentual */
function HBar({ label, value, max, colorClass, sub, delay = 0 }) {
  const pctWidth = max > 0 ? (value / max) * 100 : 0
  return (
    <div className="animate-fade-up" style={{ animationDelay: `${delay}ms` }}>
      <div className="flex items-center justify-between mb-1">
        <span className="font-mono text-xs text-gray-300 truncate max-w-[180px]">{label}</span>
        <span className={`font-mono text-xs font-bold ${colorClass}`}>{typeof value === 'number' && value <= 1 ? pct(value) : value}</span>
      </div>
      <div className="h-1.5 bg-slate-border rounded-full overflow-hidden mb-0.5">
        <div
          className={`h-full rounded-full transition-all duration-700 ${colorClass.replace('text-','bg-')}`}
          style={{ width: `${pctWidth}%` }}
        />
      </div>
      {sub && <p className="text-xs text-gray-600 font-mono">{sub}</p>}
    </div>
  )
}

/** Mini gráfico de pizza em SVG puro */
function DonutChart({ atende, verificar, nao_atende }) {
  const total = atende + verificar + nao_atende || 1
  const r = 40, cx = 50, cy = 50, stroke = 12

  function arc(start, size, color) {
    if (size === 0) return null
    const startRad = (start / total) * 2 * Math.PI - Math.PI / 2
    const endRad   = ((start + size) / total) * 2 * Math.PI - Math.PI / 2
    const x1 = cx + r * Math.cos(startRad)
    const y1 = cy + r * Math.sin(startRad)
    const x2 = cx + r * Math.cos(endRad)
    const y2 = cy + r * Math.sin(endRad)
    const large = size / total > 0.5 ? 1 : 0
    return (
      <path
        key={color}
        d={`M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`}
        fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
      />
    )
  }

  return (
    <svg viewBox="0 0 100 100" className="w-20 h-20">
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1E2A42" strokeWidth={stroke} />
      {arc(0,            atende,    '#10B981')}
      {arc(atende,       verificar, '#EAB308')}
      {arc(atende+verificar, nao_atende, '#EF4444')}
      <text x={cx} y={cy+1} textAnchor="middle" dominantBaseline="middle" fill="white" fontSize="14" fontWeight="bold" fontFamily="Syne">
        {Math.round(atende / total * 100)}%
      </text>
    </svg>
  )
}

/** Histograma de distribuição de scores */
function Histograma({ buckets, total }) {
  if (!buckets || buckets.length === 0) return null
  const maxCount = Math.max(...buckets.map(b => b.count), 1)

  return (
    <div className="flex items-end gap-1.5 h-32 mt-4">
      {buckets.map((b, i) => {
        const h = Math.max((b.count / maxCount) * 100, b.count > 0 ? 4 : 0)
        return (
          <div key={i} className="flex-1 flex flex-col items-center gap-1 group">
            <div className="relative w-full flex flex-col justify-end" style={{ height: '100px' }}>
              {/* Tooltip */}
              <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-ink-50 border border-slate-border rounded px-2 py-1 text-xs font-mono text-white whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity z-10 pointer-events-none">
                {b.count} ({Math.round(b.pct * 100)}%)
              </div>
              <div
                className={`w-full rounded-t transition-all duration-700 ${bucketColor(i)}`}
                style={{ height: `${h}%` }}
              />
            </div>
            <span className="text-xs font-mono text-gray-600" style={{ fontSize: '10px' }}>{b.faixa.split('-')[0]}</span>
          </div>
        )
      })}
    </div>
  )
}

/** Linha do tempo de evolução */
function EvolucaoChart({ evolucao }) {
  if (!evolucao || evolucao.length === 0) return (
    <p className="text-xs text-gray-500 font-mono py-4 text-center">Nenhum dado de evolução ainda.</p>
  )

  const maxScore = 1
  const pts      = evolucao.map((e, i) => ({
    x: evolucao.length === 1 ? 50 : (i / (evolucao.length - 1)) * 90 + 5,
    y: 95 - (e.score_medio / maxScore) * 85,
    ...e,
  }))

  const pathD = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')

  return (
    <div className="mt-4 relative">
      <svg viewBox="0 0 100 100" className="w-full h-36" preserveAspectRatio="none">
        {/* Grid lines */}
        {[25, 50, 75].map(y => (
          <line key={y} x1="0" y1={y} x2="100" y2={y} stroke="#1E2A42" strokeWidth="0.5" />
        ))}
        {/* Área preenchida */}
        <path d={`${pathD} L ${pts[pts.length-1].x} 100 L ${pts[0].x} 100 Z`}
              fill="rgba(59,130,246,0.08)" />
        {/* Linha */}
        <path d={pathD} fill="none" stroke="#3B82F6" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        {/* Pontos */}
        {pts.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r="2"
            fill={p.score_medio >= 0.75 ? '#10B981' : p.score_medio >= 0.45 ? '#EAB308' : '#EF4444'}
            stroke="#0B0F1A" strokeWidth="0.8" />
        ))}
      </svg>

      {/* Labels embaixo */}
      <div className="flex justify-between mt-1">
        {pts.map((p, i) => (
          <div key={i} className="text-center" style={{ width: `${100 / pts.length}%` }}>
            <p className={`text-xs font-mono font-bold ${scoreColor(p.score_medio)}`}>{round2(p.score_medio)}%</p>
            <p className="text-gray-600 font-mono truncate" style={{ fontSize: '9px' }}>
              {p.filename?.replace('.pdf', '').slice(0, 8)}…
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Página principal ──────────────────────────────────────────────────────────

export default function Analytics() {
  const { overview, produtos, requisitos, evolucao, distribuicao, loading, error, reload } = useAnalytics()
  const [tab, setTab] = useState('produtos')

  if (loading) return (
    <div className="p-8">
      <div className="animate-pulse space-y-4">
        <div className="h-8 bg-slate-border rounded w-48" />
        <div className="grid grid-cols-4 gap-4">
          {[1,2,3,4].map(i => <div key={i} className="h-24 bg-slate-card rounded-xl border border-slate-border" />)}
        </div>
        <div className="grid grid-cols-2 gap-4">
          {[1,2].map(i => <div key={i} className="h-64 bg-slate-card rounded-xl border border-slate-border" />)}
        </div>
      </div>
    </div>
  )

  return (
    <div className="p-8">

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <p className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-1">Inteligência</p>
          <h1 className="font-display font-bold text-3xl text-white">Análise de Produtos</h1>
          <p className="text-gray-400 text-sm mt-1">Performance, gaps e evolução dos matchings</p>
        </div>
        <button onClick={reload} className="btn-ghost text-xs px-3 py-2">↻ Atualizar</button>
      </div>

      {error && (
        <div className="bg-red-dim/30 border border-red-fail/30 rounded-lg px-4 py-3 mb-6">
          <p className="text-sm text-red-fail font-mono">{error}</p>
        </div>
      )}

      {/* ── KPIs ─────────────────────────────────────────────────────────── */}
      {overview && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <KPICard label="Editais" value={overview.total_editais} sub="processados" />
          <KPICard label="Matchings" value={overview.total_matchings} sub="comparações realizadas" />
          <KPICard
            label="Score Médio"
            value={pct(overview.score_medio)}
            sub="de todos os matchings"
            accent={scoreColor(overview.score_medio)}
          />
          <KPICard
            label="Taxa Atendimento"
            value={pct(overview.taxa_atendimento)}
            sub="requisitos atendidos"
            accent={scoreColor(overview.taxa_atendimento)}
          />
        </div>
      )}

      {overview?.melhor_produto && (
        <div className="card mb-8 flex items-center gap-4 border-amber/20 bg-amber/5 animate-fade-up">
          <span className="text-3xl">🏆</span>
          <div>
            <p className="text-xs font-mono text-amber uppercase tracking-widest">Melhor produto</p>
            <p className="font-display font-bold text-xl text-white">{overview.melhor_produto}</p>
            <p className="text-xs text-gray-500 font-mono">maior score médio no período</p>
          </div>
        </div>
      )}

      {/* ── Tabs ─────────────────────────────────────────────────────────── */}
      <div className="flex gap-2 mb-6">
        {[['produtos','Produtos'], ['gaps','Gaps'], ['evolucao','Evolução'], ['distribuicao','Distribuição']].map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-4 py-1.5 rounded-lg text-xs font-mono transition-all duration-150
              ${tab === k ? 'bg-azure text-white' : 'text-gray-400 border border-slate-border hover:text-white'}`}>
            {label}
          </button>
        ))}
      </div>

      {/* ── Tab: Produtos ─────────────────────────────────────────────────── */}
      {tab === 'produtos' && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">

          {/* Ranking por score médio */}
          <div className="card">
            <p className="font-display font-semibold text-white mb-1">Ranking por Score Médio</p>
            <p className="text-xs text-gray-500 font-mono mb-5">ordenado por performance geral</p>
            <div className="space-y-4">
              {produtos.slice(0, 10).map((p, i) => (
                <HBar
                  key={p.produto}
                  label={`${i + 1}. ${p.produto}`}
                  value={p.score_medio}
                  max={1}
                  colorClass={scoreColor(p.score_medio)}
                  sub={`${p.total} matchings · desvio ${round2(p.desvio)}%`}
                  delay={i * 50}
                />
              ))}
              {produtos.length === 0 && <p className="text-xs text-gray-500 font-mono">Nenhum dado ainda.</p>}
            </div>
          </div>

          {/* Cards com donut por produto */}
          <div className="space-y-3">
            <p className="font-display font-semibold text-white mb-1 px-1">Status por Produto</p>
            <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
              {produtos.slice(0, 8).map((p, i) => (
                <div key={p.produto} className="card py-4 flex items-center gap-4 animate-fade-up" style={{ animationDelay: `${i * 60}ms` }}>
                  <DonutChart atende={p.atende} verificar={p.verificar} nao_atende={p.nao_atende} />
                  <div className="flex-1 min-w-0">
                    <p className="font-mono text-sm font-medium text-white truncate mb-2">{p.produto}</p>
                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <p className="text-xs text-gray-500 font-mono">atende</p>
                        <p className="font-display font-bold text-green-match text-sm">{p.atende}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500 font-mono">verificar</p>
                        <p className="font-display font-bold text-yellow-warn text-sm">{p.verificar}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500 font-mono">falhou</p>
                        <p className="font-display font-bold text-red-fail text-sm">{p.nao_atende}</p>
                      </div>
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className={`font-display font-extrabold text-2xl ${scoreColor(p.score_medio)}`}>
                      {round2(p.score_medio)}%
                    </p>
                    <p className="text-xs text-gray-600 font-mono">score</p>
                  </div>
                </div>
              ))}
              {produtos.length === 0 && (
                <div className="card text-center py-10 text-gray-500">
                  <p className="font-mono text-sm">Nenhum dado de matching ainda.</p>
                  <p className="text-xs mt-1">Faça upload de um edital e rode o matching.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Tab: Gaps ─────────────────────────────────────────────────────── */}
      {tab === 'gaps' && (
        <div className="card">
          <p className="font-display font-semibold text-white mb-1">Requisitos Problemáticos</p>
          <p className="text-xs text-gray-500 font-mono mb-5">requisitos que mais produtos não atendem — indica gaps no catálogo</p>

          {requisitos.length === 0 ? (
            <p className="text-xs text-gray-500 font-mono text-center py-8">Nenhum dado ainda.</p>
          ) : (
            <div className="space-y-3">
              {requisitos.slice(0, 15).map((r, i) => (
                <div key={i} className="flex items-center gap-4 py-3 border-b border-slate-border last:border-0 animate-fade-up" style={{ animationDelay: `${i * 40}ms` }}>
                  {/* Ícone de severidade */}
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm flex-shrink-0 ${
                    r.taxa_falha >= 0.7 ? 'bg-red-dim/40 text-red-fail' :
                    r.taxa_falha >= 0.4 ? 'bg-yellow-dim/40 text-yellow-warn' : 'bg-slate-border text-gray-400'
                  }`}>
                    {r.taxa_falha >= 0.7 ? '!' : r.taxa_falha >= 0.4 ? '~' : '✓'}
                  </div>

                  <div className="flex-1 min-w-0">
                    <p className="font-mono text-sm text-white font-medium">{r.requisito}</p>
                    <p className="text-xs text-gray-500 truncate">{r.raw_value}</p>
                    {/* Mini barra de falha */}
                    <div className="mt-1.5 h-1 bg-slate-border rounded-full overflow-hidden w-48">
                      <div
                        className={`h-full rounded-full ${r.taxa_falha >= 0.7 ? 'bg-red-fail' : r.taxa_falha >= 0.4 ? 'bg-yellow-warn' : 'bg-green-match'}`}
                        style={{ width: pct(r.taxa_falha) }}
                      />
                    </div>
                  </div>

                  <div className="text-right flex-shrink-0">
                    <p className={`font-display font-bold text-lg ${r.taxa_falha >= 0.7 ? 'text-red-fail' : r.taxa_falha >= 0.4 ? 'text-yellow-warn' : 'text-green-match'}`}>
                      {pct(r.taxa_falha)}
                    </p>
                    <p className="text-xs text-gray-600 font-mono">taxa de falha</p>
                    <p className="text-xs text-gray-600 font-mono">{r.total} produtos</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Tab: Evolução ─────────────────────────────────────────────────── */}
      {tab === 'evolucao' && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div className="card">
            <p className="font-display font-semibold text-white mb-1">Score por Edital</p>
            <p className="text-xs text-gray-500 font-mono mb-1">evolução cronológica dos resultados</p>
            <EvolucaoChart evolucao={evolucao} />
          </div>

          <div className="card">
            <p className="font-display font-semibold text-white mb-4">Detalhes por Edital</p>
            <div className="space-y-3 max-h-80 overflow-y-auto">
              {evolucao.length === 0 ? (
                <p className="text-xs text-gray-500 font-mono">Nenhum dado ainda.</p>
              ) : evolucao.map((e, i) => (
                <div key={e.edital_id} className="flex items-center gap-3 py-2 border-b border-slate-border last:border-0 animate-fade-up" style={{ animationDelay: `${i * 50}ms` }}>
                  <span className="font-mono text-xs text-gray-500 w-16">#{e.edital_id}</span>
                  <div className="flex-1 min-w-0">
                    <p className="font-mono text-xs text-white truncate">{e.filename}</p>
                    <p className="font-mono text-xs text-gray-600">
                      {e.data ? new Date(e.data).toLocaleDateString('pt-BR') : '—'} · {e.total_resultados} matchings
                    </p>
                  </div>
                  <div className="text-right">
                    <p className={`font-display font-bold ${scoreColor(e.score_medio)}`}>{round2(e.score_medio)}%</p>
                    <p className="text-xs text-gray-600 font-mono">{pct(e.taxa_atendimento)} atendido</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Tab: Distribuição ─────────────────────────────────────────────── */}
      {tab === 'distribuicao' && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div className="card">
            <p className="font-display font-semibold text-white mb-1">Distribuição de Scores</p>
            <p className="text-xs text-gray-500 font-mono mb-1">
              {distribuicao?.total || 0} matchings no total
            </p>
            <Histograma buckets={distribuicao?.buckets} total={distribuicao?.total} />

            {/* Legenda */}
            <div className="flex gap-4 mt-4 pt-3 border-t border-slate-border">
              {[['bg-red-fail/70','Falhou (0–44%)'], ['bg-yellow-warn','Verificar (45–74%)'], ['bg-green-match','Atende (75–100%)']].map(([cls, label]) => (
                <div key={label} className="flex items-center gap-1.5">
                  <div className={`w-2.5 h-2.5 rounded-sm ${cls}`} />
                  <span className="text-xs font-mono text-gray-500">{label}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <p className="font-display font-semibold text-white mb-4">Detalhamento por Faixa</p>
            <div className="space-y-2">
              {(distribuicao?.buckets || []).map((b, i) => (
                <div key={i} className="flex items-center gap-3 animate-fade-up" style={{ animationDelay: `${i * 30}ms` }}>
                  <span className="font-mono text-xs text-gray-500 w-20">{b.faixa}</span>
                  <div className="flex-1 h-4 bg-slate-border rounded overflow-hidden">
                    <div
                      className={`h-full rounded transition-all duration-700 ${bucketColor(i)}`}
                      style={{ width: `${Math.round(b.pct * 100)}%` }}
                    />
                  </div>
                  <span className="font-mono text-xs text-white w-8 text-right">{b.count}</span>
                  <span className="font-mono text-xs text-gray-500 w-10">{Math.round(b.pct * 100)}%</span>
                </div>
              ))}
              {!distribuicao?.buckets?.length && (
                <p className="text-xs text-gray-500 font-mono text-center py-8">Nenhum dado ainda.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
