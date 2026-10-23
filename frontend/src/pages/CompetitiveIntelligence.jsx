import { useEffect, useMemo, useState } from 'react'
import { datasheetsApi } from '../api/client'
import { useToast } from '../contexts/ToastContext'

function formatCurrency(value) {
  const number = Number(value)
  if (!Number.isFinite(number) || number <= 0) return '—'
  return number.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function scoreColor(score) {
  if (score >= 70) return 'text-emerald-600 dark:text-emerald-400'
  if (score >= 45) return 'text-amber-600 dark:text-amber-400'
  return 'text-red-600 dark:text-red-400'
}

function scoreBg(score) {
  if (score >= 70) return 'bg-emerald-500'
  if (score >= 45) return 'bg-amber-400'
  return 'bg-red-500'
}

function SectionLabel({ number, children }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs font-semibold tabular-nums text-slate-400 dark:text-slate-500">{String(number).padStart(2, '0')}</span>
      <span className="h-px flex-1 max-w-6 bg-slate-200 dark:bg-slate-700" />
      <span className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">{children}</span>
    </div>
  )
}

function StatBox({ label, value, accent }) {
  return (
    <div className="flex flex-col gap-1">
      <p className={`text-4xl font-bold tabular-nums leading-none tracking-tight ${accent || 'text-slate-950 dark:text-white'}`}>{value}</p>
      <p className="text-sm text-slate-500 dark:text-slate-400">{label}</p>
    </div>
  )
}

function CompetitorCard({ row }) {
  const { competitor, history = {}, best_own_counters = [], risk_summary } = row
  const [expanded, setExpanded] = useState(false)

  return (
    <article className="rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
      {/* Cabeçalho sempre visível */}
      <button
        type="button"
        onClick={() => setExpanded(v => !v)}
        className="flex w-full items-start gap-4 p-5 text-left"
      >
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
            {competitor.manufacturer || 'Fabricante não informado'}
          </p>
          <h3 className="mt-0.5 text-lg font-semibold text-slate-950 dark:text-white">{competitor.model}</h3>
          <p className="text-sm text-slate-500 dark:text-slate-400">{competitor.category || 'Categoria não informada'}</p>
        </div>
        <div className="flex-shrink-0 text-right">
          <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
            {history.occurrences > 0 && (
              <div className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800">
                <p className="text-slate-500 dark:text-slate-400">Histórico</p>
                <p className="mt-1 text-base font-bold text-slate-950 dark:text-white">{history.occurrences}</p>
              </div>
            )}
            {history.avg_unit_price > 0 && (
              <div className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800">
                <p className="text-slate-500 dark:text-slate-400">Preço médio</p>
                <p className="mt-1 text-sm font-bold text-slate-950 dark:text-white">{formatCurrency(history.avg_unit_price)}</p>
              </div>
            )}
            {history.min_unit_price > 0 && (
              <div className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800">
                <p className="text-slate-500 dark:text-slate-400">Menor preço</p>
                <p className="mt-1 text-sm font-bold text-slate-950 dark:text-white">{formatCurrency(history.min_unit_price)}</p>
              </div>
            )}
          </div>
        </div>
        <span className="mt-1 ml-2 flex-shrink-0 text-slate-400 text-lg">{expanded ? '↑' : '↓'}</span>
      </button>

      {/* Risco — sempre visível se existir */}
      {risk_summary && (
        <div className="mx-5 mb-3 rounded-lg border border-blue-100 bg-blue-50 px-4 py-2.5 text-sm text-blue-800 dark:border-blue-900 dark:bg-blue-950/30 dark:text-blue-200">
          {risk_summary}
        </div>
      )}

      {/* Detalhes expandíveis */}
      {expanded && best_own_counters.length > 0 && (
        <div className="border-t border-slate-100 p-5 dark:border-slate-800">
          <p className="mb-3 text-xs font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
            Seus melhores contrapontos
          </p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {best_own_counters.map(counter => (
              <div key={counter.product_id} className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-slate-950 dark:text-white">{counter.model}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{counter.category || '—'}</p>
                  </div>
                  <p className={`text-xl font-bold flex-shrink-0 ${scoreColor(counter.score)}`}>{counter.score}</p>
                </div>
                {/* Mini placar */}
                <div className="mt-2 flex gap-2 text-xs">
                  <span className="rounded bg-emerald-100 px-2 py-0.5 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">+{counter.advantages}</span>
                  <span className="rounded bg-red-100 px-2 py-0.5 text-red-700 dark:bg-red-950/40 dark:text-red-300">−{counter.disadvantages}</span>
                  <span className="rounded bg-slate-200 px-2 py-0.5 text-slate-600 dark:bg-slate-700 dark:text-slate-400">={counter.ties}</span>
                </div>
                {counter.key_edges?.length > 0 && (
                  <p className="mt-2 text-xs text-slate-600 dark:text-slate-300 leading-5">
                    ✓ {counter.key_edges.slice(0, 2).join(' · ')}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Fornecedores históricos */}
      {expanded && history.suppliers?.length > 0 && (
        <div className="border-t border-slate-100 px-5 pb-4 pt-3 dark:border-slate-800">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Fornecedores históricos: <span className="text-slate-700 dark:text-slate-300">{history.suppliers.join(', ')}</span>
          </p>
        </div>
      )}
    </article>
  )
}

export default function CompetitiveIntelligence() {
  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(true)
  const [category, setCategory] = useState('')
  const { toast } = useToast()

  const categories = useMemo(() => {
    const values = new Set()
    ;(payload?.competitors || []).forEach(row => {
      if (row.competitor?.category) values.add(row.competitor.category)
    })
    return [...values].sort()
  }, [payload])

  const load = async () => {
    setLoading(true)
    try {
      const response = await datasheetsApi.competitiveIntelligence({ category: category || undefined })
      setPayload(response.data)
    } catch (err) {
      toast({
        type: 'error',
        title: 'Inteligência indisponível',
        message: err.response?.data?.detail || 'Não foi possível carregar a inteligência competitiva.',
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const summary = payload?.summary || {}
  const competitors = payload?.competitors || []
  const manufacturers = payload?.manufacturers || []
  const globalGaps = payload?.global_gaps || []

  const hasData = competitors.length > 0

  return (
    <div className="mx-auto max-w-4xl space-y-12 p-6 lg:p-8">

      {/* ── Cabeçalho ─────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">Inteligência comercial</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 dark:text-white">Análise Competitiva</h1>
          <p className="mt-2 text-base text-slate-600 dark:text-slate-400">
            {hasData
              ? `${summary.competitor_products || 0} concorrentes monitorados de ${summary.manufacturers || 0} fabricantes.`
              : 'Importe datasheets de concorrentes para ativar este painel.'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {categories.length > 0 && (
            <select
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
              value={category}
              onChange={e => setCategory(e.target.value)}
            >
              <option value="">Todas as categorias</option>
              {categories.map(item => <option key={item} value={item}>{item}</option>)}
            </select>
          )}
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
          >
            {loading ? 'Carregando...' : '↻ Atualizar'}
          </button>
        </div>
      </div>

      {!hasData && !loading && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center dark:border-slate-700 dark:bg-slate-900">
          <p className="text-lg font-semibold text-slate-950 dark:text-white">Nenhum concorrente importado</p>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            Importe datasheets de concorrentes na tela de Datasheets para alimentar este painel.
          </p>
        </div>
      )}

      {loading && (
        <div className="space-y-4">
          {[1, 2, 3].map(i => <div key={i} className="h-24 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />)}
        </div>
      )}

      {hasData && !loading && (
        <>
          {/* ── 01 · Panorama do mercado ────────────────────────────────── */}
          <section className="space-y-5">
            <SectionLabel number={1}>Panorama do mercado</SectionLabel>
            <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
              <StatBox label="Seus produtos" value={summary.own_products ?? '—'} />
              <StatBox label="Concorrentes" value={summary.competitor_products ?? '—'} />
              <StatBox label="Fabricantes" value={summary.manufacturers ?? '—'} />
              <StatBox label="Histórico indexado" value={summary.history_items_indexed ?? '—'} />
            </div>
          </section>

          {/* ── 02 · Fabricantes e lacunas ─────────────────────────────── */}
          {(manufacturers.length > 0 || globalGaps.length > 0) && (
            <section className="space-y-5">
              <SectionLabel number={2}>Mercado em números</SectionLabel>
              <div className="grid gap-5 sm:grid-cols-2">
                {manufacturers.length > 0 && (
                  <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
                    <p className="mb-4 text-sm font-semibold text-slate-950 dark:text-white">Fabricantes mais presentes</p>
                    <div className="space-y-3">
                      {manufacturers.slice(0, 6).map(item => (
                        <div key={item.manufacturer} className="flex items-center gap-3">
                          <div className="flex-1 min-w-0">
                            <p className="truncate text-sm text-slate-700 dark:text-slate-300">{item.manufacturer}</p>
                          </div>
                          <span className="text-sm font-semibold text-slate-950 dark:text-white">{item.products} prod.</span>
                          {item.history_hits > 0 && (
                            <span className="text-xs text-slate-400 dark:text-slate-500">{item.history_hits} licitações</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {globalGaps.length > 0 && (
                  <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
                    <p className="mb-4 text-sm font-semibold text-slate-950 dark:text-white">Lacunas mais recorrentes</p>
                    <div className="space-y-3">
                      {globalGaps.slice(0, 6).map(gap => (
                        <div key={gap.field} className="flex items-center gap-3">
                          <div className="flex-1 min-w-0">
                            <p className="truncate text-sm text-slate-700 dark:text-slate-300" title={gap.field}>{gap.field}</p>
                          </div>
                          <span className="flex-shrink-0 text-sm font-bold text-amber-600 dark:text-amber-400">{gap.count}×</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </section>
          )}

          {/* ── 03 · Concorrentes ──────────────────────────────────────── */}
          <section className="space-y-5">
            <SectionLabel number={3}>Concorrentes detalhados</SectionLabel>
            <p className="text-base text-slate-600 dark:text-slate-400">
              Clique em cada concorrente para ver os melhores contrapontos do seu catálogo.
            </p>
            <div className="space-y-3">
              {competitors.map(row => (
                <CompetitorCard key={row.competitor.id} row={row} />
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  )
}
