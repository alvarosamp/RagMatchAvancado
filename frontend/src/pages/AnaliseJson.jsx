import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { analysisApi, downloadBlob } from '../api/client'
import { useToast } from '../contexts/ToastContext'
import { formatNumber, compactDescription } from '../components/ui/format'
import Card from '../components/ui/Card'
import Badge, { categoryTone, riskTone } from '../components/ui/Badge'

const TABS = [
  { key: 'itens', label: 'Itens elegiveis' },
  { key: 'documentacao', label: 'Documentacao' },
  { key: 'riscos', label: 'Riscos' },
  { key: 'declaracoes', label: 'Declaracoes' },
]

function formatMoney(value) {
  if (value == null || value === '') return '-'
  const number = Number(String(value).replace(',', '.'))
  if (Number.isNaN(number)) return String(value)
  return number.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function itemDetails(item) {
  const bi = item.caracteristicas_bi || item.raw_payload?.caracteristicas_bi || {}
  return Object.values(bi).filter((value) => value && value !== 'N/C').join(' / ') || '-'
}

function InfoCard({ label, value }) {
  return (
    <Card className="p-4">
      <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{label}</p>
      <p className="mt-2 truncate text-base font-semibold text-slate-950 dark:text-white" title={String(value || '-')}>{value || '-'}</p>
    </Card>
  )
}

export default function AnaliseJson() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { toast, confirm } = useToast()

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [tab, setTab] = useState('itens')
  const [exporting, setExporting] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    setLoading(true)
    setNotFound(false)
    analysisApi.get(id)
      .then((response) => setData(response.data))
      .catch((err) => {
        if (err.response?.status === 404) setNotFound(true)
        else toast({ type: 'error', message: err.response?.data?.detail || 'Erro ao carregar a analise.' })
      })
      .finally(() => setLoading(false))
  }, [id])

  const edital = data?.edital || {}
  const riscos = data?.riscos || {}
  const documentacao = data?.documentacao || []
  const declaracoes = data?.declaracoes || []
  const items = data?.items || []
  const totalUnits = useMemo(() => items.reduce((sum, item) => sum + Number(item.quantity || 0), 0), [items])
  const totalValue = useMemo(
    () => items.reduce((sum, item) => sum + Number(item.total_value || 0), 0),
    [items],
  )

  const exportPdf = async () => {
    setExporting(true)
    try {
      const response = await analysisApi.exportPdf(id)
      downloadBlob(response.data, `bi_edital_analise_${id}.pdf`)
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Nao foi possivel exportar a analise.' })
    } finally {
      setExporting(false)
    }
  }

  const handleDelete = async () => {
    const label = edital.orgao || data?.source_name || `edital #${id}`
    const ok = await confirm(
      `Apagar "${label}"? Os itens ligados a ele somem do BI. O que já foi sincronizado no CRM não é afetado.`,
      { title: 'Apagar edital?' },
    )
    if (!ok) return
    setDeleting(true)
    try {
      await analysisApi.remove(id)
      toast({ type: 'success', message: `${label} apagado.` })
      navigate('/analise/dashboard')
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Erro ao apagar edital.' })
      setDeleting(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-surface p-6 dark:bg-surface-dark lg:p-8">
        <div className="mx-auto max-w-6xl space-y-4">
          {[...Array(5)].map((_, index) => (
            <div key={index} className="h-16 animate-pulse rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800" />
          ))}
        </div>
      </div>
    )
  }

  if (notFound || !data) {
    return (
      <div className="min-h-screen bg-surface p-6 text-slate-950 dark:bg-surface-dark dark:text-white lg:p-8">
        <Card className="mx-auto max-w-3xl p-10 text-center">
          <h1 className="text-2xl font-semibold">Analise nao encontrada</h1>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">Este edital ainda nao tem arquivo importado.</p>
          <button
            type="button"
            onClick={() => navigate('/upload')}
            className="mt-5 rounded-lg bg-brand px-5 py-2 text-sm font-medium text-white hover:bg-brand-dark dark:bg-brand-light dark:hover:bg-brand"
          >
            Enviar edital
          </button>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-surface p-6 text-slate-950 dark:bg-surface-dark dark:text-white lg:p-8">
      <div className="mx-auto max-w-[1400px] space-y-6">
        <Card className="p-6">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="mb-4 text-sm font-medium text-slate-500 hover:text-slate-950 dark:text-slate-400 dark:hover:text-white"
          >
            Voltar
          </button>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">Analise de edital</p>
              <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 dark:text-white">
                {edital.orgao || data.source_name || `Edital #${id}`}
              </h1>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                {edital.numero_pregao || '-'} · {edital.uf || '-'} · {edital.cidade || '-'}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge tone={riskTone(riscos.risco_identificado)} className="w-fit">
                {riscos.risco_identificado && riscos.risco_identificado !== 'Nenhum' ? 'Risco identificado' : 'Sem risco'}
              </Badge>
              <button
                type="button"
                onClick={exportPdf}
                disabled={exporting}
                className="rounded-lg bg-brand px-5 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50 dark:bg-brand-light dark:hover:bg-brand"
              >
                {exporting ? 'Exportando...' : 'Exportar analise'}
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleting}
                className="rounded-lg border border-slate-200 px-5 py-2 text-sm font-medium text-slate-600 hover:border-red-200 hover:bg-red-50 hover:text-red-700 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:border-red-800 dark:hover:bg-red-950/40 dark:hover:text-red-300"
              >
                {deleting ? 'Apagando...' : 'Apagar edital'}
              </button>
            </div>
          </div>
        </Card>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <InfoCard label="Data da disputa" value={edital.data_disputa} />
          <InfoCard label="Criterio" value={edital.criterio} />
          <InfoCard label="ME/EPP" value={edital.exclusividade_me_epp} />
          <InfoCard label="Itens" value={formatNumber(items.length)} />
          <InfoCard label="Unidades" value={formatNumber(totalUnits)} />
        </section>

        <nav className="flex flex-wrap gap-2 border-b border-slate-200 dark:border-slate-700">
          {TABS.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setTab(item.key)}
              className={`border-b-2 px-4 py-3 text-sm font-medium ${
                tab === item.key
                  ? 'border-brand text-brand dark:border-brand-light dark:text-brand-light'
                  : 'border-transparent text-slate-500 hover:text-slate-950 dark:text-slate-400 dark:hover:text-white'
              }`}
            >
              {item.label}{item.key === 'itens' ? ` (${items.length})` : ''}
            </button>
          ))}
        </nav>

        {tab === 'itens' && (
          <Card className="overflow-hidden">
            <div className="border-b border-slate-200 px-5 py-4 dark:border-slate-700">
              <h2 className="text-lg font-semibold text-slate-950 dark:text-white">Itens elegiveis</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Total mapeado: {formatNumber(totalUnits)} unidades · {formatMoney(totalValue)}</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1120px] text-left">
                <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Item</th>
                    <th className="px-5 py-3 font-semibold">Categoria</th>
                    <th className="px-5 py-3 font-semibold">Descricao</th>
                    <th className="px-5 py-3 font-semibold">Classificacao</th>
                    <th className="px-5 py-3 font-semibold">Prazo</th>
                    <th className="px-5 py-3 text-right font-semibold">Qtd</th>
                    <th className="px-5 py-3 text-right font-semibold">Preco unit.</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                  {items.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-5 py-8 text-center text-sm text-slate-500 dark:text-slate-400">Nenhum item elegivel listado.</td>
                    </tr>
                  ) : (
                    items.map((item) => (
                      <tr key={item.id}>
                        <td className="px-5 py-4 text-sm font-semibold text-slate-950 dark:text-white">{item.item_number || '-'}</td>
                        <td className="px-5 py-4">
                          <Badge tone={categoryTone(item.categoria)}>{item.categoria || '-'}</Badge>
                        </td>
                        <td className="px-5 py-4 text-sm text-slate-700 dark:text-slate-300">{compactDescription(item.description)}</td>
                        <td className="px-5 py-4 text-sm text-slate-700 dark:text-slate-300">{itemDetails(item)}</td>
                        <td className="px-5 py-4 text-sm text-slate-700 dark:text-slate-300">{item.prazo_entrega || item.raw_payload?.prazo_entrega || '-'}</td>
                        <td className="px-5 py-4 text-right text-sm text-slate-700 dark:text-slate-300">{formatNumber(item.quantity)}</td>
                        <td className="px-5 py-4 text-right text-sm text-slate-700 dark:text-slate-300">{formatMoney(item.unit_value ?? item.raw_payload?.preco_unitario)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {tab === 'documentacao' && (
          <Card className="overflow-hidden">
            <table className="w-full text-left">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
                <tr>
                  <th className="px-5 py-3 font-semibold">Categoria</th>
                  <th className="px-5 py-3 font-semibold">Documento</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {documentacao.length === 0 ? (
                  <tr><td colSpan={2} className="px-5 py-8 text-center text-sm text-slate-500 dark:text-slate-400">Nenhum documento listado.</td></tr>
                ) : (
                  documentacao.map((doc, index) => (
                    <tr key={`${doc.documento}-${index}`}>
                      <td className="px-5 py-4 text-sm text-slate-600 dark:text-slate-300">{doc.categoria || '-'}</td>
                      <td className="px-5 py-4 text-sm font-medium text-slate-950 dark:text-white">{doc.documento || '-'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </Card>
        )}

        {tab === 'riscos' && (
          <section className="grid gap-4 lg:grid-cols-3">
            <InfoCard label="Risco identificado" value={riscos.risco_identificado || 'Nenhum'} />
            {['risco_operacional', 'risco_documental'].map((key) => {
              const risk = riscos[key]
              return (
                <Card key={key} className="p-4">
                  <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{key.replace(/_/g, ' ')}</p>
                  <p className="mt-2 text-base font-semibold text-slate-950 dark:text-white">{risk?.existe ? 'Existe' : 'Nao existe'}</p>
                  {risk?.motivos?.length > 0 && (
                    <ul className="mt-3 space-y-2 text-sm text-slate-600 dark:text-slate-300">
                      {risk.motivos.map((motivo, index) => <li key={index}>{motivo}</li>)}
                    </ul>
                  )}
                </Card>
              )
            })}
          </section>
        )}

        {tab === 'declaracoes' && (
          <Card className="p-5">
            {declaracoes.length === 0 ? (
              <p className="text-center text-sm text-slate-500 dark:text-slate-400">Nenhuma declaracao listada.</p>
            ) : (
              <div className="grid gap-3 md:grid-cols-2">
                {declaracoes.map((declaracao, index) => (
                  <div key={`${declaracao.declaracao}-${index}`} className="rounded border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
                    {declaracao.declaracao}
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}
      </div>
    </div>
  )
}
