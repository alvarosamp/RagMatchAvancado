import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { analysisApi, downloadBlob } from '../api/client'
import { useToast } from '../contexts/ToastContext'
import { formatNumber, formatMoney, compactDescription } from '../components/ui/format'
import Badge, { categoryTone, riskTone } from '../components/ui/Badge'
import { formatBrasiliaTime, formatBrasiliaDate } from '../utils/datetime'
import { summarizeTechnicalFeatures } from '../utils/technicalFeatures'

const PERIODS = [
  { key: 'day', label: 'Hoje' },
  { key: 'week', label: 'Semana' },
  { key: 'month', label: 'Mês' },
  { key: 'year', label: 'Ano' },
]

const POLL_MS = 20_000

function normalizeRisk(value) {
  return value && value !== 'Nenhum' ? 'Risco' : 'Sem risco'
}

function itemCategorization(item) {
  const bi = item.caracteristicas_bi || {}
  const structuredSummary = summarizeTechnicalFeatures(bi)
  if (structuredSummary) return structuredSummary
  const fields = [
    bi.quantidade_portas, bi.gerenciamento, bi.alimentacao_poe || bi.alimentacao,
    bi.portas_acesso, bi.uplinks, bi.camada, bi.tecnologia_wifi, bi.ambiente,
    bi.formato, bi.velocidade, bi.tipo_meio, bi.alcance,
  ].filter(Boolean)
  return fields.length ? fields.join(' / ') : item.categoria || '—'
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

function StatBox({ label, value, danger }) {
  return (
    <div className="flex flex-col gap-1">
      <p className={`text-4xl font-bold tabular-nums leading-none tracking-tight ${danger ? 'text-red-600 dark:text-red-400' : 'text-slate-950 dark:text-white'}`}>
        {value ?? '—'}
      </p>
      <p className="text-sm text-slate-500 dark:text-slate-400">{label}</p>
    </div>
  )
}

/** Card de edital com objeto em destaque */
function EditalCard({ edital, onClick, onDelete, deleting }) {
  const categoriesFound = Array.from(new Set((edital.items || []).map(item => item.categoria).filter(Boolean)))
  const objetoText = edital.objeto || edital.object_description || edital.description || ''
  const hasObject = objetoText.trim().length > 0
  const itemCount = edital.items?.length || 0

  return (
    <article
      className="group relative cursor-pointer rounded-xl border border-slate-200 bg-white p-5 transition-all hover:border-slate-300 hover:shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-600"
      onClick={onClick}
    >
      {/* Linha topo: número + org + risco */}
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-bold text-slate-950 dark:text-white">
              {edital.numero_pregao || edital.source_name || `Edital #${edital.id}`}
            </p>
            {edital.uf && (
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300">{edital.uf}</span>
            )}
            <Badge tone={riskTone(edital.risco_identificado)}>{normalizeRisk(edital.risco_identificado)}</Badge>
          </div>
          {edital.orgao && (
            <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400 truncate">{compactDescription(edital.orgao, 80)}</p>
          )}
        </div>
        <div className="flex-shrink-0 text-right">
          {edital.data_disputa && (
            <p className="text-xs font-semibold text-amber-600 dark:text-amber-400">{edital.data_disputa}</p>
          )}
          {itemCount > 0 && (
            <p className="text-xs text-slate-400 dark:text-slate-500">{itemCount} iten{itemCount > 1 ? 's' : ''}</p>
          )}
        </div>
      </div>

      {/* OBJETO DO EDITAL — destaque */}
      {hasObject ? (
        <div className="mt-3 rounded-lg bg-slate-50 px-4 py-3 dark:bg-slate-800">
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-slate-400 dark:text-slate-500 mb-1">Objeto</p>
          <p className="text-sm leading-6 text-slate-700 dark:text-slate-300 line-clamp-3">
            {objetoText}
          </p>
        </div>
      ) : itemCount > 0 ? (
        <div className="mt-3 rounded-lg bg-slate-50 px-4 py-3 dark:bg-slate-800">
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-slate-400 dark:text-slate-500 mb-1">Itens principais</p>
          <p className="text-sm leading-6 text-slate-700 dark:text-slate-300 line-clamp-2">
            {(edital.items || []).slice(0, 3).map(item => item.description || item.categoria).filter(Boolean).join(' · ')}
          </p>
        </div>
      ) : null}

      {/* Categorias */}
      {categoriesFound.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {categoriesFound.slice(0, 4).map(cat => (
            <Badge key={cat} tone={categoryTone(cat)}>{cat}</Badge>
          ))}
          {categoriesFound.length > 4 && (
            <span className="text-xs text-slate-400 dark:text-slate-500">+{categoriesFound.length - 4}</span>
          )}
        </div>
      )}

      {/* Rodapé com apagar */}
      <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-3 dark:border-slate-800">
        <div className="flex gap-3 text-xs text-slate-400 dark:text-slate-500">
          {edital.data_disputa && <span>Disputa: {edital.data_disputa}</span>}
          {formatMoney(edital.valor_total_estimado || 0) !== '—' && (
            <span>Est.: {formatMoney(edital.valor_total_estimado)}</span>
          )}
        </div>
        <button
          type="button"
          onClick={e => { e.stopPropagation(); onDelete(edital, e) }}
          disabled={deleting === edital.id}
          className="rounded border border-slate-200 px-2 py-1 text-xs text-slate-400 hover:border-red-200 hover:text-red-600 disabled:opacity-40 dark:border-slate-700 dark:text-slate-500 dark:hover:border-red-800 dark:hover:text-red-400"
        >
          {deleting === edital.id ? '...' : 'Apagar'}
        </button>
      </div>
    </article>
  )
}

/** Seção de itens mapeados de um edital, com descrição completa */
function ItemsSection({ editais }) {
  const items = useMemo(
    () => editais.flatMap(edital =>
      (edital.items || []).slice(0, 4).map(item => ({
        ...item,
        edital_numero: edital.numero_pregao || edital.source_name || `#${edital.id}`,
        edital_orgao: edital.orgao,
      }))
    ).slice(0, 16),
    [editais]
  )

  if (items.length === 0) return null

  return (
    <div className="space-y-2">
      {items.map((item, index) => (
        <div key={`${item.description}-${index}`}
          className="flex items-start gap-4 rounded-xl border border-slate-200 bg-white px-5 py-4 dark:border-slate-700 dark:bg-slate-900"
        >
          <Badge tone={categoryTone(item.categoria)} className="mt-0.5 flex-shrink-0">
            {item.categoria || '—'}
          </Badge>
          <div className="flex-1 min-w-0">
            {/* Descrição completa do item */}
            <p className="text-sm font-medium text-slate-950 dark:text-white leading-6">
              {item.description || item.categoria || '—'}
            </p>
            <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-500 dark:text-slate-400">
              {item.edital_numero && <span>Edital: {item.edital_numero}</span>}
              {itemCategorization(item) !== '—' && <span>{itemCategorization(item)}</span>}
              {item.prazo_entrega && <span>Prazo: {item.prazo_entrega}</span>}
            </div>
          </div>
          <div className="flex-shrink-0 text-right">
            {item.quantity > 0 && (
              <p className="text-sm font-semibold text-slate-950 dark:text-white">{formatNumber(item.quantity)} un.</p>
            )}
            {item.unit_value > 0 && (
              <p className="text-xs text-slate-500 dark:text-slate-400">{formatMoney(item.unit_value)}/un.</p>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function AnalysisDashboard() {
  const navigate = useNavigate()
  const { toast, confirm } = useToast()
  const [period, setPeriod] = useState('month')
  const [dashboard, setDashboard] = useState(null)
  const [editais, setEditais] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [lastUpdated, setLastUpdated] = useState(null)
  const [deletingId, setDeletingId] = useState(null)
  const [exporting, setExporting] = useState(false)
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
  const recentRows = useMemo(() => editais.slice(0, 12), [editais])

  const exportReport = async () => {
    setExporting(true)
    try {
      const response = await analysisApi.exportReportPdf({ period })
      downloadBlob(response.data, `bi_editais_${period}.pdf`)
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Não foi possível exportar o relatório.' })
    } finally { setExporting(false) }
  }

  const handleDelete = async (edital, event) => {
    event.stopPropagation()
    const label = edital.numero_pregao || edital.source_name || `edital #${edital.id}`
    const ok = await confirm(
      `Apagar "${label}"? Os itens ligados a ele somem do BI.`,
      { title: 'Apagar edital?' },
    )
    if (!ok) return
    setDeletingId(edital.id)
    try {
      await analysisApi.remove(edital.id)
      toast({ type: 'success', message: `${label} apagado.` })
      fetchAll(false)
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Erro ao apagar edital.' })
    } finally { setDeletingId(null) }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-10 p-6 lg:p-8">

      {/* ── Cabeçalho ─────────────────────────────────────────────────────── */}
      <header>
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">Business Intelligence</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 dark:text-white">Editais</h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {lastUpdated ? `Atualizado às ${formatBrasiliaTime(lastUpdated)}` : 'Carregando...'}
              {' · '}atualização automática a cada 20s
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {/* Seletor de período compacto */}
            <div className="flex rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800 overflow-hidden">
              {PERIODS.map(item => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setPeriod(item.key)}
                  className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                    period === item.key
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-700'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={exportReport}
              disabled={exporting}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
            >
              {exporting ? 'Exportando...' : '↓ PDF'}
            </button>
            <button
              type="button"
              onClick={() => navigate('/upload')}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
            >
              + Edital
            </button>
          </div>
        </div>
      </header>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/30 dark:text-red-300">
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900" />
          ))}
        </div>
      ) : (
        <>
          {/* ── 01 · Visão geral ───────────────────────────────────────────── */}
          <section className="space-y-5">
            <SectionLabel number={1}>Visão geral do período</SectionLabel>
            <div className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900">
              <div className="grid grid-cols-2 gap-6 sm:grid-cols-5">
                <StatBox label="Editais selecionados" value={formatNumber(kpis.editais_selecionados)} />
                <StatBox label="Itens mapeados" value={formatNumber(kpis.itens_categorizados)} />
                <StatBox label="Unidades" value={formatNumber(kpis.unidades_mapeadas)} />
                <StatBox label="Com risco" value={formatNumber(kpis.editais_com_risco)} danger={kpis.editais_com_risco > 0} />
                <StatBox label="Com ME/EPP" value={formatNumber(kpis.editais_com_me_epp)} />
              </div>
            </div>
          </section>

          {/* ── 02 · Editais recentes com objeto ──────────────────────────── */}
          <section className="space-y-5">
            <div className="flex items-center justify-between">
              <SectionLabel number={2}>Editais recentes</SectionLabel>
              <button
                type="button"
                onClick={() => navigate('/upload')}
                className="text-xs font-semibold text-blue-600 hover:underline dark:text-blue-400"
              >
                + Novo
              </button>
            </div>

            {recentRows.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center dark:border-slate-700 dark:bg-slate-900">
                <p className="text-lg font-semibold text-slate-950 dark:text-white">Nenhum edital importado ainda</p>
                <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                  Envie um edital em JSON para começar a usar o BI.
                </p>
                <button
                  type="button"
                  onClick={() => navigate('/upload')}
                  className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                >
                  Enviar edital
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {recentRows.map(edital => (
                  <EditalCard
                    key={edital.id}
                    edital={edital}
                    onClick={() => navigate(`/analise/documentos/${edital.id}`)}
                    onDelete={handleDelete}
                    deleting={deletingId}
                  />
                ))}
              </div>
            )}
          </section>

          {/* ── 03 · Itens mapeados com descrição completa ────────────────── */}
          {recentRows.length > 0 && (
            <section className="space-y-5">
              <SectionLabel number={3}>Itens dos editais</SectionLabel>
              <p className="text-base text-slate-600 dark:text-slate-400">
                Descrições completas dos itens encontrados nos editais mais recentes.
              </p>
              <ItemsSection editais={recentRows} />
            </section>
          )}

          {/* ── 04 · Por categoria ────────────────────────────────────────── */}
          {categories.length > 0 && (
            <section className="space-y-5">
              <SectionLabel number={4}>Por categoria de equipamento</SectionLabel>
              <div className="space-y-3">
                {categories.slice(0, 4).map(cat => (
                  <div key={cat.categoria} className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <h3 className="text-base font-semibold text-slate-950 dark:text-white">{cat.categoria}</h3>
                        <p className="text-xs text-slate-500 dark:text-slate-400">{cat.itens} itens · {formatNumber(cat.unidades)} unidades</p>
                      </div>
                      <p className="text-right text-lg font-bold text-slate-950 dark:text-white">{formatMoney(cat.valor_mapeado)}</p>
                    </div>

                    {/* Breakdowns simplificados */}
                    {Object.entries(cat.breakdowns || {}).slice(0, 2).map(([field, rows]) => (
                      <div key={field} className="mt-3 border-t border-slate-100 pt-3 dark:border-slate-800">
                        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.1em] text-slate-400 dark:text-slate-500">
                          {field.replace(/_/g, ' ')}
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {rows.slice(0, 5).map(row => (
                            <span key={row.valor} className="rounded-full border border-slate-200 px-3 py-0.5 text-xs text-slate-700 dark:border-slate-700 dark:text-slate-300">
                              {row.valor} <span className="text-slate-400 dark:text-slate-500">({formatNumber(row.unidades)})</span>
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}
