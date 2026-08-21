import { useNavigate } from 'react-router-dom'
import { useMarket } from '../contexts/MarketContext'

const AI_FEATURES_ENABLED = import.meta.env.VITE_AI_FEATURES_ENABLED === '1'

const MODULES = [
  {
    number: '01',
    title: 'Radar de oportunidades',
    description: 'Busca PNCP, filtros por segmento e priorizacao de editais aderentes ao perfil comercial.',
    path: '/radar',
    cta: 'Abrir radar',
    checks: ['PNCP', 'Filtros por perfil', 'Score de prioridade'],
  },
  {
    number: '02',
    title: 'Alertas operacionais',
    description: 'Central de prazos, mudancas, sessoes e oportunidades que exigem acao do time.',
    path: '/controle',
    cta: 'Ver controle',
    checks: ['Prazos', 'Pendencias', 'Proximas sessoes'],
  },
  {
    number: '03',
    title: 'Analise IA do edital',
    description: 'Upload de PDF ou JSON para extrair objeto, itens, requisitos, riscos e perguntas ao edital.',
    path: '/upload',
    cta: 'Analisar edital',
    checks: ['Resumo', 'Checklist', 'Perguntas ao edital'],
  },
  {
    number: '04',
    title: 'Matching tecnico com catalogo',
    description: 'Comparacao entre requisitos do edital e produtos, com score, gaps e evidencias tecnicas.',
    path: '/inteligencia/datasheets',
    cta: 'Comparar catalogo',
    checks: ['Score tecnico', 'Gaps', 'Evidencias'],
    featured: true,
  },
  {
    number: '05',
    title: 'Proposta e documentos',
    description: 'Relatorios, exportacoes e dossies para transformar a analise em material comercial revisavel.',
    path: '/relatorios',
    cta: 'Gerar relatorios',
    checks: ['XLSX', 'CSV', 'Dossie executivo'],
  },
  {
    number: '06',
    title: 'CRM e pipeline',
    description: 'Funil de licitacoes para acompanhar decisao, responsaveis, itens, disputa e resultado.',
    path: '/crm',
    cta: 'Abrir CRM',
    checks: ['Kanban', 'Responsaveis', 'Historico comercial'],
  },
]
const VISIBLE_MODULES = AI_FEATURES_ENABLED
  ? MODULES
  : MODULES.filter((module) => !['03', '04'].includes(module.number))

const DIFFERENTIATORS = [
  'Uma assinatura para captacao, proposta e acompanhamento.',
  'Fluxo centralizado para organizar oportunidades, documentos e disputa.',
  'Fluxo desenhado para decidir rapido se vale participar e quais produtos ofertar.',
]

const ADVANCED_MODULES = [
  { title: 'PNCP 24/7', path: '/monitoramento-pncp', text: 'Filtros salvos, rodadas automaticas, historico e falso positivo.' },
  { title: 'Propostas', path: '/propostas', text: 'DOCX/PDF, declaracoes, carta comercial e dossie.' },
  { title: 'Habilitacao', path: '/habilitacao', text: 'Checklist juridico, documentos faltantes e riscos.' },
  { title: 'Precificacao', path: '/precificacao', text: 'Historico, margem, preco medio e alerta de inexequibilidade.' },
  { title: 'Pregao', path: '/monitor-pregao', text: 'Sessao, chat, mensagens e acompanhamento da disputa.' },
  { title: 'Pos-vitoria', path: '/pos-vitoria', text: 'Contrato, entregas, vigencia, renovacoes e SLA.' },
  { title: 'Onboarding', path: '/onboarding-planos', text: 'Primeiro edital, catalogo, perfil, alertas e planos.' },
  { title: 'Integracoes', path: '/integracoes', text: 'WhatsApp, e-mail, calendario, portais e CRM externo.' },
]

function ModuleCard({ module }) {
  const navigate = useNavigate()
  return (
    <article className={`rounded-lg border bg-white p-5 shadow-sm transition-colors dark:bg-slate-800 ${
      module.featured
        ? 'border-blue-300 dark:border-blue-700'
        : 'border-slate-200 dark:border-slate-700'
    }`}>
      <div className="flex items-start justify-between gap-4">
        <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${
          module.featured
            ? 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-300'
            : 'border-slate-200 bg-slate-50 text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400'
        }`}>
          {module.number}
        </span>
        {module.featured && (
          <span className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
            Diferencial
          </span>
        )}
      </div>
      <h2 className="mt-4 text-base font-semibold text-slate-950 dark:text-white">{module.title}</h2>
      <p className="mt-2 min-h-[60px] text-sm leading-6 text-slate-500 dark:text-slate-400">{module.description}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {module.checks.map((check) => (
          <span key={check} className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
            {check}
          </span>
        ))}
      </div>
      <button type="button" onClick={() => navigate(module.path)} className="btn-ghost mt-5 w-full">
        {module.cta}
      </button>
    </article>
  )
}

export default function Suite() {
  const market = useMarket()
  const navigate = useNavigate()

  return (
    <div className="space-y-6 p-6 lg:p-8">
      <section className="rounded-lg border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-600 dark:text-blue-300">Suite completa</p>
            <h1 className="mt-2 text-2xl font-bold text-slate-950 dark:text-white">
              Uma plataforma para encontrar, analisar, propor e acompanhar licitacoes
            </h1>
            <p className="mt-3 text-sm leading-6 text-slate-500 dark:text-slate-400">
              {market.app.product_name} cobre os principais fluxos esperados em ferramentas de licitacao, com foco especial no matching tecnico entre edital e catalogo.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <button type="button" onClick={() => navigate('/radar')} className="btn-primary">
              Buscar oportunidades
            </button>
            <button type="button" onClick={() => navigate('/upload')} className="btn-ghost">
              Analisar edital
            </button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {VISIBLE_MODULES.map((module) => <ModuleCard key={module.number} module={module} />)}
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        {DIFFERENTIATORS.map((item) => (
          <div key={item} className="rounded-lg border border-slate-200 bg-white p-4 text-sm leading-6 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
            {item}
          </div>
        ))}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-800">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm font-semibold text-slate-950 dark:text-white">Cobertura avancada contra concorrentes</p>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Modulos que completam a jornada para monitoramento, proposta, habilitacao, preco, disputa e pos-venda.
            </p>
          </div>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {ADVANCED_MODULES.map((item) => (
            <button
              key={item.path}
              type="button"
              onClick={() => navigate(item.path)}
              className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-left transition-colors hover:border-blue-200 hover:bg-white dark:border-slate-700 dark:bg-slate-900 dark:hover:border-blue-800 dark:hover:bg-slate-800"
            >
              <p className="text-sm font-semibold text-slate-950 dark:text-white">{item.title}</p>
              <p className="mt-2 min-h-[54px] text-xs leading-5 text-slate-500 dark:text-slate-400">{item.text}</p>
              <p className="mt-3 text-xs font-semibold text-blue-600 dark:text-blue-300">Abrir modulo</p>
            </button>
          ))}
        </div>
      </section>
    </div>
  )
}
