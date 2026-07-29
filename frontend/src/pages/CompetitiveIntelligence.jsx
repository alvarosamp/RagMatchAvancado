import { useEffect, useMemo, useState } from 'react'
import { datasheetsApi } from '../api/client'
import { useToast } from '../contexts/ToastContext'

function formatCurrency(value) {
  const number = Number(value)
  if (!Number.isFinite(number) || number <= 0) return '-'
  return number.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function scoreClass(score) {
  if (score >= 70) return 'text-emerald-600 dark:text-emerald-300'
  if (score >= 45) return 'text-amber-600 dark:text-amber-300'
  return 'text-red-600 dark:text-red-300'
}

function CounterProduct({ counter }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-800">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-950 dark:text-white">{counter.model}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">{counter.category || 'Categoria nao informada'}</p>
        </div>
        <p className={`text-xl font-bold ${scoreClass(counter.score)}`}>{counter.score}</p>
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2 text-center text-xs">
        <span className="rounded bg-emerald-50 px-2 py-1 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300">{counter.advantages} vantagens</span>
        <span className="rounded bg-red-50 px-2 py-1 text-red-700 dark:bg-red-950/30 dark:text-red-300">{counter.disadvantages} perdas</span>
        <span className="rounded bg-slate-100 px-2 py-1 text-slate-600 dark:bg-slate-900 dark:text-slate-300">{counter.ties} empates</span>
      </div>
      {!!counter.key_edges?.length && (
        <p className="mt-2 text-xs leading-5 text-slate-600 dark:text-slate-300">
          Vantagens: {counter.key_edges.join(', ')}
        </p>
      )}
      {!!counter.vulnerabilities?.length && (
        <p className="mt-1 text-xs leading-5 text-amber-700 dark:text-amber-300">
          Lacunas: {counter.vulnerabilities.join(', ')}
        </p>
      )}
    </div>
  )
}

function CompetitorCard({ row }) {
  const competitor = row.competitor
  const history = row.history || {}
  return (
    <article className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {competitor.manufacturer || 'Fabricante nao informado'}
          </p>
          <h2 className="mt-1 text-lg font-semibold text-slate-950 dark:text-white">{competitor.model}</h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{competitor.category || 'Categoria nao informada'}</p>
        </div>
        <div className="grid grid-cols-2 gap-2 text-right text-xs sm:grid-cols-4 lg:min-w-[460px]">
          <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-900">
            <p className="text-slate-500 dark:text-slate-400">Historico</p>
            <p className="mt-1 text-lg font-bold text-slate-950 dark:text-white">{history.occurrences || 0}</p>
          </div>
          <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-900">
            <p className="text-slate-500 dark:text-slate-400">Preco medio</p>
            <p className="mt-1 text-sm font-bold text-slate-950 dark:text-white">{formatCurrency(history.avg_unit_price)}</p>
          </div>
          <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-900">
            <p className="text-slate-500 dark:text-slate-400">Menor preco</p>
            <p className="mt-1 text-sm font-bold text-slate-950 dark:text-white">{formatCurrency(history.min_unit_price)}</p>
          </div>
          <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-900">
            <p className="text-slate-500 dark:text-slate-400">Valor hist.</p>
            <p className="mt-1 text-sm font-bold text-slate-950 dark:text-white">{formatCurrency(history.estimated_total_value)}</p>
          </div>
        </div>
      </div>

      <p className="mt-4 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-800 dark:border-blue-900 dark:bg-blue-950/30 dark:text-blue-200">
        {row.risk_summary}
      </p>

      {!!history.suppliers?.length && (
        <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">Fornecedores historicos: {history.suppliers.join(', ')}</p>
      )}

      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        {(row.best_own_counters || []).map((counter) => (
          <CounterProduct key={counter.product_id} counter={counter} />
        ))}
      </div>
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
    ;(payload?.competitors || []).forEach((row) => {
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
        title: 'Inteligencia indisponivel',
        message: err.response?.data?.detail || 'Nao foi possivel carregar a inteligencia competitiva.',
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <div className="min-h-screen space-y-6 p-6 lg:p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">Inteligencia comercial</p>
          <h1 className="mt-2 text-2xl font-bold text-slate-950 dark:text-white">Inteligencia competitiva</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600 dark:text-slate-300">
            Consolida datasheets concorrentes, historico de itens e contrapontos do seu catalogo para preparar proximos editais.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select className="input w-56" value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="">Todas as categorias</option>
            {categories.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <button type="button" onClick={load} disabled={loading} className="btn-primary">
            {loading ? 'Atualizando...' : 'Atualizar'}
          </button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        {[
          ['Seus produtos', payload?.summary?.own_products ?? '-'],
          ['Concorrentes', payload?.summary?.competitor_products ?? '-'],
          ['Fabricantes', payload?.summary?.manufacturers ?? '-'],
          ['Historico indexado', payload?.summary?.history_items_indexed ?? '-'],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
            <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
            <p className="mt-1 text-2xl font-bold text-slate-950 dark:text-white">{loading ? '-' : value}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <section className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-800">
          <h2 className="text-base font-semibold text-slate-950 dark:text-white">Fabricantes monitorados</h2>
          <div className="mt-4 space-y-3">
            {(payload?.manufacturers || []).slice(0, 8).map((item) => (
              <div key={item.manufacturer} className="grid grid-cols-[1fr_72px_92px] items-center gap-3 text-sm">
                <span className="truncate text-slate-700 dark:text-slate-300">{item.manufacturer}</span>
                <span className="text-right font-semibold text-slate-950 dark:text-white">{item.products} prod.</span>
                <span className="text-right text-slate-500 dark:text-slate-400">{item.history_hits} hist.</span>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-800">
          <h2 className="text-base font-semibold text-slate-950 dark:text-white">Lacunas recorrentes</h2>
          <div className="mt-4 space-y-3">
            {(payload?.global_gaps || []).map((gap) => (
              <div key={gap.field} className="grid grid-cols-[1fr_56px] items-center gap-3 text-sm">
                <span className="truncate text-slate-700 dark:text-slate-300" title={gap.field}>{gap.field}</span>
                <span className="text-right font-semibold text-amber-700 dark:text-amber-300">{gap.count}x</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="space-y-4">
        {(payload?.competitors || []).map((row) => (
          <CompetitorCard key={row.competitor.id} row={row} />
        ))}
      </div>

      {!loading && !payload?.competitors?.length && (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center dark:border-slate-700 dark:bg-slate-800">
          <h2 className="text-lg font-semibold text-slate-950 dark:text-white">Nenhum concorrente importado</h2>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            Importe datasheets de concorrentes na tela de Datasheets para alimentar este painel.
          </p>
        </div>
      )}
    </div>
  )
}
