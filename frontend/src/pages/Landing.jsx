import { Link } from 'react-router-dom'
import ProductMark from '../components/ProductMark'
import { useAuth } from '../contexts/AuthContext'
import { useMarket } from '../contexts/MarketContext'

const journey = [
  ['01', 'Encontrar', 'Radar PNCP e filtros para transformar publicações em oportunidades priorizadas.'],
  ['02', 'Analisar', 'Leitura estruturada do edital, requisitos, riscos e evidências em um só lugar.'],
  ['03', 'Comparar', 'Matching técnico, catálogo de produtos, datasheets e inteligência competitiva.'],
  ['04', 'Decidir', 'Score, pareceres e contexto comercial para disputar, analisar ou descartar.'],
  ['05', 'Operar', 'CRM, documentos, relatórios e acompanhamento da disputa até o resultado.'],
]

const availableTools = [
  ['Radar PNCP', 'Busca, filtros, score e priorização de oportunidades.'],
  ['Importação de editais', 'Entrada por PDF, JSON ou oportunidade do radar.'],
  ['Análise documental', 'Requisitos, lotes, itens, categorias e riscos estruturados.'],
  ['Matching técnico', 'Compatibilidade entre exigências e produtos do catálogo.'],
  ['Chat com o edital', 'Perguntas e respostas apoiadas nas evidências do documento.'],
  ['Datasheets', 'Extração, catálogo, comparação e identificação de lacunas.'],
  ['Inteligência competitiva', 'Concorrentes, alternativas e argumentos de resposta.'],
  ['CRM comercial', 'Funil, calendário, órgãos, portais e acompanhamento da disputa.'],
  ['Documentos e assinaturas', 'Versões, anexos, solicitações e status de assinatura.'],
  ['Robô de lances assistido', 'Sessões, lotes e lances críticos com confirmação humana.'],
  ['Relatórios e exportações', 'Visões executivas e arquivos PDF, XLSX e CSV.'],
  ['Gestão da operação', 'Fila de processamento, progresso, alertas e indicadores.'],
]

const expansionTools = [
  ['Propostas', 'Geração e organização de documentos e declarações.'],
  ['Habilitação', 'Checklist jurídico e acompanhamento de pendências.'],
  ['Precificação', 'Margem, histórico, cenários e limites de disputa.'],
  ['Pós-vitória', 'Contrato, entrega, obrigações e acompanhamento.'],
  ['Integrações', 'Novos canais, portais e sistemas conectados.'],
]

const faqs = [
  ['A plataforma participa automaticamente de uma licitação?', 'Não. Ela organiza dados, recomenda ações e automatiza etapas assistidas. Decisões críticas, como confirmar um lance, continuam sob controle da equipe.'],
  ['A inteligência artificial substitui a análise humana?', 'Não. A IA acelera leitura, comparação e busca de evidências. O parecer final permanece com quem conhece o negócio, o produto e o risco da disputa.'],
  ['Cada empresa tem seu próprio ambiente?', 'Sim. O produto foi pensado como uma plataforma multiempresa, com usuários, permissões, dados e configuração separados por organização.'],
  ['Consigo exportar os resultados?', 'Sim. Há exportações em PDF, XLSX e CSV, além de relatórios executivos e operacionais.'],
  ['É apenas uma ferramenta de busca de editais?', 'Não. A busca é a entrada de uma jornada que inclui análise documental, matching técnico, decisão, CRM, documentos, disputa assistida e acompanhamento.'],
]

function CheckIcon() {
  return (
    <span className="grid h-6 w-6 flex-none place-items-center rounded-full bg-emerald-100 text-sm font-bold text-emerald-700">✓</span>
  )
}

function RadarPreview() {
  return (
    <div className="relative rounded-[2rem] border border-slate-200 bg-white p-3 shadow-2xl shadow-blue-950/15">
      <div className="rounded-[1.45rem] border border-slate-100 bg-slate-50 p-4 sm:p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-700">Radar de oportunidades</p>
            <p className="mt-1 text-sm text-slate-500">Atualizado agora</p>
          </div>
          <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-700">PNCP ativo</span>
        </div>
        <div className="mb-3 grid grid-cols-3 gap-2 text-xs text-slate-500">
          <div className="rounded-xl border bg-white px-3 py-2">Categoria</div>
          <div className="rounded-xl border bg-white px-3 py-2">UF</div>
          <div className="rounded-xl border bg-white px-3 py-2">Prazo</div>
        </div>
        <div className="rounded-2xl border border-blue-100 bg-white p-4 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold text-slate-400">PE 0142/2026 · Hospital Municipal</p>
              <h3 className="mt-1 font-bold text-slate-900">Aquisição de equipamentos hospitalares</h3>
            </div>
            <div className="grid h-14 w-14 flex-none place-items-center rounded-2xl bg-blue-700 text-white">
              <span className="text-lg font-black">91</span>
              <span className="-mt-4 text-[9px] uppercase">score</span>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-4 gap-2">
            {[['Técnico', '94'], ['Comercial', '88'], ['Urgência', '82'], ['Risco', 'Baixo']].map(([label, value]) => (
              <div key={label} className="rounded-xl bg-slate-50 p-2 text-center">
                <p className="text-[10px] text-slate-400">{label}</p>
                <p className="text-xs font-bold text-slate-800">{value}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap gap-2 text-xs font-bold">
            <span className="rounded-lg bg-blue-700 px-3 py-2 text-white">Analisar</span>
            <span className="rounded-lg bg-emerald-100 px-3 py-2 text-emerald-700">Disputar</span>
            <span className="rounded-lg border px-3 py-2 text-slate-500">Descartar</span>
          </div>
        </div>
      </div>
      <div className="absolute -bottom-5 -left-5 hidden rounded-2xl border border-emerald-100 bg-white p-3 shadow-xl sm:block">
        <p className="text-xs text-slate-500">Oportunidades aderentes</p>
        <p className="text-xl font-black text-emerald-600">+12 hoje</p>
      </div>
    </div>
  )
}

function AnalysisPreview() {
  const rows = [
    ['Registro sanitário vigente', 'Atende', 'emerald'],
    ['Tensão bivolt automática', 'Atende', 'emerald'],
    ['Garantia mínima de 24 meses', 'Verificar', 'amber'],
    ['Peso máximo de 4,5 kg', 'Não atende', 'rose'],
  ]
  const tones = {
    emerald: 'bg-emerald-100 text-emerald-700',
    amber: 'bg-amber-100 text-amber-700',
    rose: 'bg-rose-100 text-rose-700',
  }
  return (
    <div className="rounded-[2rem] bg-slate-950 p-3 shadow-2xl shadow-slate-950/20">
      <div className="rounded-[1.45rem] bg-white p-5">
        <div className="flex items-center justify-between border-b pb-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-700">Análise técnica</p>
            <p className="mt-1 font-bold text-slate-900">48 requisitos identificados</p>
          </div>
          <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">Lote 03</span>
        </div>
        <div className="divide-y">
          {rows.map(([label, status, tone]) => (
            <div key={label} className="flex items-center justify-between gap-3 py-3">
              <span className="text-sm text-slate-600">{label}</span>
              <span className={`whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] font-bold ${tones[tone]}`}>{status}</span>
            </div>
          ))}
        </div>
        <div className="mt-3 rounded-2xl bg-blue-50 p-4">
          <p className="text-xs font-bold uppercase tracking-wide text-blue-700">Melhor compatibilidade</p>
          <p className="mt-1 font-bold text-slate-900">Produto Atlas Pro · 92%</p>
          <p className="mt-2 text-xs leading-5 text-slate-500">Evidências vinculadas ao edital e ao datasheet do produto.</p>
        </div>
      </div>
    </div>
  )
}

function CrmPreview() {
  return (
    <div className="rounded-[2rem] bg-slate-950 p-5 text-white shadow-2xl shadow-slate-950/20">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-300">CRM comercial</p>
          <p className="mt-1 font-bold">Pipeline de oportunidades</p>
        </div>
        <span className="rounded-full bg-white/10 px-3 py-1 text-xs text-slate-300">Visão da equipe</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          ['Triagem', ['Prefeitura de Santos', 'Hospital Regional']],
          ['Em análise', ['Universidade Federal', 'Secretaria de Saúde']],
          ['Disputa', ['Consórcio Municipal', 'Fundação Estadual']],
        ].map(([title, cards], columnIndex) => (
          <div key={title} className="rounded-2xl bg-white/[0.06] p-3">
            <div className="mb-3 flex items-center justify-between text-xs font-bold text-slate-300">
              <span>{title}</span><span>{cards.length}</span>
            </div>
            <div className="space-y-2">
              {cards.map((card, cardIndex) => (
                <div key={card} className="rounded-xl bg-white p-3 text-slate-900">
                  <p className="text-xs font-bold">{card}</p>
                  <div className="mt-3 h-1.5 rounded-full bg-slate-100">
                    <div className="h-full rounded-full bg-blue-600" style={{ width: `${48 + columnIndex * 17 + cardIndex * 8}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function OperationPreview() {
  return (
    <div className="rounded-[2rem] border border-slate-200 bg-white p-5 shadow-2xl shadow-blue-950/10">
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-700">Central de operação</p>
      <p className="mt-1 font-bold text-slate-900">Acompanhe o que precisa de atenção</p>
      <div className="mt-5 space-y-3">
        {[
          ['Análise do edital 104/2026', 'Processando', '72%', 'bg-blue-600'],
          ['Assinatura da declaração', 'Aguardando', '40%', 'bg-amber-500'],
          ['Relatório executivo mensal', 'Concluído', '100%', 'bg-emerald-500'],
        ].map(([title, status, progress, color]) => (
          <div key={title} className="rounded-2xl bg-slate-50 p-4">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-semibold text-slate-800">{title}</span>
              <span className="text-xs font-bold text-slate-500">{status}</span>
            </div>
            <div className="mt-3 h-2 rounded-full bg-slate-200">
              <div className={`h-full rounded-full ${color}`} style={{ width: progress }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function FeatureSection({ eyebrow, title, description, bullets, preview, reverse = false }) {
  return (
    <section className="border-b border-slate-100 py-20 sm:py-28">
      <div className={`mx-auto grid max-w-7xl items-center gap-12 px-6 lg:grid-cols-2 lg:gap-20 ${reverse ? 'lg:[&>*:first-child]:order-2' : ''}`}>
        <div>
          <p className="text-sm font-black uppercase tracking-[0.2em] text-blue-700">{eyebrow}</p>
          <h2 className="mt-4 text-3xl font-black tracking-tight text-slate-950 sm:text-5xl">{title}</h2>
          <p className="mt-5 max-w-xl text-lg leading-8 text-slate-600">{description}</p>
          <div className="mt-8 space-y-4">
            {bullets.map((bullet) => (
              <div key={bullet} className="flex items-start gap-3 text-slate-700"><CheckIcon /><span className="pt-0.5">{bullet}</span></div>
            ))}
          </div>
        </div>
        <div>{preview}</div>
      </div>
    </section>
  )
}

export default function Landing() {
  const { user } = useAuth()
  const market = useMarket()
  const productName = market?.app?.product_name || 'Edital Matcher'
  const appLink = user ? '/dashboard' : '/login'

  return (
    <div className="min-h-screen bg-white text-slate-900">
      <header className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/90 backdrop-blur-xl">
        <div className="mx-auto flex h-18 max-w-7xl items-center justify-between px-6 py-3">
          <Link to="/" className="flex items-center gap-3" aria-label={productName}>
            <ProductMark className="h-10 w-10" title={productName} />
            <div><p className="font-black tracking-tight">{productName}</p><p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">Inteligência para licitações</p></div>
          </Link>
          <nav className="hidden items-center gap-7 text-sm font-semibold text-slate-600 md:flex">
            <a href="#ciclo" className="hover:text-blue-700">Como funciona</a>
            <a href="#ferramentas" className="hover:text-blue-700">Ferramentas</a>
            <a href="#seguranca" className="hover:text-blue-700">Segurança</a>
            <a href="#duvidas" className="hover:text-blue-700">Dúvidas</a>
          </nav>
          <div className="flex items-center gap-2">
            {!user && <Link to="/login" className="hidden px-3 py-2 text-sm font-bold text-slate-700 sm:block">Entrar</Link>}
            <Link to={appLink} className="rounded-xl bg-blue-700 px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-blue-700/20 transition hover:bg-blue-800">
              {user ? 'Abrir plataforma' : 'Conhecer a plataforma'}
            </Link>
          </div>
        </div>
      </header>

      <main>
        <section className="relative overflow-hidden bg-gradient-to-b from-blue-50 via-white to-white pb-24 pt-20 sm:pt-28">
          <div className="absolute left-1/2 top-0 h-[520px] w-[820px] -translate-x-1/2 rounded-full bg-cyan-200/25 blur-3xl" />
          <div className="relative mx-auto grid max-w-7xl items-center gap-14 px-6 lg:grid-cols-[0.9fr_1.1fr]">
            <div>
              <span className="inline-flex rounded-full border border-blue-200 bg-white px-4 py-2 text-xs font-black uppercase tracking-[0.18em] text-blue-700">Da oportunidade ao resultado</span>
              <h1 className="mt-7 text-5xl font-black leading-[1.02] tracking-[-0.045em] text-slate-950 sm:text-6xl">Encontre, analise e opere licitações em um só lugar.</h1>
              <p className="mt-6 max-w-xl text-lg leading-8 text-slate-600">Uma plataforma para transformar editais em decisões claras, conectar análise técnica ao comercial e dar ritmo à operação da sua equipe.</p>
              <div className="mt-9 flex flex-wrap gap-3">
                <Link to={appLink} className="rounded-xl bg-blue-700 px-6 py-3.5 font-bold text-white shadow-xl shadow-blue-700/20 transition hover:-translate-y-0.5 hover:bg-blue-800">{user ? 'Ir para o painel' : 'Entrar na plataforma'}</Link>
                <a href="#ferramentas" className="rounded-xl border border-slate-300 bg-white px-6 py-3.5 font-bold text-slate-700 transition hover:border-blue-300 hover:text-blue-700">Ver ferramentas</a>
              </div>
              <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3 text-sm text-slate-500">
                <span>✓ Ambiente por empresa</span><span>✓ Decisão humana preservada</span><span>✓ Dados exportáveis</span>
              </div>
            </div>
            <RadarPreview />
          </div>
        </section>

        <section className="border-y border-slate-100 bg-white">
          <div className="mx-auto grid max-w-7xl gap-px bg-slate-100 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ['Uma visão', 'Radar, análise e operação conectados.'],
              ['Multiempresa', 'Cada organização em seu ambiente.'],
              ['Com evidências', 'Respostas ligadas aos documentos.'],
              ['Sob controle', 'A equipe confirma ações críticas.'],
            ].map(([title, text]) => <div key={title} className="bg-white px-6 py-7"><p className="font-black text-slate-900">{title}</p><p className="mt-1 text-sm text-slate-500">{text}</p></div>)}
          </div>
        </section>

        <section id="ciclo" className="bg-slate-950 py-24 text-white sm:py-28">
          <div className="mx-auto max-w-7xl px-6">
            <div className="max-w-3xl">
              <p className="text-sm font-black uppercase tracking-[0.2em] text-cyan-300">Ciclo completo</p>
              <h2 className="mt-4 text-3xl font-black tracking-tight sm:text-5xl">Menos ferramentas soltas. Mais continuidade entre as etapas.</h2>
              <p className="mt-5 text-lg leading-8 text-slate-300">A informação capturada no início acompanha a oportunidade até a decisão e a operação comercial.</p>
            </div>
            <div className="mt-14 grid gap-4 md:grid-cols-5">
              {journey.map(([number, title, text]) => (
                <div key={number} className="rounded-2xl border border-white/10 bg-white/[0.05] p-5">
                  <p className="text-xs font-black text-cyan-300">{number}</p><h3 className="mt-8 text-xl font-black">{title}</h3><p className="mt-3 text-sm leading-6 text-slate-400">{text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <FeatureSection eyebrow="Radar e decisão" title="Priorize o que merece a atenção da equipe." description="O radar organiza oportunidades e reúne sinais técnicos, comerciais, de prazo e de risco antes que o edital entre no funil." bullets={['Busca e monitoramento no PNCP', 'Score e prioridade por oportunidade', 'Decisão entre disputar, analisar ou descartar', 'Importação direta para a análise']} preview={<RadarPreview />} />
        <FeatureSection reverse eyebrow="Análise e matching" title="Saia do documento extenso para uma decisão explicável." description="Requisitos e itens são estruturados para comparar o edital com o catálogo, encontrar lacunas e manter a evidência acessível." bullets={['Requisitos e lotes estruturados', 'Matching técnico com produtos', 'Chat apoiado no conteúdo do edital', 'Comparação de datasheets e concorrentes']} preview={<AnalysisPreview />} />
        <FeatureSection eyebrow="CRM comercial" title="Leve a inteligência técnica para dentro do funil." description="A oportunidade não termina na leitura do edital. O CRM concentra acompanhamento, agenda, decisão e contexto para a equipe comercial." bullets={['Pipeline por etapa da oportunidade', 'Calendário, órgãos e portais', 'Histórico de decisões e resultados', 'Visão compartilhada entre áreas']} preview={<CrmPreview />} />
        <FeatureSection reverse eyebrow="Operação e governança" title="Acompanhe processamento, documentos e resultados." description="Tenha uma visão operacional do que está rodando, do que aguarda ação e do que já pode virar relatório para a gestão." bullets={['Fila e progresso dos processamentos', 'Documentos, versões e assinaturas', 'Relatórios executivos e operacionais', 'Exportações em PDF, XLSX e CSV']} preview={<OperationPreview />} />

        <section id="ferramentas" className="bg-slate-50 py-24 sm:py-28">
          <div className="mx-auto max-w-7xl px-6">
            <div className="max-w-3xl"><p className="text-sm font-black uppercase tracking-[0.2em] text-blue-700">Ferramentas disponíveis</p><h2 className="mt-4 text-3xl font-black tracking-tight text-slate-950 sm:text-5xl">O que já existe na plataforma hoje.</h2><p className="mt-5 text-lg leading-8 text-slate-600">Recursos conectados ao produto e à operação real do sistema.</p></div>
            <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {availableTools.map(([title, text]) => (
                <div key={title} className="rounded-2xl border border-slate-200 bg-white p-6 transition hover:-translate-y-1 hover:border-blue-200 hover:shadow-xl hover:shadow-blue-950/5">
                  <div className="flex items-center justify-between gap-3"><h3 className="font-black text-slate-900">{title}</h3><span className="rounded-full bg-emerald-100 px-2.5 py-1 text-[10px] font-black uppercase tracking-wide text-emerald-700">Disponível</span></div>
                  <p className="mt-3 text-sm leading-6 text-slate-500">{text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="py-24 sm:py-28">
          <div className="mx-auto max-w-7xl px-6">
            <div className="rounded-[2rem] border border-blue-100 bg-blue-50 p-8 sm:p-12">
              <div className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr]">
                <div><p className="text-sm font-black uppercase tracking-[0.2em] text-blue-700">Produto em evolução</p><h2 className="mt-4 text-3xl font-black tracking-tight text-slate-950">Próximos módulos da jornada.</h2><p className="mt-5 leading-7 text-slate-600">Estas frentes já fazem parte da visão do produto e estão em expansão. Elas aparecem separadas para deixar claro o estágio atual da plataforma.</p></div>
                <div className="grid gap-3 sm:grid-cols-2">
                  {expansionTools.map(([title, text]) => <div key={title} className="rounded-2xl bg-white p-5"><span className="text-[10px] font-black uppercase tracking-wide text-blue-600">Em expansão</span><h3 className="mt-2 font-black text-slate-900">{title}</h3><p className="mt-2 text-sm leading-6 text-slate-500">{text}</p></div>)}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="seguranca" className="bg-slate-950 py-24 text-white sm:py-28">
          <div className="mx-auto grid max-w-7xl items-center gap-12 px-6 lg:grid-cols-2">
            <div><p className="text-sm font-black uppercase tracking-[0.2em] text-cyan-300">Plataforma multiempresa</p><h2 className="mt-4 text-3xl font-black tracking-tight sm:text-5xl">Seu produto. O ambiente e os dados de cada cliente.</h2><p className="mt-5 max-w-xl text-lg leading-8 text-slate-300">A identidade principal é da plataforma. Empresas como a TOR usam seu próprio ambiente, com seus usuários, permissões e operação, sem se tornarem a marca do sistema.</p></div>
            <div className="grid gap-4 sm:grid-cols-2">
              {[
                ['Ambientes separados', 'Configuração e dados organizados por empresa.'],
                ['Papéis de acesso', 'Perfis administrativos, editores e usuários.'],
                ['Rastreabilidade', 'Histórico de documentos, decisões e processos.'],
                ['Controle humano', 'Ações críticas permanecem confirmadas pela equipe.'],
              ].map(([title, text]) => <div key={title} className="rounded-2xl border border-white/10 bg-white/[0.05] p-6"><h3 className="font-black">{title}</h3><p className="mt-2 text-sm leading-6 text-slate-400">{text}</p></div>)}
            </div>
          </div>
        </section>

        <section id="duvidas" className="py-24 sm:py-28">
          <div className="mx-auto max-w-4xl px-6">
            <div className="text-center"><p className="text-sm font-black uppercase tracking-[0.2em] text-blue-700">Dúvidas frequentes</p><h2 className="mt-4 text-3xl font-black tracking-tight text-slate-950 sm:text-5xl">Antes de entrar na plataforma.</h2></div>
            <div className="mt-12 divide-y divide-slate-200 border-y border-slate-200">
              {faqs.map(([question, answer]) => <details key={question} className="group py-5"><summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-black text-slate-900"><span>{question}</span><span className="text-2xl font-light text-blue-700 transition group-open:rotate-45">+</span></summary><p className="max-w-3xl pt-4 leading-7 text-slate-600">{answer}</p></details>)}
            </div>
          </div>
        </section>

        <section className="px-6 pb-24">
          <div className="mx-auto max-w-7xl overflow-hidden rounded-[2rem] bg-blue-700 px-8 py-14 text-center text-white shadow-2xl shadow-blue-800/20 sm:px-16 sm:py-20">
            <h2 className="text-3xl font-black tracking-tight sm:text-5xl">Transforme editais em decisões mais rápidas e organizadas.</h2>
            <p className="mx-auto mt-5 max-w-2xl text-lg leading-8 text-blue-100">Entre no ambiente da sua empresa para usar o radar, analisar oportunidades e acompanhar a operação.</p>
            <Link to={appLink} className="mt-8 inline-flex rounded-xl bg-white px-6 py-3.5 font-black text-blue-700 transition hover:-translate-y-0.5">{user ? 'Abrir meu painel' : 'Ir para o login'}</Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200 bg-white py-8">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3"><ProductMark className="h-8 w-8" title={productName} /><span className="font-bold text-slate-700">{productName}</span></div>
          <p>{market?.app?.footer_primary || 'Plataforma de inteligência para licitações.'}</p>
          <Link to="/login" className="font-bold text-blue-700">Acesso à plataforma</Link>
        </div>
      </footer>
    </div>
  )
}
