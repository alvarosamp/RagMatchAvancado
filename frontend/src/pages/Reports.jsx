import { useEffect, useMemo, useState } from 'react'
import { reportsApi } from '../api/client'

const BRL = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

const DATE = new Intl.DateTimeFormat('pt-BR', {
  dateStyle: 'short',
  timeStyle: 'short',
})

const STAGE_LABELS = {
  triage: 'Triagem',
  analysis: 'Analise',
  documentation: 'Documentacao',
  auction: 'Pregao',
  result: 'Resultado',
}

function money(value) {
  return BRL.format(Number(value || 0))
}

function formatDate(value) {
  if (!value) return 'Sem data'
  return DATE.format(new Date(value))
}

function Kpi({ label, value, helper }) {
  return (
    <div className="rounded-lg border border-slate-700 bg-ink-50/70 p-5">
      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-gray-500">{label}</p>
      <p className="mt-3 text-3xl font-bold text-white">{value}</p>
      {helper && <p className="mt-2 text-sm text-gray-400">{helper}</p>}
    </div>
  )
}

function EmptyState({ title, text }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-700 bg-ink-50/40 p-8 text-center">
      <p className="text-sm font-semibold text-white">{title}</p>
      <p className="mt-2 text-sm text-gray-500">{text}</p>
    </div>
  )
}

function agendaId(notice, index) {
  return notice.id || `${notice.numero || 'sem-numero'}-${notice.data || index}`
}

function agendaSummary(notice) {
  return (
    notice.resumo
    || notice.summary
    || notice.descricao
    || notice.objeto
    || notice.titulo
    || 'Resumo ainda nao informado para esta disputa.'
  )
}

function AgendaItem({ notice, expanded, onToggle }) {
  const summary = agendaSummary(notice)

  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={expanded}
      className="w-full rounded-lg border border-slate-700 bg-ink-50/60 p-4 text-left transition hover:border-red-400/70 hover:bg-ink-50 focus:outline-none focus:ring-2 focus:ring-red-400/70"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="font-semibold text-white">{notice.titulo}</p>
          <p className="mt-1 text-sm text-gray-500">
            {notice.numero || 'Sem numero'} | {STAGE_LABELS[notice.fase] || notice.fase || 'Sem fase'}
          </p>
        </div>
        <p className="shrink-0 text-right text-sm font-semibold text-red-400">{formatDate(notice.data)}</p>
      </div>

      <p className={`mt-3 text-sm leading-6 text-gray-400 ${expanded ? '' : 'line-clamp-2'}`}>
        {summary}
      </p>

      {expanded && (
        <div className="mt-4 grid gap-3 rounded-lg border border-slate-700/70 bg-black/15 p-3 text-xs text-gray-400 sm:grid-cols-2">
          <p>
            <span className="block font-semibold uppercase tracking-[0.18em] text-gray-500">Valor</span>
            <span className="mt-1 block text-sm font-semibold text-white">{money(notice.valor_estimado)}</span>
          </p>
          <p>
            <span className="block font-semibold uppercase tracking-[0.18em] text-gray-500">Modalidade</span>
            <span className="mt-1 block text-sm text-gray-300">{notice.modalidade || 'Nao informada'}</span>
          </p>
          <p>
            <span className="block font-semibold uppercase tracking-[0.18em] text-gray-500">Orgao</span>
            <span className="mt-1 block text-sm text-gray-300">{notice.orgao || notice.titulo || 'Nao informado'}</span>
          </p>
          <p>
            <span className="block font-semibold uppercase tracking-[0.18em] text-gray-500">UF</span>
            <span className="mt-1 block text-sm text-gray-300">{notice.uf || 'Nao informada'}</span>
          </p>
        </div>
      )}

      <span className="mt-3 inline-flex text-xs font-semibold text-red-400">
        {expanded ? 'Recolher resumo' : 'Expandir resumo'}
      </span>
    </button>
  )
}

export default function Reports() {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expandedAgendaIds, setExpandedAgendaIds] = useState(() => new Set())

  function toggleAgenda(noticeId) {
    setExpandedAgendaIds((current) => {
      const next = new Set(current)
      if (next.has(noticeId)) {
        next.delete(noticeId)
      } else {
        next.add(noticeId)
      }
      return next
    })
  }

  async function load() {
    setLoading(true)
    setError('')
    try {
      const response = await reportsApi.executive()
      setReport(response.data)
    } catch (err) {
      setError('Nao foi possivel carregar o relatorio executivo.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const pipeline = useMemo(() => {
    const entries = Object.entries(report?.pipeline?.por_fase || {})
    const max = Math.max(...entries.map(([, value]) => value), 1)
    return entries.map(([stage, value]) => ({
      stage,
      label: STAGE_LABELS[stage] || stage || 'Sem fase',
      value,
      width: `${Math.max((value / max) * 100, value ? 8 : 0)}%`,
    }))
  }, [report])

  if (loading) {
    return (
      <div className="space-y-6 p-6 md:p-8">
        <div className="h-40 animate-pulse rounded-[2rem] border border-slate-700 bg-slate-800" />
        <div className="grid gap-4 md:grid-cols-4">
          {[1, 2, 3, 4].map((item) => (
            <div key={item} className="h-32 animate-pulse rounded-lg border border-slate-700 bg-slate-800" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 md:p-8">
        <EmptyState title="Relatorio indisponivel" text={error} />
      </div>
    )
  }

  const kpis = report?.kpis || {}

  return (
    <div className="space-y-6 p-6 md:p-8">
      <section className="overflow-hidden rounded-[2rem] border border-slate-700 bg-gradient-to-br from-ink-50 via-slate-card to-ink-100 p-7 shadow-2xl shadow-black/20">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-red-400">Relatorios</p>
            <h1 className="mt-4 text-4xl font-black tracking-tight text-white md:text-5xl">
              Relatorio executivo de licitacoes
            </h1>
            <p className="mt-4 text-base leading-7 text-gray-300">{report.summary}</p>
          </div>
          <div className="rounded-lg border border-slate-700 bg-black/20 p-4 text-sm text-gray-400">
            <p className="font-semibold text-white">Atualizado</p>
            <p className="mt-1">{formatDate(report.generated_at)}</p>
            <button
              onClick={load}
              className="mt-4 rounded-lg bg-white px-4 py-2 text-sm font-bold text-ink transition hover:bg-gray-200"
            >
              Atualizar dados
            </button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Oportunidades ativas" value={kpis.oportunidades_ativas || 0} helper={`${kpis.oportunidades_crm || 0} no CRM`} />
        <Kpi label="Itens mapeados" value={kpis.itens_em_editais || 0} helper={`${kpis.matches_fortes || 0} matches fortes`} />
        <Kpi label="Valor ativo" value={money(kpis.valor_estimado_ativo)} helper="Baseado no CRM" />
        <Kpi label="Valor ganho" value={money(kpis.valor_ganho_por_item)} helper={`${kpis.itens_ganhos || 0} itens ganhos`} />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1fr_1.15fr]">
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-gray-500">Pipeline</p>
              <h2 className="mt-2 text-2xl font-bold text-white">Fases comerciais</h2>
            </div>
            <span className="rounded-full border border-slate-700 px-3 py-1 text-xs text-gray-400">
              {kpis.oportunidades_crm || 0} editais
            </span>
          </div>

          <div className="mt-6 space-y-4">
            {pipeline.length === 0 ? (
              <EmptyState title="Sem fases ainda" text="Quando os editais entrarem no CRM, o funil aparece aqui." />
            ) : pipeline.map((item) => (
              <div key={item.stage}>
                <div className="mb-2 flex items-center justify-between text-sm">
                  <span className="font-semibold text-white">{item.label}</span>
                  <span className="text-gray-500">{item.value}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-ink">
                  <div className="h-full rounded-full bg-red-400" style={{ width: item.width }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-gray-500">Proximas acoes</p>
          <h2 className="mt-2 text-2xl font-bold text-white">Recomendacoes da operacao</h2>
          <div className="mt-6 space-y-3">
            {(report.recomendacoes || []).map((item) => (
              <div key={item} className="rounded-lg border border-slate-700 bg-ink-50/60 p-4 text-sm leading-6 text-gray-300">
                {item}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <div className="card">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-gray-500">Agenda</p>
          <h2 className="mt-2 text-2xl font-bold text-white">Proximas disputas</h2>
          <div className="mt-6 space-y-3">
            {(report.proximas_disputas || []).length === 0 ? (
              <EmptyState title="Nada agendado" text="Defina a data da sessao nos editais para aparecerem aqui." />
            ) : report.proximas_disputas.map((notice, index) => {
              const noticeId = agendaId(notice, index)
              return (
                <AgendaItem
                  key={noticeId}
                  notice={notice}
                  expanded={expandedAgendaIds.has(noticeId)}
                  onToggle={() => toggleAgenda(noticeId)}
                />
              )
            })}
          </div>
        </div>

        <div className="card">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-gray-500">Itens</p>
          <h2 className="mt-2 text-2xl font-bold text-white">Maiores oportunidades</h2>
          <div className="mt-6 space-y-3">
            {(report.itens_prioritarios || []).length === 0 ? (
              <EmptyState title="Sem itens importados" text="Importe a planilha ou rode a analise do edital para popular esta lista." />
            ) : report.itens_prioritarios.map((item) => (
              <div key={item.id} className="rounded-lg border border-slate-700 bg-ink-50/60 p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-white">
                      Item {item.item || '-'} {item.lote ? `| Lote ${item.lote}` : ''}
                    </p>
                    <p className="mt-1 line-clamp-2 text-sm leading-6 text-gray-400">{item.descricao}</p>
                  </div>
                  <p className="whitespace-nowrap text-sm font-bold text-white">{money(item.valor_total)}</p>
                </div>
                <p className="mt-3 text-xs text-gray-500">
                  Quantidade {item.quantidade || 0} | Ref. {money(item.valor_referencia)}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
