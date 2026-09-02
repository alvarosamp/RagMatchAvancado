import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

const STORAGE_PREFIX = 'tor_procurement_module_'
const CRM_ENTRYPOINT = '/crm/'

const MODULES = {
  pncp_monitor: {
    title: 'Monitoramento PNCP 24/7',
    eyebrow: 'Captacao continua',
    description: 'Salve filtros, acompanhe historico de oportunidades vistas e registre descartes para reduzir falsos positivos.',
    primaryAction: 'Abrir Radar PNCP',
    primaryPath: '/radar',
    metrics: [
      ['Filtros salvos', '3'],
      ['Rodadas hoje', '4'],
      ['Novas oportunidades', '12'],
      ['Falsos positivos', '2'],
    ],
    sections: [
      {
        title: 'Filtros monitorados',
        items: ['Switch, roteador, firewall e access point', 'Pregao eletronico com propostas abertas', 'Valor estimado acima de R$ 20 mil', 'Estados prioritarios: SP, MG, RJ, PR'],
      },
      {
        title: 'Aprendizado operacional',
        items: ['Descartes por fora do segmento ajustam o score', 'Oportunidades importadas deixam de aparecer como novas', 'Termos com baixa conversao entram em revisao', 'Historico preserva orgao, data e decisao tomada'],
      },
    ],
    tasks: ['Salvar filtro PNCP por perfil comercial', 'Agendar busca automatica diaria', 'Marcar oportunidade ja vista', 'Registrar falso positivo com motivo', 'Enviar alerta para responsavel'],
  },
  proposal_studio: {
    title: 'Gerador completo de proposta',
    eyebrow: 'Documentos comerciais',
    description: 'Central para montar proposta, declaracoes, planilha de itens, dossie e textos de esclarecimento ou impugnacao.',
    primaryAction: 'Abrir Relatorios',
    primaryPath: '/relatorios',
    metrics: [
      ['Modelos', '6'],
      ['Formatos', 'DOCX/PDF/XLSX'],
      ['Campos revisaveis', '18'],
      ['Tempo medio', '5 min'],
    ],
    sections: [
      {
        title: 'Pacote de proposta',
        items: ['Carta comercial', 'Proposta tecnica', 'Planilha de itens', 'Declaracoes obrigatorias', 'Dossie de habilitacao'],
      },
      {
        title: 'Textos assistidos',
        items: ['Pedido de esclarecimento', 'Minuta de impugnacao', 'Resposta a diligencia', 'Justificativa tecnica do produto ofertado'],
      },
    ],
    tasks: ['Escolher edital base', 'Selecionar itens atendidos', 'Preencher dados da empresa', 'Gerar proposta DOCX/PDF', 'Exportar planilha de itens'],
  },
  compliance_checklist: {
    title: 'Checklist juridico e habilitacao',
    eyebrow: 'Lei 14.133 e risco',
    description: 'Mapeie documentos exigidos, pendencias, riscos juridicos, clausulas restritivas e exigencias de habilitacao tecnica.',
    primaryAction: 'Analisar Edital',
    primaryPath: '/upload',
    metrics: [
      ['Documentos', '14'],
      ['Riscos', '5'],
      ['Pendencias', '3'],
      ['Clausulas criticas', '2'],
    ],
    sections: [
      {
        title: 'Habilitacao',
        items: ['Certidoes fiscais', 'Atestado de capacidade tecnica', 'Balanco e qualificação economica', 'Declaracoes ME/EPP', 'Documentos societarios'],
      },
      {
        title: 'Risco juridico',
        items: ['Clausula restritiva', 'Prazo inexequivel', 'Exigencia de marca sem justificativa', 'Garantia/assistencia tecnica fora do padrao'],
      },
    ],
    tasks: ['Extrair documentos exigidos', 'Classificar risco por gravidade', 'Marcar documento faltante', 'Gerar checklist de habilitacao', 'Preparar esclarecimento/impugnacao'],
  },
  pricing: {
    title: 'Precificacao e margem',
    eyebrow: 'Preco vencedor',
    description: 'Estruture historico de precos, media por orgao/item, sugestao de preco e alerta de inexequibilidade.',
    primaryAction: 'Ver Inteligencia Competitiva',
    primaryPath: '/inteligencia/competitiva',
    metrics: [
      ['Historico', 'Atas e PNCP'],
      ['Margem minima', 'Configuravel'],
      ['Alertas', 'Inexequivel'],
      ['Comparacao', 'Concorrentes'],
    ],
    sections: [
      {
        title: 'Sinais de preco',
        items: ['Preco medio por item similar', 'Preco vencedor mais recente', 'Variação por regiao', 'Faixa segura de lance', 'Margem minima por categoria'],
      },
      {
        title: 'Decisao comercial',
        items: ['Sugerir preco inicial', 'Simular margem', 'Alertar preço abaixo do custo', 'Comparar com concorrente recorrente'],
      },
    ],
    tasks: ['Importar historico de atas', 'Cadastrar custo minimo por produto', 'Calcular preco medio por orgao', 'Sugerir preco por item', 'Alertar inexequibilidade'],
  },
  auction_monitor: {
    title: 'Monitor de pregão e chat',
    eyebrow: 'Disputa em tempo real',
    description: 'Painel para registrar sessoes, mensagens do pregoeiro, avisos e acompanhamento de disputa.',
    primaryAction: 'Abrir CRM',
    primaryPath: CRM_ENTRYPOINT,
    external: true,
    metrics: [
      ['Sessoes proximas', '7 dias'],
      ['Mensagens', 'Registro'],
      ['Avisos', 'Tempo real'],
      ['Origem', 'Compras.gov/BLL'],
    ],
    sections: [
      {
        title: 'Sessao',
        items: ['Data e hora da disputa', 'Portal de origem', 'Responsavel interno', 'Status de login no portal', 'Itens em acompanhamento'],
      },
      {
        title: 'Chat e avisos',
        items: ['Mensagem do pregoeiro', 'Pedido de anexo', 'Nova rodada de lance', 'Suspensao/reabertura', 'Registro de ocorrencias'],
      },
    ],
    tasks: ['Cadastrar sessao do pregao', 'Vincular responsavel', 'Registrar mensagens', 'Configurar aviso de fala do pregoeiro', 'Anexar ata da disputa'],
  },
  post_award: {
    title: 'Gestao pos-vitoria',
    eyebrow: 'Contrato e entrega',
    description: 'Acompanhe contrato, vigencia, entregas, renovacoes, documentos pos-adjudicacao e SLA interno.',
    primaryAction: 'Abrir CRM',
    primaryPath: CRM_ENTRYPOINT,
    external: true,
    metrics: [
      ['Contratos', 'Pipeline'],
      ['Vigencia', 'Renovacoes'],
      ['Entregas', 'SLA'],
      ['Riscos', 'Penalidades'],
    ],
    sections: [
      {
        title: 'Contrato',
        items: ['Numero do contrato', 'Orgao contratante', 'Vigencia', 'Valor homologado', 'Garantias e penalidades'],
      },
      {
        title: 'Execucao',
        items: ['Cronograma de entrega', 'Documentos pos-adjudicacao', 'SLA interno', 'Renovacao/reequilibrio', 'Ocorrencias'],
      },
    ],
    tasks: ['Criar contrato a partir de vitoria', 'Cadastrar entregas', 'Alertar vencimento de vigencia', 'Registrar documento pos-adjudicacao', 'Monitorar SLA'],
  },
  onboarding_plans: {
    title: 'Onboarding e planos',
    eyebrow: 'Primeiro valor rapido',
    description: 'Guie o usuario por catalogo, perfil comercial, alertas, primeiro edital, primeira proposta e limites por plano.',
    primaryAction: 'Enviar primeiro edital',
    primaryPath: '/upload',
    metrics: [
      ['Passos', '6'],
      ['Planos', '3'],
      ['Setup', '15 min'],
      ['Limites', 'Configuraveis'],
    ],
    sections: [
      {
        title: 'Onboarding',
        items: ['Importar catalogo', 'Configurar CNPJ/CNAE', 'Definir perfil PNCP', 'Ativar alertas', 'Testar primeiro edital', 'Gerar primeira proposta'],
      },
      {
        title: 'Planos',
        items: ['Starter: radar e analise basica', 'Pro: matching, proposta e CRM', 'Enterprise: integracoes, multiusuario e auditoria'],
      },
    ],
    tasks: ['Criar checklist inicial', 'Configurar perfil da empresa', 'Definir limites por plano', 'Mostrar progresso de ativacao', 'Liberar primeiro teste guiado'],
  },
  integrations: {
    title: 'Integracoes externas',
    eyebrow: 'Tudo em um lugar',
    description: 'Centralize canais de notificacao, calendario, portais de compra, assinatura, documentos e CRM externo.',
    primaryAction: 'Abrir Ajustes',
    primaryPath: '/configuracoes',
    metrics: [
      ['WhatsApp', 'Planejado'],
      ['E-mail', 'Monitorado'],
      ['Calendario', 'Planejado'],
      ['Portais', 'Compras.gov/BLL'],
    ],
    sections: [
      {
        title: 'Canais',
        items: ['WhatsApp para alertas criticos', 'E-mail para resumo diario', 'Calendario para sessoes e prazos', 'Assinatura/documentos'],
      },
      {
        title: 'Sistemas',
        items: ['Compras.gov', 'BLL/Licitacoes-e', 'CRM externo', 'Google/Microsoft Calendar', 'Drive/SharePoint'],
      },
    ],
    tasks: ['Conectar e-mail de alertas', 'Configurar calendario', 'Mapear portal de disputa', 'Preparar webhook de CRM', 'Definir canal por tipo de alerta'],
  },
}

function readDone(moduleId) {
  try {
    return JSON.parse(localStorage.getItem(`${STORAGE_PREFIX}${moduleId}`) || '[]')
  } catch {
    return []
  }
}

function saveDone(moduleId, done) {
  localStorage.setItem(`${STORAGE_PREFIX}${moduleId}`, JSON.stringify(done))
}

export default function ProcurementExpansion({ moduleId }) {
  const navigate = useNavigate()
  const module = MODULES[moduleId] || MODULES.pncp_monitor
  const [done, setDone] = useState(() => readDone(moduleId))

  const progress = useMemo(() => {
    if (!module.tasks.length) return 0
    return Math.round((done.length / module.tasks.length) * 100)
  }, [done, module.tasks.length])

  const toggleTask = (task) => {
    setDone((current) => {
      const next = current.includes(task) ? current.filter((item) => item !== task) : [...current, task]
      saveDone(moduleId, next)
      return next
    })
  }

  return (
    <div className="space-y-6 p-6 lg:p-8">
      <section className="rounded-lg border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-600 dark:text-blue-300">{module.eyebrow}</p>
            <h1 className="mt-2 text-2xl font-bold text-slate-950 dark:text-white">{module.title}</h1>
            <p className="mt-3 text-sm leading-6 text-slate-500 dark:text-slate-400">{module.description}</p>
          </div>
          <button type="button" onClick={() => module.external ? window.location.assign(module.primaryPath) : navigate(module.primaryPath)} className="btn-primary">
            {module.primaryAction}
          </button>
        </div>
      </section>

      <section className="grid gap-3 md:grid-cols-4">
        {module.metrics.map(([label, value]) => (
          <div key={label} className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
            <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
            <p className="mt-2 text-xl font-bold text-slate-950 dark:text-white">{value}</p>
          </div>
        ))}
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        {module.sections.map((section) => (
          <article key={section.title} className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-800">
            <h2 className="text-base font-semibold text-slate-950 dark:text-white">{section.title}</h2>
            <div className="mt-4 space-y-2">
              {section.items.map((item) => (
                <div key={item} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
                  {item}
                </div>
              ))}
            </div>
          </article>
        ))}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-800">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-950 dark:text-white">Plano de implementacao</h2>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Checklist local para organizar a ativacao deste modulo.</p>
          </div>
          <div className="min-w-40">
            <div className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-900">
              <div className="h-full rounded-full bg-blue-600" style={{ width: `${progress}%` }} />
            </div>
            <p className="mt-1 text-right text-xs text-slate-500 dark:text-slate-400">{progress}%</p>
          </div>
        </div>

        <div className="mt-5 grid gap-2 md:grid-cols-2">
          {module.tasks.map((task) => {
            const checked = done.includes(task)
            return (
              <button
                key={task}
                type="button"
                onClick={() => toggleTask(task)}
                className={`flex items-center gap-3 rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                  checked
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300'
                    : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-white dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800'
                }`}
              >
                <span className="grid h-5 w-5 shrink-0 place-items-center rounded border border-current text-[11px]">
                  {checked ? 'OK' : ''}
                </span>
                <span>{task}</span>
              </button>
            )
          })}
        </div>
      </section>
    </div>
  )
}
