# CRM Design System - Especificacao de Implementacao do Layout

## Objetivo

Este documento transforma o manual visual do CRM em um plano de implementacao para atualizar o layout do sistema.

Ele deve orientar:

- onde implementar;
- em que ordem implementar;
- quais componentes criar ou padronizar;
- quais tokens visuais alterar;
- quais telas revisar;
- quais comportamentos preservar;
- quais criterios usar para aceitar a mudanca.

## Principio central

O redesign deve melhorar a leitura operacional sem alterar a logica principal do CRM.

Diretrizes obrigatorias:

- preservar as etapas atuais do pipeline;
- manter pipeline como macroestado do edital;
- tratar atividades intermediarias como acoes, status internos, checklists, tarefas ou alertas;
- manter modo claro e modo escuro;
- abrir edital em popup/modal sem perder contexto;
- manter dados existentes;
- reduzir excesso visual sem esconder informacoes importantes.

## Fonte tecnica do CRM

### Estrutura atual observada

O CRM e aberto pelo frontend principal em:

```text
frontend/src/pages/CrmHub.jsx
```

Esse arquivo redireciona o usuario para:

```text
/crm/index.html
```

O CRM servido atualmente esta em:

```text
frontend/public/crm
```

Os metadados de sincronizacao indicam que a fonte esperada do CRM e:

```text
bid-buddy
```

com build embarcado copiado por:

```text
scripts/sync-bid-buddy.mjs
```

### Regra de implementacao

A implementacao correta deve acontecer no codigo-fonte do CRM, dentro do projeto `bid-buddy`, e depois ser sincronizada para `frontend/public/crm`.

Fluxo ideal:

```text
1. Alterar fonte em bid-buddy
2. Rodar build embedado do CRM
3. Copiar build para frontend/public/crm
4. Testar CRM embarcado em /crm
5. Commitar fonte + build sincronizado conforme estrategia do repositorio
```

### Observacao importante

Na copia atual deste repositorio, a pasta `bid-buddy` esta vazia. Portanto, antes de implementar o redesign completo, e necessario restaurar ou acessar o codigo-fonte do CRM.

Edicoes diretas em arquivos compilados de `frontend/public/crm/assets` devem ser consideradas apenas hotfix temporario. Para redesign visual, isso nao e recomendado como caminho principal.

## Arquivos efetivos do CRM embarcado

Enquanto o CRM fonte nao estiver disponivel, os principais arquivos compilados que representam a superficie atual sao:

```text
frontend/public/crm/index.html
frontend/public/crm/assets/index-Ckk4Meuk.css
frontend/public/crm/assets/index-CZyHlYqJ.js
frontend/public/crm/assets/Notices-CrW0sitM.js
frontend/public/crm/assets/NoticesCalendar-sdZF7k8-.js
frontend/public/crm/assets/NoticeDetail-BTc0Mh-i.js
frontend/public/crm/assets/StageBadge-COaIdTs4.js
frontend/public/crm/assets/SuspendedNotices-ByXRG5zX.js
frontend/public/crm/assets/DiscardedNotices-BWaqikw-.js
frontend/public/crm/assets/Results-eexgG2tr.js
```

No codigo-fonte do `bid-buddy`, estes devem corresponder a telas e componentes como:

```text
Notices
NoticesCalendar
NoticeDetail
StageBadge
Layout / AppShell
Card
Button
Input
Select
Tabs
Dialog
Document rows
Item cards
```

## Escopo da primeira implementacao

### Entra no escopo

- tokens de tema claro e escuro;
- padronizacao visual de cards;
- padronizacao visual de colunas do pipeline;
- refinamento da barra de filtros;
- destaque de data no card;
- agrupamento visual das informacoes do card;
- separacao visual de riscos e pendencias;
- indicadores de documentos pendentes e assinatura pendente;
- melhoria do modal/popup do edital;
- reorganizacao visual da aba Informacoes;
- reorganizacao visual da aba Itens;
- reorganizacao visual da aba Documentacao;
- ajustes de calendario para manter contexto;
- criterios de hover, foco, loading e estado vazio.

### Fora do escopo inicial

- alterar etapas do pipeline;
- criar modulo completo de tarefas;
- criar central completa de notificacoes;
- criar algoritmo de prioridade;
- alterar regras comerciais;
- mudar modelo de dados sem necessidade;
- refatorar backend sem relacao direta com layout;
- criar relatorios e graficos.

## Ordem de implementacao

### Fase 1 - Base visual e tokens

Objetivo: melhorar a sensacao geral do sistema antes de mexer em cada tela.

Implementar:

- revisar variaveis CSS de tema claro;
- revisar variaveis CSS de tema escuro;
- reduzir excesso de escuridao no dark mode;
- aumentar hierarquia e contraste no light mode;
- padronizar radius maximo dos cards em 8px;
- reduzir sombras fortes em cards;
- manter sombra mais forte para modal/popup;
- criar tokens semanticos para status, risco, alerta e etapa.

Arquivos esperados no fonte:

```text
src/index.css
src/styles/globals.css
tailwind.config.*
src/lib/theme.*
```

Tokens minimos:

```text
--background
--foreground
--card
--card-foreground
--popover
--popover-foreground
--primary
--primary-foreground
--secondary
--secondary-foreground
--muted
--muted-foreground
--accent
--accent-foreground
--border
--input
--ring
--destructive
--success
--warning
--info
--stage-triage
--stage-analysis
--stage-documentation
--stage-proposal
--stage-auction
--stage-result
--radius
```

Recomendacao inicial para radius:

```text
--radius: 0.5rem
```

### Fase 2 - Componentes base

Objetivo: criar blocos reutilizaveis para evitar redesign inconsistente tela por tela.

Criar ou padronizar:

```text
CrmEntityCard
CrmMetric
CrmBadge
CrmAlertDot
CrmPriorityStars
CrmFilterBar
CrmPipelineColumn
CrmModalRecord
CrmSection
CrmEditableField
CrmItemGroup
CrmItemCard
CrmDocumentRow
CrmTimeline
```

Componentes existentes que podem ser reaproveitados:

```text
Card
Button
Badge
Input
Select
Tabs
Dialog
Tooltip
DropdownMenu
Checkbox
```

Regra:

Antes de redesenhar uma tela inteira, criar os componentes pequenos que serao usados nela.

### Fase 3 - Card de edital

Objetivo: deixar o card mais claro, compacto e orientado a decisao.

Implementar estrutura:

```text
Header
  Identificacao do edital
  Data do pregao
  Prioridade futura

Contexto
  Portal
  Municipio
  Orgao

Itens e valores
  Resumo de itens
  Valor total

Status e alertas
  Etapa atual
  Documentos pendentes
  Assinatura pendente
  Risco
  Pendencia anterior

Acoes
  Menu compacto
```

Regras:

- data sempre em `DD/MM/YYYY`;
- se nao houver data, mostrar `Sem data`;
- data deve aparecer mais visivel que hoje;
- risco deve ficar em bloco proprio;
- documentos pendentes devem aparecer como numero;
- assinatura pendente deve aparecer como alerta separado;
- prioridade deve ficar prevista no topo direito;
- responsavel do edital nao aparece por padrao;
- tarefas podem aparecer como indicador quando existirem.

Aceite:

- o usuario entende data, etapa e risco sem abrir o edital;
- o card continua compacto;
- informacoes de mesma natureza aparecem juntas;
- nenhuma informacao critica fica misturada em texto longo.

### Fase 4 - Pipeline

Objetivo: transformar o pipeline em uma area mais organizada e facil de operar.

Preservar:

- etapas atuais;
- drag-and-drop;
- acao de avancar;
- filtros atuais;
- ordenacao por data crescente;
- abertura de edital em popup/modal.

Implementar:

- coluna com header mais claro;
- contagem por etapa;
- cor sutil por etapa;
- largura estavel de coluna;
- cards com altura previsivel;
- estado vazio discreto;
- realce de drop target ao arrastar;
- area principal com scroll confortavel.

Aceite:

- cards podem ser movidos entre etapas permitidas;
- colunas nao pulam visualmente com hover ou loading;
- etapas pos-disputa continuam movimentaveis;
- usuario consegue voltar ao mesmo ponto depois de abrir popup.

### Fase 5 - Barra de filtros

Objetivo: reduzir atrito de busca e segmentacao.

Manter filtros:

- portal;
- cidade;
- termo;
- data;
- etapa;
- documentos;
- revisao;
- valor minimo;
- valor maximo.

Prever filtro futuro:

- prioridade.

Implementar:

- uma barra compacta;
- filtros ativos visiveis;
- limpar filtros sempre acessivel;
- atalhos de prazo;
- opcao `Sem data`;
- agrupamento de filtros por natureza quando a largura permitir.

Aceite:

- filtros cabem bem em tela grande;
- em tela menor, filtros quebram linha sem sobrepor;
- limpar filtros e sempre visivel;
- filtro por data nao esconde editais sem data quando `Sem data` esta ativo.

### Fase 6 - Modal do edital

Objetivo: permitir consulta e edicao sem perder contexto.

Implementar:

- popup/modal aberto a partir do pipeline e calendario;
- header fixo no modal;
- botao `Abrir em nova janela`;
- fechar claro e acessivel;
- conteudo do edital em area rolavel;
- preservacao de filtros, scroll e etapa de origem.

Layout recomendado:

```text
Header fixo
  Identificacao
  Data
  Status
  Acoes principais

Tabs
  Informacoes
  Itens
  Documentacao
  Historico
  Outras funcionalidades

Conteudo rolavel
```

Aceite:

- abrir e fechar edital nao recarrega o pipeline;
- filtros e ordenacao permanecem como estavam;
- modal funciona bem em desktop;
- botao de nova janela abre a pagina propria do edital.

### Fase 7 - Calendario

Objetivo: manter a visao por data, mas reduzir cliques.

Preservar:

- calendario mensal;
- lista lateral ao clicar em uma data;
- exibicao de preggoes e prazos pos-disputa.

Implementar:

- clique direto no edital abre popup;
- remover necessidade de selecionar e depois abrir;
- cards da lista lateral com data e contexto;
- indicadores de sessao principal, sessao adicional e prazo pos-disputa;
- mesma linguagem visual do card do pipeline.

Aceite:

- clique em edital abre popup;
- popup exibe pagina do edital;
- opcao de abrir em nova janela existe dentro do popup;
- usuario nao perde o dia selecionado.

## Detalhe do edital

### Fase 8 - Aba Informacoes

Objetivo: deixar a aba parecendo ficha operacional.

Implementar agrupamentos:

```text
Identificacao
Prazos
Orgao e localidade
Portal
Resumo e criterio
Riscos
Links e arquivos
Status operacional
```

Interacao:

- modo leitura por padrao;
- edicao campo a campo por icone;
- feedback de salvamento por campo;
- evitar botao geral de edicao;
- campos calculados permanecem somente leitura.

Aceite:

- a aba nao parece formulario bruto;
- dados importantes aparecem em blocos logicos;
- editar um campo nao exige ativar modo geral;
- usuario nao perde alteracao por esquecer de ligar edicao global.

### Fase 9 - Aba Itens

Objetivo: facilitar decisao sobre itens disputados.

Implementar:

- agrupamento por lote;
- itens em disputa primeiro;
- itens retirados separados em bloco discreto;
- bloco de retirados expansivel;
- acao de reabrir item retirado;
- valor unitario, quantidade e valor total;
- produto vinculado;
- alerta para item em disputa sem produto vinculado.

Layout recomendado:

```text
Lote
  Resumo do lote
  Itens em disputa
  Itens retirados
```

Aceite:

- fica claro o que esta em disputa;
- retirados ficam acessiveis, mas sem competir com itens ativos;
- valor total do item aparece;
- produto vinculado aparece perto do item.

### Fase 10 - Aba Documentacao

Objetivo: transformar a aba em checklist + biblioteca de arquivos.

Implementar:

- resumo documental no topo;
- grupos por categoria;
- linha de documento padronizada;
- status claro;
- documento anexado visivel;
- assinatura pendente como alerta proprio;
- acoes consistentes: selecionar, anexar, criar/upload, baixar, solicitar assinatura;
- confirmacao visual de documentos conferidos.

Layout recomendado:

```text
Resumo
  Conferidos
  Pendentes
  Assinaturas

Lista
  Status
  Documento
  Arquivo vinculado
  Validade
  Acoes
```

Aceite:

- documentos pendentes sao identificaveis rapidamente;
- assinatura pendente se destaca;
- acoes ficam proximas do documento certo;
- a tela nao vira uma lista pesada sem agrupamento.

### Fase 11 - Historico

Objetivo: melhorar rastreabilidade.

Implementar:

- timeline detalhada;
- eventos recentes primeiro;
- data, usuario, acao e detalhes;
- visual leve;
- filtros futuros por tipo de evento.

Aceite:

- historico permite entender o que aconteceu;
- eventos nao parecem uma tabela generica;
- texto de evento e objetivo.

## Regras visuais detalhadas

### Densidade

Usar densidade compacta, mas com grupos claros.

Regras:

- cards de edital devem ter padding entre 12px e 16px;
- metricas dentro de card podem usar 4px a 8px de gap;
- evitar blocos grandes de texto;
- limitar resumos a 2 linhas;
- usar tooltip para texto truncado importante;
- evitar card dentro de card.

### Tipografia

Regras:

- titulo de tela entre 20px e 24px;
- card usa 12px a 14px;
- labels pequenas podem usar 11px ou 12px;
- valores importantes usam peso 600;
- nao usar letter spacing negativo;
- uppercase somente para labels pequenas e consistentes.

### Icones

Regras:

- usar icones da mesma familia visual;
- icone + legenda curta para metricas recorrentes;
- tooltip quando o icone nao for obvio;
- nao usar icone sozinho para dado critico;
- tamanho padrao de 14px a 16px em cards.

Categorias sugeridas:

```text
Data
Portal
Municipio
Orgao
Valor
Documento
Assinatura
Risco
Tarefa
Prioridade
```

### Alertas

Alertas fortes:

```text
danger/warning badge
borda semantica
icone de alerta
texto curto
```

Alertas discretos:

```text
bolinha vermelha
exclamacao
tooltip obrigatorio
```

Nao misturar alerta forte com metadados comuns.

## Modelo de tokens proposto

### Tema claro

Direcao:

```text
background: neutro frio claro
card: branco ou quase branco
border: mais visivel que hoje
muted: legivel
accent: superficie levemente marcada
primary: azul institucional
```

Objetivo:

- deixar o modo claro menos insosso;
- dar mais presenca as superficies;
- manter leitura confortavel.

### Tema escuro

Direcao:

```text
background: cinza-azulado escuro, nao preto
card: um nivel acima do fundo
popover: mais destacado que card
border: discreta, mas visivel
muted: legivel
alertas: menos saturados
```

Objetivo:

- deixar o modo escuro menos pesado;
- criar camadas claras de superficie;
- reduzir cansaco visual.

## Dados necessarios e lacunas de implementacao

### Ja existe ou foi identificado no sistema

- data do pregao;
- portal;
- municipio;
- orgao;
- resumo de itens;
- itens;
- lote;
- quantidade;
- valor unitario de referencia;
- valor total de referencia por item;
- valor estimado;
- riscos;
- documentos;
- assinatura pendente;
- etapas atuais;
- etapas pos-disputa;
- calendario;
- modal de edital no calendario;
- acoes de avancar e arrastar.

### Ainda precisa ser modelado ou confirmado

- prioridade por estrelas;
- tarefas por edital;
- central de tarefas;
- central de notificacoes;
- regra para tarefa com prazo expirando;
- regra para analise tecnica atrasada;
- regra visual para etapa anterior nao concluida;
- criterio de quando `documentos conferidos` vira confirmacao geral;
- onde armazenar confirmacoes operacionais alem das tags atuais.

## Dependencias tecnicas provaveis

### Frontend

- React;
- Vite;
- Tailwind;
- lucide-react;
- componentes base ja existentes no CRM;
- biblioteca atual de drag-and-drop usada no pipeline.

### Backend/dados

Evitar alteracoes backend na primeira rodada visual.

Alterar backend apenas se for necessario para:

- trazer contagem de tarefas;
- trazer prioridade;
- trazer assinatura pendente agregada;
- trazer confirmacoes operacionais em campo proprio;
- expor alertas calculados.

## Estrategia para prioridade, tarefas e notificacoes

Como esses recursos ainda nao sao foco de implementacao completa, a primeira rodada deve prever espaco visual sem construir todo o modulo.

### Prioridade

Primeira rodada:

- reservar area no topo direito do card;
- criar componente visual `CrmPriorityStars`;
- deixar oculto ou vazio quando nao houver dado.

Implementacao futura:

- campo de prioridade manual;
- filtro por prioridade;
- algoritmo futuro de sugestao.

### Tarefas

Primeira rodada:

- prever indicador no card quando houver tarefa critica;
- nao criar central completa ainda.

Implementacao futura:

- tarefas dentro do edital;
- atribuicao a pessoa;
- prazo;
- status;
- observacoes;
- central de tarefas.

### Notificacoes

Primeira rodada:

- prever linguagem visual dos alertas;
- nao criar central completa ainda.

Implementacao futura:

- central de notificacoes;
- notificacoes geradas por tarefa, prazo, assinatura e atraso operacional.

## Plano de execucao recomendado

### Sprint visual 1

Entrega:

- tema claro refinado;
- tema escuro refinado;
- tokens semanticos;
- badges padronizados;
- metricas e alertas base.

Resultado esperado:

- sistema ja fica mais agradavel mesmo antes do redesign completo.

### Sprint visual 2

Entrega:

- novo card de edital;
- colunas do pipeline;
- barra de filtros;
- comportamento visual de drag-and-drop.

Resultado esperado:

- tela de Editais fica mais organizada e facil de escanear.

### Sprint visual 3

Entrega:

- popup/modal padronizado;
- calendario ajustado;
- abertura contextual do edital.

Resultado esperado:

- menos entrada e saida de tela;
- usuario preserva contexto.

### Sprint visual 4

Entrega:

- aba Informacoes reorganizada;
- edicao campo a campo;
- agrupamentos operacionais.

Resultado esperado:

- pagina do edital parece um registro de CRM, nao um formulario bruto.

### Sprint visual 5

Entrega:

- aba Itens reorganizada por lote;
- separacao de itens em disputa e retirados;
- valor total do item;
- alerta de item sem produto vinculado.

Resultado esperado:

- analise tecnica dos itens fica mais clara.

### Sprint visual 6

Entrega:

- aba Documentacao como checklist + biblioteca;
- assinatura pendente destacada;
- linhas de documentos padronizadas;
- resumo documental.

Resultado esperado:

- conferencia documental fica mais intuitiva.

## Criterios gerais de aceite

Uma mudanca visual so deve ser aceita se:

- melhora a leitura da data;
- melhora a leitura da etapa atual;
- separa risco de informacao comum;
- preserva a compacidade dos cards;
- agrupa dados semelhantes;
- nao remove informacao indispensavel;
- funciona em modo claro e escuro;
- nao quebra drag-and-drop;
- nao quebra avancar etapa;
- nao quebra abertura em popup;
- nao cria etapa nova desnecessaria no pipeline;
- nao obriga usuario a entrar e sair de telas sem necessidade.

## Checklist de QA visual

Testar em:

- tela grande de escritorio;
- notebook;
- largura menor simulada no navegador;
- modo claro;
- modo escuro.

Cenarios:

- pipeline com muitos editais;
- pipeline com coluna vazia;
- card com data;
- card sem data;
- card com data vencida;
- card com pregao nas proximas 24h;
- card com risco;
- card com documentos pendentes;
- card com assinatura pendente;
- edital em etapa pos-disputa;
- calendario com varios editais no mesmo dia;
- popup aberto a partir do pipeline;
- popup aberto a partir do calendario;
- aba Itens com lote;
- aba Itens com item retirado;
- aba Documentacao com documento sem arquivo;
- aba Documentacao com assinatura solicitada;
- historico com muitos eventos.

## Comandos de verificacao

Quando o fonte `bid-buddy` estiver disponivel:

```text
cd frontend
npm run build:crm
npm run build
```

Se houver servidor de desenvolvimento proprio do `bid-buddy`, usar tambem:

```text
cd bid-buddy
npm install
npm run dev
```

ou o comando equivalente existente no projeto.

## Entregaveis esperados ao final

Ao final da implementacao, devem existir:

- tokens revisados;
- componentes CRM padronizados;
- card de edital redesenhado;
- pipeline redesenhado;
- filtros mais claros;
- calendario com popup consistente;
- detalhe do edital mais organizado;
- aba Itens mais legivel;
- aba Documentacao mais intuitiva;
- guia de QA visual aplicado;
- build do CRM sincronizado em `frontend/public/crm`.

## Risco principal

O maior risco tecnico e implementar o redesign diretamente em assets compilados.

Isso pode funcionar para ajustes pequenos, mas dificulta manutencao, revisao, testes e futuras alteracoes.

Direcao recomendada:

```text
Restaurar fonte do bid-buddy
-> implementar no fonte
-> gerar build embedado
-> sincronizar para frontend/public/crm
```
