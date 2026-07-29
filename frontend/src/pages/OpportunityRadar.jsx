import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { pncpApi } from '../api/client'
import { useToast } from '../contexts/ToastContext'

const INITIAL_FILTERS = {
  texto: 'switch roteador firewall access point',
  modalidade: 'Pregao Eletronico',
  dataInicio: '',
  dataFim: '',
  minScore: 40,
  propostasAbertas: true,
  useCache: true,
}

const DECISION_ACTIONS = [
  { value: 'disputar', label: 'Disputar', className: 'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300' },
  { value: 'analisar', label: 'Analisar', className: 'border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300' },
  { value: 'descartar', label: 'Descartar', className: 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300' },
  { value: 'falso_positivo', label: 'Falso positivo', className: 'border-red-200 bg-red-50 text-red-700 hover:bg-red-100 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300' },
]

const DECISION_LABELS = {
  disputar: 'Disputar',
  analisar: 'Analisar depois',
  descartar: 'Descartada',
  falso_positivo: 'Falso positivo',
  fora_segmento: 'Fora do segmento',
}

const INTELLIGENCE_LABELS = {
  disputar: 'Disputar',
  analisar: 'Analisar antes',
  nao_disputar: 'Nao disputar',
}

function formatCurrency(value) {
  const number = Number(value)
  if (!Number.isFinite(number) || number <= 0) return '-'
  return number.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function formatDate(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleDateString('pt-BR')
}

function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString('pt-BR')
}

function priorityClass(priority) {
  if (priority === 'alta') return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300'
  if (priority === 'analisar') return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300'
  return 'border-slate-200 bg-slate-100 text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300'
}

function scoreTone(score) {
  if (score >= 75) return 'text-emerald-600 dark:text-emerald-300'
  if (score >= 50) return 'text-amber-600 dark:text-amber-300'
  return 'text-slate-500 dark:text-slate-400'
}

function verdictClass(verdict) {
  if (verdict === 'vale_entrar') return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300'
  if (verdict === 'avaliar') return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300'
  return 'border-slate-200 bg-slate-100 text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300'
}

function OpportunityCard({ item, importing, deciding, onImport, onDecision, onOpenCrm, onOpenJobs }) {
  const opportunity = item.opportunity || {}
  const idPncp = item.id_pncp || item.numero_controle
  const organ = item.orgao_entidade?.nome_razao_social || 'Orgao nao informado'
  const city = item.unidade_orgao?.municipio
  const uf = item.unidade_orgao?.uf
  const currentDecision = item.decision?.decision
  const intelligence = item.decision?.decision_intelligence
  const engineering = item.engineering_summary
  const radarItems = item.radar_items || []

  return (
    <article className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className={`rounded-md border px-2.5 py-1 text-xs font-semibold ${priorityClass(opportunity.priority)}`}>
              {opportunity.priority === 'alta' ? 'Prioridade alta' : opportunity.priority === 'analisar' ? 'Analisar' : 'Descartar'}
            </span>
            {idPncp && <span className="font-mono text-xs text-slate-400">{idPncp}</span>}
            {item.modalidade && <span className="rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-500 dark:border-slate-700 dark:text-slate-400">{item.modalidade}</span>}
            {currentDecision && (
              <span className="rounded-md border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700 dark:border-blue-800 dark:bg-blue-950/30 dark:text-blue-300">
                {item.decision?.crm_notice_id ? 'Enviado para CRM' : `Decisao: ${DECISION_LABELS[currentDecision] || currentDecision}`}
              </span>
            )}
            {item.decision?.import_job_id && (
              <span className="rounded-md border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
                Analise enfileirada
              </span>
            )}
            {item.decision?.import_error && (
              <span className="rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
                Importacao pendente
              </span>
            )}
          </div>

          <h2 className="line-clamp-3 text-base font-semibold leading-6 text-slate-950 dark:text-white">
            {item.objeto || item.titulo || 'Objeto nao informado'}
          </h2>

          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
            <span>{organ}</span>
            {(city || uf) && <span>{[city, uf].filter(Boolean).join(' / ')}</span>}
            <span>Publicacao: {formatDate(item.data_publicacao_pncp)}</span>
            <span>Encerramento: {formatDate(item.data_encerramento_proposta)}</span>
            <span>{formatCurrency(item.valor_total_estimado)}</span>
          </div>
        </div>

        <div className="flex flex-row items-center gap-3 lg:flex-col lg:items-end">
          <div className="text-right">
            <p className={`text-3xl font-bold ${scoreTone(opportunity.score)}`}>{opportunity.score ?? '-'}</p>
            <p className="text-xs text-slate-400">score IA</p>
          </div>
          <button
            type="button"
            className="btn-primary whitespace-nowrap disabled:opacity-40"
            disabled={!idPncp || importing === idPncp}
            onClick={() => onImport(idPncp)}
          >
            {importing === idPncp ? 'Importando...' : 'Importar'}
          </button>
          {item.decision?.crm_notice_id && (
            <button
              type="button"
              className="btn-ghost whitespace-nowrap"
              onClick={() => onOpenCrm(item.decision.crm_notice_id)}
            >
              Abrir CRM
            </button>
          )}
          {item.decision?.import_job_id && (
            <button
              type="button"
              className="btn-ghost whitespace-nowrap"
              onClick={onOpenJobs}
            >
              Ver análise
            </button>
          )}
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-4">
        {[
          ['Aderencia tecnica', opportunity.technical_fit],
          ['Comercial', opportunity.commercial_fit],
          ['Urgencia', opportunity.urgency],
          ['Risco', opportunity.risk],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg border border-slate-100 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-900">
            <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
            <p className="mt-1 text-lg font-bold text-slate-950 dark:text-white">{value ?? '-'}</p>
          </div>
        ))}
      </div>

      <div className="mt-4 rounded-lg border border-slate-100 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Engenharia</p>
            <p className="mt-1 text-sm font-semibold text-slate-950 dark:text-white">
              {engineering?.headline || 'Itens ainda nao detalhados pelo PNCP'}
            </p>
          </div>
          <span className={`rounded-md border px-2.5 py-1 text-xs font-semibold ${verdictClass(engineering?.verdict)}`}>
            {engineering?.label || 'Aguardando itens'} · {engineering?.fit_score ?? '-'}
          </span>
        </div>

        {!!radarItems.length && (
          <div className="mt-3 grid gap-2 lg:grid-cols-2">
            {radarItems.slice(0, 4).map((row, index) => (
              <div key={`${row.numero_item || index}-${row.fit_score}`} className="rounded-md border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-800">
                <div className="flex items-start justify-between gap-3">
                  <p className="line-clamp-2 text-xs font-semibold leading-5 text-slate-800 dark:text-slate-100">
                    {row.numero_item ? `Item ${row.numero_item}: ` : ''}{row.descricao || 'Descricao nao informada'}
                  </p>
                  <span className="shrink-0 rounded border border-blue-200 bg-blue-50 px-1.5 py-0.5 text-[11px] font-semibold text-blue-700 dark:border-blue-800 dark:bg-blue-950/30 dark:text-blue-300">
                    {row.fit_score}
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-500 dark:text-slate-400">
                  {row.quantidade && <span>Qtd {row.quantidade}{row.unidade ? ` ${row.unidade}` : ''}</span>}
                  {row.valor_total && <span>{formatCurrency(row.valor_total)}</span>}
                  {!!row.matched_terms?.length && <span>{row.matched_terms.slice(0, 4).join(', ')}</span>}
                </div>
              </div>
            ))}
          </div>
        )}

        {!radarItems.length && item.items_error && (
          <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">
            PNCP ainda nao retornou itens detalhados para esta oportunidade.
          </p>
        )}
      </div>

      {!!opportunity.matched_terms?.length && (
        <div className="mt-4 flex flex-wrap gap-2">
          {opportunity.matched_terms.map((term) => (
            <span key={term} className="rounded-md border border-blue-200 bg-blue-50 px-2 py-1 text-xs text-blue-700 dark:border-blue-800 dark:bg-blue-950/30 dark:text-blue-300">
              {term}
            </span>
          ))}
        </div>
      )}

      {!!item.competitor_predictions?.length && (
        <div className="mt-4 rounded-lg border border-slate-100 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-slate-900 dark:text-white">Possiveis entradas dos concorrentes</p>
            <span className="text-xs text-slate-500 dark:text-slate-400">{item.competitor_predictions.length} candidato(s)</span>
          </div>
          <div className="mt-3 space-y-3">
            {item.competitor_predictions.map((prediction) => (
              <div key={`${prediction.product_id || prediction.model}-${prediction.probability}`} className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-800">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-slate-950 dark:text-white">{prediction.model}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {[prediction.manufacturer, prediction.category].filter(Boolean).join(' · ') || 'Concorrente cadastrado'}
                    </p>
                  </div>
                  <span className={`rounded-md border px-2.5 py-1 text-xs font-semibold ${prediction.level === 'provavel' ? 'border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300' : prediction.level === 'risco_tecnico' ? 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300' : 'border-slate-200 bg-slate-100 text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300'}`}>
                    {prediction.probability}% · {prediction.level === 'provavel' ? 'provavel' : prediction.level === 'risco_tecnico' ? 'risco tecnico' : 'possivel'}
                  </span>
                </div>
                {!!prediction.evidence?.length && (
                  <ul className="mt-2 space-y-1">
                    {prediction.evidence.slice(0, 2).map((reason) => (
                      <li key={reason} className="text-xs leading-5 text-slate-600 dark:text-slate-300">{reason}</li>
                    ))}
                  </ul>
                )}
                {!!prediction.conflicts?.length && (
                  <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">
                    Conflito: {prediction.conflicts[0]}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-4 border-t border-slate-100 pt-4 dark:border-slate-700">
        <p className="text-sm font-semibold text-slate-900 dark:text-white">{opportunity.recommendation}</p>
        {item.decision?.crm_notice_id && (
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
            CRM criado. {item.decision?.pncp_files_count || 0} arquivo(s) PNCP sincronizado(s).
            {item.decision?.import_job_id ? ' A analise do PDF principal foi enfileirada.' : ''}
          </p>
        )}
        {item.decision?.import_error && (
          <p className="mt-2 text-sm text-amber-700 dark:text-amber-300">{item.decision.import_error}</p>
        )}
        {intelligence && (
          <div className="mt-4 rounded-lg border border-emerald-100 bg-emerald-50/60 p-4 dark:border-emerald-900/60 dark:bg-emerald-950/20">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-300">Parecer IA de decisao</p>
                <p className="mt-1 text-sm font-semibold text-slate-950 dark:text-white">
                  {INTELLIGENCE_LABELS[intelligence.recommendation] || intelligence.recommendation}
                </p>
              </div>
              <div className="flex gap-2 text-xs">
                <span className="rounded-md border border-emerald-200 bg-white px-2.5 py-1 font-semibold text-emerald-700 dark:border-emerald-800 dark:bg-slate-900 dark:text-emerald-300">
                  Score {intelligence.score ?? '-'}
                </span>
                <span className="rounded-md border border-amber-200 bg-white px-2.5 py-1 font-semibold text-amber-700 dark:border-amber-800 dark:bg-slate-900 dark:text-amber-300">
                  Risco {intelligence.risk_score ?? '-'}
                </span>
              </div>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-700 dark:text-slate-300">{intelligence.executive_summary}</p>
            {!!intelligence.risk_flags?.length && (
              <div className="mt-3 flex flex-wrap gap-2">
                {intelligence.risk_flags.slice(0, 4).map((risk) => (
                  <span key={risk.code} className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-700 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
                    {risk.label}
                  </span>
                ))}
              </div>
            )}
            {!!intelligence.next_actions?.length && (
              <ul className="mt-3 space-y-1">
                {intelligence.next_actions.slice(0, 3).map((action) => (
                  <li key={action} className="text-xs leading-5 text-slate-600 dark:text-slate-300">{action}</li>
                ))}
              </ul>
            )}
          </div>
        )}
        <ul className="mt-2 space-y-1">
          {(opportunity.reasons || []).map((reason) => (
            <li key={reason} className="text-sm leading-6 text-slate-600 dark:text-slate-300">{reason}</li>
          ))}
        </ul>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-4 dark:border-slate-700">
        {DECISION_ACTIONS.map((action) => {
          const active = currentDecision === action.value
          return (
            <button
              key={action.value}
              type="button"
              disabled={!idPncp || deciding === idPncp}
              onClick={() => onDecision(item, action.value)}
              className={`rounded-lg border px-3 py-2 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${action.className} ${active ? 'ring-2 ring-blue-300 dark:ring-blue-700' : ''}`}
            >
              {deciding === idPncp ? 'Salvando...' : action.label}
            </button>
          )
        })}
      </div>
    </article>
  )
}

export default function OpportunityRadar() {
  const [filters, setFilters] = useState(INITIAL_FILTERS)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [importing, setImporting] = useState(null)
  const [deciding, setDeciding] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [meta, setMeta] = useState(null)
  const { toast } = useToast()
  const navigate = useNavigate()

  const summary = useMemo(() => {
    const high = items.filter((item) => item.opportunity?.priority === 'alta').length
    const review = items.filter((item) => item.opportunity?.priority === 'analisar').length
    const avg = items.length
      ? Math.round(items.reduce((sum, item) => sum + (item.opportunity?.score || 0), 0) / items.length)
      : 0
    return { high, review, avg }
  }, [items])

  const runRadar = async (event) => {
    if (event) event.preventDefault()
    setLoading(true)
    setSearched(true)
    try {
      const response = await pncpApi.radar({ ...filters, pagina: 1, tamanhoPagina: 30, maxPages: 5 })
      setItems(response.data.items || [])
      setMeta(response.data)
    } catch (err) {
      setItems([])
      setMeta(null)
      toast({
        type: 'error',
        title: 'Radar indisponivel',
        message: err.response?.data?.detail || 'Nao foi possivel consultar o PNCP agora.',
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    runRadar()
  }, [])

  const setField = (field) => (event) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
    setFilters((current) => ({ ...current, [field]: value }))
  }

  const handleImport = async (idPncp) => {
    setImporting(idPncp)
    try {
      const response = await pncpApi.importEdital(idPncp)
      toast({
        type: 'success',
        title: 'Importacao iniciada',
        message: response.data?.message || 'Acompanhe o processamento na fila.',
      })
      navigate('/jobs')
    } catch (err) {
      toast({
        type: 'error',
        title: 'Falha ao importar',
        message: err.response?.data?.detail || 'Nao foi possivel baixar o edital no PNCP.',
      })
    } finally {
      setImporting(null)
    }
  }

  const handleDecision = async (item, decision) => {
    const idPncp = item.id_pncp || item.numero_controle
    if (!idPncp) return
    setDeciding(idPncp)
    try {
      const response = await pncpApi.decide({
        id_pncp: idPncp,
        decision,
        score: item.opportunity?.score,
        priority: item.opportunity?.priority,
        notice: {
          id_pncp: idPncp,
          objeto: item.objeto,
          modalidade: item.modalidade,
          orgao_entidade: item.orgao_entidade,
          unidade_orgao: item.unidade_orgao,
          valor_total_estimado: item.valor_total_estimado,
          data_publicacao_pncp: item.data_publicacao_pncp,
          data_encerramento_proposta: item.data_encerramento_proposta,
          radar_items: item.radar_items,
          engineering_summary: item.engineering_summary,
        },
      })
      setItems((current) => current.map((row) => {
        const rowId = row.id_pncp || row.numero_controle
        return rowId === idPncp ? { ...row, decision: response.data } : row
      }))
      toast({
        type: 'success',
        message: decision === 'disputar'
          ? 'Oportunidade enviada para o CRM.'
          : `Decisao salva: ${DECISION_LABELS[decision] || decision}.`,
      })
    } catch (err) {
      toast({
        type: 'error',
        title: 'Erro ao salvar decisao',
        message: err.response?.data?.detail || 'Nao foi possivel registrar a decisao.',
      })
    } finally {
      setDeciding(null)
    }
  }

  const handleOpenCrm = () => {
    navigate('/crm')
  }

  const handleOpenJobs = () => {
    navigate('/jobs')
  }

  const handleRefreshNow = async () => {
    setRefreshing(true)
    try {
      const refresh = await pncpApi.refreshRadar({ maxPages: 8, tamanhoPagina: 50, propostasAbertas: filters.propostasAbertas })
      toast({
        type: 'success',
        title: 'Radar atualizado',
        message: `${refresh.data?.upserted || 0} oportunidade(s) sincronizada(s) do PNCP.`,
      })
      await runRadar()
    } catch (err) {
      toast({
        type: 'error',
        title: 'Falha ao atualizar Radar',
        message: err.response?.data?.detail || 'Nao foi possivel puxar oportunidades do PNCP agora.',
      })
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <div className="min-h-screen space-y-6 p-6 lg:p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">Inteligencia comercial</p>
          <h1 className="mt-2 text-2xl font-bold text-slate-950 dark:text-white">Radar IA de oportunidades</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600 dark:text-slate-300">
            Puxa diariamente oportunidades de switches, access points, firewall, roteadores e itens de rede no PNCP, cruza com sinais do catalogo e prioriza onde vale gastar tempo de analise.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-ghost" onClick={handleRefreshNow} disabled={refreshing || loading}>
            {refreshing ? 'Atualizando...' : 'Atualizar PNCP agora'}
          </button>
          <button type="button" className="btn-ghost" onClick={() => navigate('/pncp')}>
            Busca PNCP manual
          </button>
        </div>
      </div>

      <form onSubmit={runRadar} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <div className="grid gap-4 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Termos</label>
            <input className="input" value={filters.texto} onChange={setField('texto')} placeholder="switch roteador firewall" />
          </div>
          <div className="lg:col-span-3">
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Modalidade</label>
            <input className="input" value={filters.modalidade} onChange={setField('modalidade')} placeholder="Pregao Eletronico" />
          </div>
          <div className="lg:col-span-2">
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Score minimo</label>
            <input className="input" type="number" min="0" max="100" value={filters.minScore} onChange={setField('minScore')} />
          </div>
          <div className="flex items-end lg:col-span-2">
            <button type="submit" disabled={loading} className="btn-primary w-full">
              {loading ? 'Analisando...' : 'Rodar radar'}
            </button>
          </div>
          <div className="lg:col-span-3">
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Data inicial</label>
            <input className="input" type="date" value={filters.dataInicio} onChange={setField('dataInicio')} />
          </div>
          <div className="lg:col-span-3">
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Data final</label>
            <input className="input" type="date" value={filters.dataFim} onChange={setField('dataFim')} />
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300 lg:col-span-6 lg:pt-8">
            <input type="checkbox" checked={filters.propostasAbertas} onChange={setField('propostasAbertas')} />
            Buscar preferencialmente contratacoes com propostas abertas
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300 lg:col-span-6">
            <input type="checkbox" checked={filters.useCache} onChange={setField('useCache')} />
            Usar oportunidades capturadas diariamente
          </label>
        </div>
      </form>

      <div className="grid gap-3 md:grid-cols-3">
        {[
          ['Prioridade alta', summary.high],
          ['Para analisar', summary.review],
          ['Score medio', summary.avg || '-'],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
            <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
            <p className="mt-1 text-2xl font-bold text-slate-950 dark:text-white">{loading ? '-' : value}</p>
          </div>
        ))}
      </div>

      {meta?.scoring && (
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Formula atual: {meta.scoring}. Fonte: {meta.source === 'pncp-radar-cache' ? 'captura diaria' : 'PNCP ao vivo'}.
          {' '}Ultima captura: {formatDateTime(meta.cache_last_update)}.
          {' '}Termos de catalogo ativos: {meta.catalog_terms_count ?? '-'}. Produtos concorrentes monitorados: {meta.competitor_products_count ?? 0}.
        </p>
      )}

      <div className="space-y-4">
        {items.map((item) => (
          <OpportunityCard
            key={item.id_pncp || item.numero_controle || item.objeto}
            item={item}
            importing={importing}
            deciding={deciding}
            onImport={handleImport}
            onDecision={handleDecision}
            onOpenCrm={handleOpenCrm}
            onOpenJobs={handleOpenJobs}
          />
        ))}
      </div>

      {!loading && searched && !items.length && (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center dark:border-slate-700 dark:bg-slate-800">
          <h2 className="text-lg font-semibold text-slate-950 dark:text-white">
            {filters.useCache ? 'Aguardando captura diaria' : 'Nenhuma oportunidade encontrada'}
          </h2>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            {filters.useCache
              ? 'A rotina diaria esta ativa. Use Atualizar PNCP agora se quiser puxar switches, access points e itens de rede imediatamente.'
              : 'Ajuste termos, datas ou reduza o score minimo para ampliar a triagem.'}
          </p>
        </div>
      )}
    </div>
  )
}
