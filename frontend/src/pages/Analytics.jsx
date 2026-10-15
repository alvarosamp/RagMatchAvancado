/**
 * pages/Analytics.jsx — Inteligência de Produtos
 * Narrativa por seção: overview → melhor produto → gaps → distribuição → evolução
 */

import { useEffect, useState, useCallback } from 'react'
import api from '../api/client'
import { formatBrasiliaDate } from '../utils/datetime'

// ── Dados ────────────────────────────────────────────────────────────────────

function useAnalytics() {
  const [data, setData] = useState({ overview: null, produtos: [], requisitos: [], evolucao: [], distribuicao: null })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

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
    } catch {
      setError('Erro ao carregar dados de análise.')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])
  return { ...data, loading, error, reload: load }
}

// ── Utilitários ──────────────────────────────────────────────────────────────

const pct = (v) => `${Math.round((v || 0) * 100)}%`
const round2 = (v) => ((v || 0) * 100).toFixed(1)

function scoreColor(score) {
  if (score >= 0.75) return 'text-emerald-600 dark:text-emerald-400'
  if (score >= 0.45) return 'text-amber-600 dark:text-amber-400'
  return 'text-red-600 dark:text-red-400'
}

function scoreBg(score) {
  if (score >= 0.75) return 'bg-emerald-500'
  if (score >= 0.45) return 'bg-amber-400'
  return 'bg-red-500'
}

// ── Componentes ──────────────────────────────────────────────────────────────

function SectionLabel({ number, children }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs font-semibold tabular-nums text-slate-400 dark:text-slate-500">{String(number).padStart(2, '0')}</span>
      <span className="h-px flex-1 max-w-6 bg-slate-200 dark:bg-slate-700" />
      <span className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">{children}</span>
    </div>
  )
}

function BigNumber({ value, label, accent, sub }) {
  return (
    <div className="flex flex-col gap-1">
      <p className={`text-5xl font-bold tabular-nums leading-none tracking-tight ${accent || 'text-slate-950 dark:text-white'}`}>{value}</p>
      <p className="text-sm font-medium text-slate-700 dark:text-slate-300">{label}</p>
      {sub && <p className="text-xs text-slate-500 dark:text-slate-400">{sub}</p>}
    </div>
  )
}

function BarRow({ label, value, max, score, delay = 0 }) {
  const width = max > 0 ? (value / max) * 100 : 0
  return (
    <div className="animate-fade-up" style={{ animationDelay: `${delay}ms` }}>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-sm text-slate-700 dark:text-slate-300 truncate max-w-[220px]">{label}</span>
        <span className={`text-sm font-bold tabular-nums ${scoreColor(score)}`}>{round2(score)}%</span>
      </div>
      <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${scoreBg(score)}`}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  )
}

function GapRow({ requisito, taxa_falha, raw_value, total, index }) {
  const severity = taxa_falha >= 0.7 ? 'alta' : taxa_falha >= 0.4 ? 'media' : 'baixa'
  const colors = { alta: 'text-red-600 dark:text-red-400', media: 'text-amber-600 dark:text-amber-400', baixa: 'text-slate-600 dark:text-slate-400' }
  const bg = { alta: 'bg-red-500', media: 'bg-amber-400', baixa: 'bg-slate-300 dark:bg-slate-600' }

  return (
    <div className="flex items-start gap-4 py-4 border-b border-slate-100 dark:border-slate-800 last:border-0 animate-fade-up" style={{ animationDelay: `${index * 40}ms` }}>
      <span className="mt-0.5 w-6 text-xs font-bold tabular-nums text-slate-400 dark:text-slate-500">{index + 1}</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-950 dark:text-white">{requisito}</p>
        {raw_value && <p className="text-xs text-slate-500 dark:text-slate-400 truncate mt-0.5">{raw_value}</p>}
        <div className="mt-2 h-1.5 rounded-full bg-slate-100 dark:bg-slate-800 w-40 overflow-hidden">
          <div className={`h-full rounded-full ${bg[severity]}`} style={{ width: pct(taxa_falha) }} />
        </div>
      </div>
      <div className="text-right flex-shrink-0">
        <p className={`text-lg font-bold tabular-nums ${colors[severity]}`}>{pct(taxa_falha)}</p>
        <p className="text-[11px] text-slate-400 dark:text-slate-500">{total} produtos</p>
      </div>
    </div>
  )
}

function HistBar({ b, i, maxCount }) {
  const height = maxCount > 0 ? Math.max((b.count / maxCount) * 100, b.count > 0 ? 6 : 0) : 0
  const color = i >= 7 ? 'bg-emerald-500' : i >= 4 ? 'bg-amber-400' : 'bg-red-500'
  return (
    <div className="group flex flex-1 flex-col items-center gap-1">
      <div className="relative flex flex-col justify-end w-full" style={{ height: 80 }}>
        <div className="absolute -top-7 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-slate-900 px-2 py-1 text-[11px] text-white opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
          {b.count} ({Math.round(b.pct * 100)}%)
        </div>
        <div className={`w-full rounded-t ${color} transition-all duration-700`} style={{ height: `${height}%` }} />
      </div>
      <span className="text-[10px] text-slate-400 dark:text-slate-500">{b.faixa.split('-')[0]}</span>
    </div>
  )
}

function EvolucaoPoint({ e, score, maxScore, index, total }) {
  const x = total === 1 ? 50 : (index / (total - 1)) * 90 + 5
  const y = 95 - (score / maxScore) * 85
  return { x, y, score, ...e }
}

// ── Página ───────────────────────────────────────────────────────────────────

export default function Analytics() {
  const { overview, produtos, requisitos, evolucao, distribuicao, loading, error, reload } = useAnalytics()

  if (loading) return (
    <div className="mx-auto max-w-4xl space-y-6 p-8">
      {[1, 2, 3].map(i => <div key={i} className="h-32 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />)}
    </div>
  )

  const hasData = overview && (overview.total_editais > 0 || overview.total_matchings > 0)

  // Evolução como sparkline
  const pts = evolucao.map((e, i) => ({
    x: evolucao.length === 1 ? 50 : (i / (evolucao.length - 1)) * 90 + 5,
    y: 95 - (e.score_medio / 1) * 85,
    ...e,
  }))
  const pathD = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')

  const buckets = distribuicao?.buckets || []
  const maxCount = Math.max(...buckets.map(b => b.count), 1)

  return (
    <div className="mx-auto max-w-4xl space-y-12 p-6 lg:p-8">

      {/* ── Cabeçalho ─────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">Inteligência</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 dark:text-white">Performance de Produtos</h1>
          <p className="mt-2 text-base text-slate-600 dark:text-slate-400">
            {hasData
              ? `${overview.total_editais} edital${overview.total_editais > 1 ? 'is' : ''} analisado${overview.total_editais > 1 ? 's' : ''}, ${overview.total_matchings.toLocaleString('pt-BR')} comparações realizadas.`
              : 'Analise editais para visualizar performance do catálogo.'}
          </p>
        </div>
        <button onClick={reload} className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700">
          ↻ Atualizar
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/30 dark:text-red-300">
          {error}
        </div>
      )}

      {!hasData && !error && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center dark:border-slate-700 dark:bg-slate-900">
          <p className="text-lg font-semibold text-slate-950 dark:text-white">Nenhum dado de matching ainda</p>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">Envie um edital e rode o matching para ver a performance do seu catálogo aqui.</p>
        </div>
      )}

      {hasData && (
        <>
          {/* ── 01 · Resultado geral ──────────────────────────────────────── */}
          <section className="space-y-5">
            <SectionLabel number={1}>Resultado geral</SectionLabel>
            <div className="grid gap-6 sm:grid-cols-4">
              <BigNumber value={overview.total_editais} label="Editais" sub="analisados" />
              <BigNumber value={overview.total_matchings.toLocaleString('pt-BR')} label="Comparações" sub="realizadas" />
              <BigNumber
                value={pct(overview.score_medio)}
                label="Score médio"
                accent={scoreColor(overview.score_medio)}
              />
              <BigNumber
                value={pct(overview.taxa_atendimento)}
                label="Requisitos atendidos"
                accent={scoreColor(overview.taxa_atendimento)}
              />
            </div>

            {overview.melhor_produto && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-5 py-4 dark:border-amber-800 dark:bg-amber-950/20">
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-amber-600 dark:text-amber-400">🏆 Melhor produto no período</p>
                <p className="mt-1 text-xl font-bold text-slate-950 dark:text-white">{overview.melhor_produto}</p>
                <p className="text-sm text-amber-700 dark:text-amber-300">maior score médio entre todas as comparações</p>
              </div>
            )}
          </section>

          {/* ── 02 · Ranking de produtos ──────────────────────────────────── */}
          {produtos.length > 0 && (
            <section className="space-y-5">
              <SectionLabel number={2}>Ranking por performance</SectionLabel>
              <p className="text-base text-slate-600 dark:text-slate-400">
                Os produtos com maior score médio nos editais analisados. Quanto mais alto, mais vezes atendeu os requisitos.
              </p>
              <div className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900 space-y-5">
                {produtos.slice(0, 8).map((p, i) => (
                  <BarRow
                    key={p.produto}
                    label={`${i + 1}. ${p.produto}`}
                    value={p.score_medio}
                    max={1}
                    score={p.score_medio}
                    delay={i * 50}
                  />
                ))}
              </div>
            </section>
          )}

          {/* ── 03 · Gaps de catálogo ─────────────────────────────────────── */}
          {requisitos.length > 0 && (
            <section className="space-y-5">
              <SectionLabel number={3}>Onde o catálogo falha</SectionLabel>
              <p className="text-base text-slate-600 dark:text-slate-400">
                Requisitos que mais produtos não conseguem atender. São os pontos onde o catálogo precisa evoluir.
              </p>
              <div className="rounded-xl border border-slate-200 bg-white px-6 dark:border-slate-700 dark:bg-slate-900">
                {requisitos.slice(0, 10).map((r, i) => (
                  <GapRow key={i} {...r} index={i} />
                ))}
              </div>
            </section>
          )}

          {/* ── 04 · Distribuição de scores ───────────────────────────────── */}
          {buckets.length > 0 && (
            <section className="space-y-5">
              <SectionLabel number={4}>Distribuição de scores</SectionLabel>
              <p className="text-base text-slate-600 dark:text-slate-400">
                {distribuicao?.total?.toLocaleString('pt-BR') || 0} comparações distribuídas por faixa de performance.
              </p>
              <div className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900">
                <div className="flex items-end gap-1.5 h-24 mt-4">
                  {buckets.map((b, i) => (
                    <HistBar key={i} b={b} i={i} maxCount={maxCount} />
                  ))}
                </div>
                <div className="flex gap-5 mt-5 pt-4 border-t border-slate-100 dark:border-slate-800">
                  {[['bg-red-500', 'Falhou (0–44%)'], ['bg-amber-400', 'Verificar (45–74%)'], ['bg-emerald-500', 'Atende (75–100%)']].map(([cls, label]) => (
                    <div key={label} className="flex items-center gap-2">
                      <div className={`h-2.5 w-2.5 rounded-sm ${cls}`} />
                      <span className="text-xs text-slate-500 dark:text-slate-400">{label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          )}

          {/* ── 05 · Evolução ─────────────────────────────────────────────── */}
          {evolucao.length > 0 && (
            <section className="space-y-5">
              <SectionLabel number={5}>Evolução por edital</SectionLabel>
              <p className="text-base text-slate-600 dark:text-slate-400">
                Como o score médio variou ao longo dos editais analisados em ordem cronológica.
              </p>
              <div className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900">
                <svg viewBox="0 0 100 100" className="w-full h-40" preserveAspectRatio="none">
                  {[25, 50, 75].map(y => (
                    <line key={y} x1="0" y1={y} x2="100" y2={y} stroke="#e2e8f0" strokeWidth="0.5" />
                  ))}
                  <path d={`${pathD} L ${pts[pts.length - 1].x} 100 L ${pts[0].x} 100 Z`} fill="rgba(59,130,246,0.08)" />
                  <path d={pathD} fill="none" stroke="#3B82F6" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  {pts.map((p, i) => (
                    <circle key={i} cx={p.x} cy={p.y} r="2.5"
                      fill={p.score_medio >= 0.75 ? '#10B981' : p.score_medio >= 0.45 ? '#F59E0B' : '#EF4444'}
                      stroke="white" strokeWidth="1" />
                  ))}
                </svg>
                <div className="mt-4 grid gap-2 border-t border-slate-100 dark:border-slate-800 pt-4">
                  {evolucao.slice(0, 6).map((e, i) => (
                    <div key={e.edital_id} className="flex items-center gap-3">
                      <span className="text-xs text-slate-400 dark:text-slate-500 w-16 flex-shrink-0">{formatBrasiliaDate(e.data)}</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs text-slate-700 dark:text-slate-300 truncate">{e.filename}</p>
                      </div>
                      <span className={`text-sm font-bold tabular-nums flex-shrink-0 ${scoreColor(e.score_medio)}`}>{round2(e.score_medio)}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}
