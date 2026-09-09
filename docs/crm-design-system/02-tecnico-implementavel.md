# CRM Design System - Documento Tecnico e Implementavel

## Objetivo

Este documento transforma as diretrizes de produto do CRM em especificacoes praticas para design e implementacao.

Ele deve orientar:

- tokens de design;
- componentes reutilizaveis;
- composicao dos cards;
- organizacao das abas;
- padroes de alertas;
- filtros;
- temas claro/escuro;
- futuras refatoracoes de frontend.

## Base visual

Proporcao de referencias:

```text
40% Atlassian
25% Salesforce
25% Carbon/IBM
10% Linear
```

Aplicacao:

- Pipeline: Atlassian.
- Detalhe do edital: Salesforce.
- Itens, documentacao, resultados e catalogo: Carbon/IBM.
- Polimento visual, temas e espacamento: Linear.

## Tokens

### Cores semanticas

Usar cores por significado, nao por preferencia decorativa.

```text
primary        Acao principal, link ativo, destaque moderado
neutral        Texto, borda, superficies e informacao comum
success        Concluido, ganho, validado
warning        Atencao, prazo proximo, pendencia relevante
danger         Risco forte, bloqueio, vencido, erro
info           Informacao auxiliar, status neutro ativo
muted          Dados secundarios, contexto, metadados
```

### Cores por etapa

Cada etapa deve ter cor propria, mas de baixa saturacao no fundo.

```text
triage          cor fria neutra
analysis        amarelo/ambar controlado
documentation   azul/ciano operacional
proposal        verde/teal moderado
auction         azul/indigo
judgment        violeta discreto ou azul profundo
qualification   ciano/teal
appeals         laranja controlado
adjudication    verde
homologation    verde/azul institucional
result          cinza/verde conforme resultado
suspended       warning
discarded       muted/danger discreto
```

### Tema claro

Direcao:

- fundo geral cinza muito claro ou levemente frio;
- cards brancos ou quase brancos;
- bordas mais presentes;
- headers com leve tint sem gradiente pesado;
- status com fundos suaves;
- texto secundario mais legivel que o atual.

### Tema escuro

Direcao:

- evitar preto absoluto;
- usar camadas de superficie;
- aumentar diferenciacao entre fundo, coluna e card;
- reduzir saturacao de cores fortes;
- manter texto secundario confortavel;
- bordas visiveis, mas discretas.

### Tipografia

Regras:

- titulos de tela: fortes, mas sem exagero;
- cards: texto compacto e escaneavel;
- labels: pequenas, uppercase apenas quando forem metadados;
- valores: peso medio/semibold;
- nao usar tamanho de hero em superficies operacionais;
- evitar excesso de tracking em informacoes longas.

### Espacamento

Base sugerida:

```text
4px    micro espacamento
8px    espacamento interno compacto
12px   espacamento de grupo
16px   card/section padding
24px   separacao entre blocos
```

### Bordas e radius

```text
radius-sm   4px
radius-md   6px
radius-lg   8px
```

Cards operacionais devem usar no maximo 8px de radius.

### Sombras

Usar sombra com parcimonia:

- card normal: sem sombra ou sombra minima;
- card hover: sombra leve;
- modal/drawer: sombra forte;
- alertas: destaque por cor/borda, nao por sombra.

## Componentes principais

### CrmEntityCard

Card base para edital.

Estrutura:

```text
Header
  Identificacao
  Data
  Prioridade futura

Contexto
  Portal
  Municipio
  Orgao

Itens e valores
  Resumo dos itens
  Itens principais
  Valor total

Status operacional
  Etapa atual
  Documentos pendentes
  Riscos
  Assinatura pendente
  Pendencia anterior

Acoes
  Menu compacto
```

Regras:

- card compacto;
- informacoes agrupadas;
- data mais visivel que hoje;
- prioridade no topo direito quando existir;
- responsavel pelo edital nao e dado central;
- tarefa atribuida pode aparecer como alerta/indicador.

### CrmMetric

Usado para dados como valor, quantidade, data, documentos pendentes.

Formato:

```text
icone + label curta + valor
```

Exemplos:

```text
Calendario  12/09/2026
Portal      BLL
Valor       R$ 120.000,00
Docs        3 pend.
```

### CrmBadge

Badges devem representar estados curtos.

Tipos:

```text
stage
status
risk
warning
success
muted
priority
```

Regras:

- badge nao deve carregar texto longo;
- risco forte usa danger;
- pendencia comum usa warning ou muted;
- status concluido usa success.

### CrmAlertDot

Indicador discreto para pendencia anterior.

Comportamento:

- bolinha vermelha com exclamacao;
- tooltip obrigatorio;
- nao substituir alerta forte;
- usado quando etapa anterior obrigatoria nao foi confirmada.

### CrmModalRecord

Modal para abrir o edital sem sair do contexto.

Regras:

- usado em pipeline e calendario;
- deve exibir a pagina real do edital ou componente equivalente;
- deve ter botao "Abrir em nova janela";
- deve ter botao claro de fechar;
- deve preservar o estado da tela de origem.

### CrmPipelineColumn

Coluna do pipeline.

Regras:

- header com nome da etapa, cor e quantidade;
- cards com densidade compacta;
- aceitar drag-and-drop;
- quando a coluna estiver vazia, mostrar estado vazio discreto;
- manter largura estavel.

### CrmItemCard

Card de item dentro do edital.

Regras:

- agrupado por lote;
- compacto, mas legivel;
- mostrar se esta em disputa ou fora da disputa;
- itens fora da disputa ficam separados em bloco discreto;
- deve permitir consultar e reabrir item retirado;
- mostrar valor de referencia unitario, quantidade e valor total;
- mostrar produto vinculado quando houver;
- sinalizar item em disputa sem produto vinculado.

### CrmDocumentRow

Linha de documento.

Regras:

- mistura de checklist com biblioteca de arquivos;
- mostrar status, nome, origem, validade e acoes;
- acoes: anexar, baixar, upload, selecionar existente, solicitar assinatura;
- assinatura pendente deve ter alerta proprio.

### CrmTimeline

Historico detalhado.

Regras:

- formato timeline;
- ordenacao cronologica reversa por padrao;
- eventos com data, usuario, acao e detalhes;
- filtros futuros por tipo de evento.

## Card de edital - especificacao proposta

### Header

Conteudo:

- numero/ID do edital;
- data do pregao em DD/MM/YYYY;
- prioridade futura por estrelas no topo direito.

Regra:

- data deve ser mais evidente que hoje;
- se sem data, exibir "Sem data";
- data vencida ou proximas 24h deve gerar alerta forte.

### Contexto institucional

Conteudo:

- portal;
- municipio;
- orgao.

Formato:

- icone + label curta;
- duas linhas no maximo;
- orgao pode truncar com tooltip.

### Itens e valores

Conteudo:

- resumo dos itens;
- itens principais;
- lote quando houver;
- preco dos itens;
- preco total.

Formato:

- mostrar no maximo os principais itens;
- indicar "+N itens" quando houver muitos;
- valor total alinhado e com destaque moderado.

### Status operacional

Conteudo:

- etapa atual;
- documentos pendentes como numero;
- assinatura pendente como alerta separado;
- risco tecnico/documental/comercial;
- pendencia anterior por bolinha vermelha com exclamacao.

Regra:

- risco nao deve ficar misturado com informacoes de contexto;
- documentos pendentes nao devem listar nomes no card;
- assinatura pendente merece mais destaque que pendencia comum.

### Acoes

Manter acoes atuais, ajustando nomes quando necessario.

Exemplos:

- abrir edital;
- avancar;
- agendamento;
- enviar para pos-disputa;
- marcar analise tecnica;
- marcar documentacao;
- descartar;
- reabrir;
- excluir quando permitido.

## Filtros

Filtros atuais a manter:

- portal;
- cidade;
- termo/busca textual;
- data;
- etapa;
- documentos;
- revisao.

Filtro futuro:

- prioridade.

Regras:

- filtros devem ficar agrupados em linha de controle compacta;
- filtros rapidos por prazo devem continuar;
- "Sem data" deve permanecer como filtro;
- limpar filtros deve ser sempre visivel.

## Tela Editais

Visualizacoes:

- Pipeline;
- Calendario;
- Suspensos.

Pipeline e calendario mostram os mesmos dados em formatos diferentes.

Regras:

- preservar as etapas atuais do pipeline;
- tratar o pipeline como macroestado do edital;
- nao transformar toda acao operacional em coluna;
- manter atividades intermediarias como acoes, checklists, status internos, tarefas ou alertas;
- abrir edital em popup/modal sem perder contexto;
- opcao de abrir em tela propria;
- ordenacao padrao por data crescente;
- cards mais proximos aparecem primeiro;
- data deve ser mais visivel.

Exemplos de atividades que nao precisam ser etapa propria no pipeline:

- agendar;
- classificar prioridade;
- conferir documentos;
- gerar proposta;
- baixar documentos;
- solicitar assinatura;
- registrar tarefa;
- marcar confirmacao operacional.

## Tela Calendario

Regras:

- clique no dia abre lista lateral;
- clique no edital da lista abre popup;
- popup exibe a pagina do edital;
- popup tem opcao "Abrir em nova janela";
- nao exigir selecionar e depois clicar em abrir.

## Detalhe do edital

### Aba Informacoes

Direcao:

- preservar dados existentes;
- melhorar apresentacao;
- parecer ficha operacional, nao formulario bruto.

Interacao:

- modo leitura por padrao;
- edicao pontual por campo;
- icone discreto de editar;
- feedback de salvamento;
- evitar modo de edicao geral.

### Aba Itens

Direcao:

- agrupamento por lote;
- itens em disputa primeiro;
- itens retirados separados e discretos;
- permitir consultar e reabrir retirados;
- informacoes organizadas por blocos.

Campos relevantes:

- item;
- lote;
- descricao/resumo;
- quantidade;
- unidade;
- valor de referencia unitario;
- valor de referencia total;
- produto vinculado;
- status em disputa / fora da disputa;
- riscos ou observacoes relevantes.

### Aba Documentacao

Direcao:

- mistura de checklist com biblioteca de arquivos.

Funcoes:

- selecionar documento existente;
- anexar;
- baixar;
- upload;
- solicitar assinatura;
- marcar conferido;
- indicar assinatura pendente.

### Aba Historico

Direcao:

- timeline detalhada;
- rastreabilidade de acoes;
- mostrar usuario, data, acao e detalhes.

## Alertas

### Alertas fortes

Usar danger/warning forte para:

- data do pregao vencida;
- pregao nas proximas 24h;
- documento sem assinatura;
- analise tecnica atrasada;
- item em disputa sem produto vinculado;
- proposta nao cadastrada antes da disputa;
- tarefa com prazo expirando.

### Pendencias comuns

Usar indicador discreto para:

- documentos pendentes por quantidade;
- etapa anterior nao confirmada;
- informacao incompleta que nao bloqueia fluxo.

## Notificacoes e tarefas

### Notificacoes

Central de notificacoes.

Fontes:

- tarefa atribuida;
- prazo proximo;
- assinatura pendente;
- analise parada ha muito tempo;
- tarefa com prazo expirando.

### Tarefas

Criadas dentro de cada edital.

Campos minimos:

- titulo;
- descricao;
- responsavel;
- prazo;
- status;
- observacoes;
- origem;
- link para edital.

Tarefas podem gerar notificacoes.

## Resultados e descartados

Manter separados.

Motivo:

- ganhos, perdidos e descartados terao tratamentos operacionais diferentes;
- ganhos podem evoluir para modulo de atas, pedidos, envio, faturamento e execucao.

## Checklist de aplicacao

Antes de aceitar uma tela ou componente:

- A informacao principal aparece sem abrir o edital?
- A data esta visivel?
- O status atual esta claro?
- Riscos e pendencias estao separados do restante?
- O usuario entende o proximo passo?
- O layout continua compacto?
- Os dados semelhantes estao agrupados?
- O tema claro tem presenca?
- O tema escuro tem respiro?
- O usuario consegue abrir detalhe sem perder contexto?
