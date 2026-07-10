import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { analysisApi } from '../api/client'
import { formatNumber, formatMoney, compactDescription } from '../components/ui/format'
import StatCard from '../components/ui/StatCard'
import Card from '../components/ui/Card'
import Badge, { categoryTone, riskTone } from '../components/ui/Badge'
import { BreakdownGroup } from '../components/ui/MetricBar'

const PERIODS = [
  { key: 'day', label: 'Diario' },
  { key: 'week', label: 'Semanal' },
  { key: 'month', label: 'Mensal' },
  { key: 'year', label: 'Anual' },
]

const POLL_MS = 20_000

function normalizeRisk(value) {
  return value && value !== 'Nenhum' ? 'Risco' : 'Sem risco'
}

function itemCategorization(item) {
  const bi = item.caracteristicas_bi || {}
  const fields = [
    bi.quantidade_portas,
    bi.gerenciamento,
    bi.alimentacao_poe || bi.alimentacao,
    bi.portas_acesso,
    bi.uplinks,
    bi.tecnologia_wifi,
    bi.ambiente,
    bi.formato,
    bi.tipo_meio,
  ].filter(Boolean)
  return fields.length ? fields.join(' / ') : item.categoria || '-'
}

function CategoryPanel({ category }) {
  const breakdownEntries = Object.entries(category.breakdowns || {})
  const primaryRows = breakdownEntries.slice(0, 3)
  const ufRows = (category.ufs || []).map((row) => ({ valor: row.uf, unidades: row.unidades }))

  return (
    <Card className="p-6">
      <div className="mb-5 flex flex-col gap-4 border-b border-slate-100 pb-4 dark:border-slate-700 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h3 className="text-xl font-semibold text-slate-950 dark:text-white">{category.categoria}</h3>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Resumo comercial por classificacao e volume.</p>
        </div>
        <div className="grid grid-cols-3 gap-6 text-right">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Itens</p>
            <p className="text-lg font-semibold text-slate-950 dark:text-white">{formatNumber(category.itens)}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Unidades</p>
            <p className="text-lg font-semibold text-slate-950 dark:text-white">{formatNumber(category.unidades)}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Valor</p>
            <p className="text-lg font-semibold text-slate-950 dark:text-white">{formatMoney(category.valor_mapeado)}</p>
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        {primaryRows.map(([field, rows]) => (
          <BreakdownGroup key={field} title={field.replace(/_/g, ' ')} rows={rows} />
        ))}
        <BreakdownGroup title="UFs com mais unidades" rows={ufRows} />
      </div>
    </Card>
  )
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
      setError(err.response?.data?.detail || 'Erro ao carregar o painel.')
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
  const selectedPeriod = PERIODS.find((item) => item.key === period)?.label || 'Mensal'

  const categoryRows = useMemo(() => categories.slice(0, 3), [categories])
  const recentRows = useMemo(() => editais.slice(0, 12), [editais])

  return (
    <div className="min-h-screen bg-surface p-6 text-slate-950 dark:bg-surface-dark dark:text-white lg:p-8">
      <div className="mx-auto max-w-[1480px] space-y-8">
        <header className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">Business Intelligence</p>
            <h1 className="mt-2 text-4xl font-bold tracking-tight text-slate-950 dark:text-white">Editais</h1>
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
              {lastUpdated ? `Atualizado as ${lastUpdated.toLocaleTimeString('pt-BR')}` : 'Carregando dados'} · atualizacao automatica a cada 20s
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex rounded-lg bg-slate-100 p-1 dark:bg-slate-800">
              {PERIODS.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setPeriod(item.key)}
                  className={`rounded-md px-5 py-2 text-sm font-medium transition-colors ${
                    period === item.key
                      ? 'bg-brand text-white dark:bg-brand-light'
                      : 'text-slate-600 hover:text-slate-950 dark:text-slate-400 dark:hover:text-white'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => fetchAll(true)}
              className="rounded-lg border border-slate-300 bg-white px-5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
            >
              Atualizar
            </button>
            <button
              type="button"
              onClick={() => navigate('/upload')}
              className="rounded-lg bg-brand px-5 py-2 text-sm font-medium text-white hover:bg-brand-dark dark:bg-brand-light dark:hover:bg-brand"
            >
              Enviar edital
            </button>
          </div>
        </header>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300">
            {error}
          </div>
        )}

        {loading ? (
          <div className="space-y-4">
            {[...Array(5)].map((_, index) => (
              <div key={index} className="h-20 animate-pulse rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800" />
            ))}
          </div>
        ) : (
          <>
            <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-5">
              <StatCard label="Editais selecionados" value={formatNumber(kpis.editais_selecionados)} />
              <StatCard label="Itens mapeados" value={formatNumber(kpis.itens_categorizados)} />
              <StatCard label="Unidades mapeadas" value={formatNumber(kpis.unidades_mapeadas)} />
              <StatCard label="Editais com risco" value={formatNumber(kpis.editais_com_risco)} danger />
              <StatCard label="Com ME/EPP" value={formatNumber(kpis.editais_com_me_epp)} />
            </section>

            <section className="space-y-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-slate-950 dark:text-white">Por categoria de equipamento</h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400">{selectedPeriod} · principais familias mapeadas</p>
                </div>
              </div>
              <div className="grid gap-5 xl:grid-cols-2">
                {categoryRows.length === 0 ? (
                  <Card className="p-8 text-center text-sm text-slate-500 dark:text-slate-400">
                    Nenhuma analise importada no periodo selecionado.
                  </Card>
                ) : (
                  categoryRows.map((category) => <CategoryPanel key={category.categoria} category={category} />)
                )}
              </div>
            </section>

            <section className="space-y-4">
              <div className="flex items-center justify-between gap-4">
                <h2 className="text-lg font-semibold text-slate-950 dark:text-white">Editais recentes</h2>
                <button
                  type="button"
                  onClick={() => navigate('/upload')}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
                >
                  Novo envio
                </button>
              </div>
              <Card className="overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[980px] text-left">
                    <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
                      <tr>
                        <th className="px-5 py-4 font-semibold">Edital</th>
                        <th className="px-5 py-4 font-semibold">Orgao</th>
                        <th className="px-5 py-4 font-semibold">UF</th>
                        <th className="px-5 py-4 font-semibold">Disputa</th>
                        <th className="px-5 py-4 font-semibold">Itens</th>
                        <th className="px-5 py-4 font-semibold">Categorias</th>
                        <th className="px-5 py-4 font-semibold">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                      {recentRows.length === 0 ? (
                        <tr>
                          <td className="px-5 py-8 text-center text-sm text-slate-500 dark:text-slate-400" colSpan={7}>
                            Nenhum edital importado ainda.
                          </td>
                        </tr>
                      ) : (
                        recentRows.map((edital) => {
                          const categoriesFound = Array.from(new Set((edital.items || []).map((item) => item.categoria).filter(Boolean)))
                          return (
                            <tr
                              key={edital.id}
                              className="cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700/50"
                              onClick={() => navigate(`/analise/documentos/${edital.id}`)}
                            >
                              <td className="px-5 py-4">
                                <p className="font-semibold text-slate-950 dark:text-white">{edital.numero_pregao || edital.source_name || '-'}</p>
                              </td>
                              <td className="px-5 py-4 text-sm text-slate-700 dark:text-slate-300">{compactDescription(edital.orgao, 64) || '-'}</td>
                              <td className="px-5 py-4 text-sm text-slate-700 dark:text-slate-300">{edital.uf || '-'}</td>
                              <td className="px-5 py-4 text-sm text-slate-700 dark:text-slate-300">{edital.data_disputa || '-'}</td>
                              <td className="px-5 py-4 text-sm text-slate-700 dark:text-slate-300">{formatNumber(edital.items?.length)}</td>
                              <td className="px-5 py-4">
                                <div className="flex flex-wrap gap-1.5">
                                  {categoriesFound.length === 0 ? (
                                    <span className="text-sm text-slate-400">-</span>
                                  ) : (
                                    categoriesFound.slice(0, 3).map((category) => (
                                      <Badge key={category} tone={categoryTone(category)}>{category}</Badge>
                                    ))
                                  )}
                                </div>
                              </td>
                              <td className="px-5 py-4">
                                <Badge tone={riskTone(edital.risco_identificado)}>{normalizeRisk(edital.risco_identificado)}</Badge>
                              </td>
                            </tr>
                          )
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </Card>
            </section>

            <Card className="p-6">
              <h2 className="text-lg font-semibold text-slate-950 dark:text-white">Itens mapeados</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Amostra consolidada dos itens classificados nas analises recentes.</p>
              <div className="mt-5 overflow-x-auto">
                <table className="w-full min-w-[920px] text-left">
                  <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-700 dark:text-slate-400">
                    <tr>
                      <th className="py-3 pr-4 font-semibold">Categoria</th>
                      <th className="px-4 py-3 font-semibold">Descricao</th>
                      <th className="px-4 py-3 font-semibold">Classificacao</th>
                      <th className="px-4 py-3 text-right font-semibold">Qtd</th>
                      <th className="py-3 pl-4 text-right font-semibold">Preco unit.</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                    {recentRows.flatMap((edital) => (edital.items || []).slice(0, 3)).slice(0, 12).map((item, index) => (
                      <tr key={`${item.description}-${index}`}>
                        <td className="py-3 pr-4">
                          <Badge tone={categoryTone(item.categoria)}>{item.categoria || '-'}</Badge>
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-700 dark:text-slate-300">{compactDescription(item.description)}</td>
                        <td className="px-4 py-3 text-sm text-slate-700 dark:text-slate-300">{itemCategorization(item)}</td>
                        <td className="px-4 py-3 text-right text-sm text-slate-700 dark:text-slate-300">{formatNumber(item.quantity)}</td>
                        <td className="py-3 pl-4 text-right text-sm text-slate-700 dark:text-slate-300">{item.unit_value ? formatMoney(item.unit_value) : '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </>
        )}
      </div>
    </div>
  )
}
