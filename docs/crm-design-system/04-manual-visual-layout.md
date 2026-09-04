# CRM Design System - Manual Visual para Layout

## Objetivo

Este manual traduz as referencias visuais do CRM em diretrizes aplicaveis ao layout do sistema.

Ele deve orientar a atualizacao visual das telas, principalmente:

- pipeline de editais;
- calendario;
- cards de edital;
- modal/popup do edital;
- abas internas;
- itens;
- documentacao;
- alertas;
- filtros;
- temas claro e escuro.

## Mistura visual oficial

```text
40% Atlassian
25% Salesforce
25% Carbon/IBM
10% Linear
```

Esta mistura nao deve ser entendida como copia visual. Ela define o papel de cada referencia.

### Atlassian - 40%

Usar como base para:

- pipeline;
- colunas por etapa;
- cards arrastaveis;
- badges de status;
- pendencias;
- indicadores de bloqueio;
- fluxo operacional claro.

Direcao pratica:

- colunas bem separadas;
- headers de etapa com contagem;
- cards compactos;
- estados visuais simples;
- acoes proximas do contexto;
- alertas visiveis, mas sem poluir o card.

### Salesforce - 25%

Usar como base para:

- pagina do edital;
- organizacao do registro;
- historico;
- acoes por edital;
- visao de CRM;
- relacao entre dados, tarefas e proximos passos.

Direcao pratica:

- edital como registro central;
- topo com dados essenciais e acoes;
- abas internas claras;
- secoes bem agrupadas;
- atividade, historico e tarefas conectados ao edital;
- modal do edital como extensao natural do CRM.

### Carbon/IBM - 25%

Usar como base para:

- dados densos;
- tabelas;
- filtros;
- listas de itens;
- biblioteca de documentos;
- formularios tecnicos;
- organizacao de informacao complexa.

Direcao pratica:

- tabelas limpas;
- labels claros;
- hierarquia forte entre label e valor;
- estados de linha bem definidos;
- filtros objetivos;
- menos ornamentacao;
- informacao tecnica com boa legibilidade.

### Linear - 10%

Usar como base para:

- polimento visual;
- leveza;
- microinteracoes;
- espacamento;
- tipografia;
- refinamento dos temas claro e escuro.

Direcao pratica:

- superficies elegantes;
- contraste confortavel;
- bordas discretas;
- hover suave;
- componentes com acabamento refinado;
- interface produtiva, sem parecer pesada.

## Personalidade visual do CRM

O CRM deve parecer:

- organizado;
- confiavel;
- tecnico;
- operacional;
- agradavel para uso prolongado;
- rapido de escanear;
- calmo, mas nao apagado;
- produtivo, mas nao agressivo.

O CRM nao deve parecer:

- uma landing page;
- um painel decorativo;
- um formulario bruto;
- um Kanban generico;
- uma tabela sem hierarquia;
- um sistema escuro demais;
- um sistema claro sem contraste.

## Hierarquia visual geral

A interface deve sempre responder nesta ordem:

1. O que e este edital?
2. Qual e a data do pregao?
3. Em que macroetapa ele esta?
4. Existe risco forte?
5. Existe pendencia que exige atencao?
6. Quais itens e valores importam?
7. Qual e a proxima acao?

Essa hierarquia deve aparecer nos cards, no detalhe do edital e no calendario.

## Layout do CRM

### Estrutura geral

Usar uma composicao de trabalho, nao de apresentacao.

Padrao recomendado:

```text
Menu lateral
Topo da area atual
Barra de filtros e controles
Area principal
Modal ou drawer contextual quando necessario
```

### Menu lateral

Direcao:

- reduzir quantidade de itens;
- organizar por grandes areas;
- manter nomes usados pelo setor quando forem importantes;
- evitar duplicar visoes que podem ser filtros ou abas internas.

Itens recomendados:

```text
Editais
Catalogo
Documentacao
Inteligencia / Match
Resultados
Descartados
Administracao
```

Dentro de Editais:

```text
Pipeline
Calendario
Suspensos
```

Observacao: manter "Suspensos" como nomenclatura, pois e termo do setor.

## Pipeline

### Direcao visual

O pipeline deve funcionar como visao de macroestado.

Regras:

- preservar as etapas atuais;
- evitar criar coluna para cada acao operacional;
- usar colunas com largura estavel;
- ordenar cards por data crescente;
- tornar a data mais visivel;
- permitir arrastar cards entre etapas;
- permitir abrir edital em popup sem perder contexto;
- usar contagem por etapa no header.

### Colunas

Cada coluna deve ter:

- nome da etapa;
- contagem de editais;
- cor sutil da etapa;
- area de cards com scroll confortavel;
- estado vazio discreto.

Visual recomendado:

```text
Header da etapa
  Nome
  Quantidade
  Indicador de cor

Lista de cards
```

### Cores de etapa

As cores de etapa devem ajudar a reconhecer o fluxo, mas nao dominar a tela.

Direcao:

- fundo da coluna neutro;
- linha ou chip colorido no header;
- badge da etapa no card;
- baixa saturacao;
- contraste suficiente no claro e no escuro.

## Card de edital

### Papel do card

O card deve permitir triagem rapida sem abrir o edital.

Ele deve ser compacto, mas nao pobre. A solucao e agrupar informacoes por natureza, e nao tentar dar o mesmo peso para tudo.

### Estrutura recomendada

```text
Topo
  Numero / identificacao
  Data do pregao
  Prioridade futura

Contexto
  Portal
  Municipio
  Orgao

Itens e valores
  Resumo dos itens
  Valor total

Status e alertas
  Etapa atual
  Docs pendentes
  Assinatura pendente
  Risco

Acoes
  Menu compacto
```

### Regras de densidade

- limitar linhas longas;
- usar icones com legenda curta;
- truncar textos longos com tooltip;
- evitar blocos coloridos grandes;
- evitar badges demais;
- agrupar riscos em uma area propria;
- deixar o card respirando, mesmo compacto.

### Data

A data do pregao deve ser uma das informacoes mais visiveis do card.

Regras:

- sempre usar `DD/MM/YYYY`;
- se nao houver data, mostrar `Sem data`;
- data vencida usa alerta forte;
- pregao nas proximas 24h usa alerta forte;
- data comum deve ser visivel sem parecer alerta.

### Prioridade

A prioridade por estrelas deve ser prevista no topo direito.

Regras:

- inicialmente manual;
- nao ocupar espaco central antes de existir;
- servir como filtro futuro;
- nao competir visualmente com alerta de prazo.

### Alertas no card

Separar alertas de contexto comum.

Alertas fortes:

- data vencida;
- pregao nas proximas 24h;
- documento sem assinatura;
- analise tecnica atrasada;
- item em disputa sem produto vinculado;
- proposta nao cadastrada antes da disputa;
- tarefa com prazo expirando.

Alertas discretos:

- etapa anterior nao concluida;
- documentos pendentes sem assinatura;
- informacao incompleta sem bloqueio imediato.

Padrao visual:

```text
alerta forte = badge/chip danger ou warning
alerta discreto = bolinha vermelha com exclamacao + tooltip
```

## Modal ou popup do edital

### Objetivo

O usuario deve abrir, consultar e editar o edital sem perder o ponto em que estava no pipeline ou calendario.

### Regras

- abrir ao clicar no edital;
- exibir a pagina do edital ou componente equivalente;
- ter acao secundaria "Abrir em nova janela";
- permitir fechar com seguranca;
- preservar filtros, scroll e etapa de origem;
- evitar parecer uma tela reduzida quebrada.

### Layout do modal

```text
Header fixo
  Identificacao do edital
  Data
  Status
  Acoes principais

Abas
  Informacoes
  Itens
  Documentacao
  Historico
  Outras funcionalidades

Conteudo
  Area rolavel
```

## Aba Informacoes

### Direcao visual

Deve parecer uma ficha operacional, nao um formulario bruto.

Regras:

- abrir em modo leitura;
- agrupar dados por natureza;
- editar campo por campo via icone;
- mostrar feedback de salvamento;
- evitar botao geral de edicao;
- destacar prazo, portal, municipio, orgao, status e riscos.

### Agrupamentos sugeridos

```text
Identificacao
Prazos
Orgao e localidade
Portal
Dados do edital
Riscos e observacoes
Status operacional
```

## Aba Itens

### Direcao visual

Itens devem ser faceis de comparar e decidir.

Regras:

- agrupar por lote;
- mostrar itens em disputa primeiro;
- separar itens retirados em area discreta;
- permitir reabrir item retirado;
- destacar quantidade, valor unitario e valor total;
- mostrar produto vinculado;
- alertar item em disputa sem produto vinculado.

### Estrutura visual

```text
Lote
  Itens em disputa
    Item
    Quantidade
    Valor unitario
    Valor total
    Produto vinculado
    Status / alerta

  Itens retirados
    Lista discreta expansivel
```

## Aba Documentacao

### Direcao visual

A aba deve misturar checklist com biblioteca de arquivos.

Regras:

- status documental claro;
- separar documentos obrigatorios, anexados, pendentes e assinaturas;
- permitir selecionar existente, anexar, upload, baixar e solicitar assinatura;
- assinatura pendente deve ter alerta proprio;
- documentos conferidos devem ter confirmacao visual.

### Estrutura visual

```text
Resumo documental
  Conferidos
  Pendentes
  Assinaturas solicitadas

Lista de documentos
  Status
  Nome
  Origem
  Validade
  Acoes
```

## Aba Historico

### Direcao visual

Historico deve ser timeline detalhada.

Cada evento deve mostrar:

- data;
- usuario;
- acao;
- detalhe relevante;
- origem da alteracao quando fizer sentido.

Direcao:

- eventos recentes primeiro;
- filtros futuros por tipo;
- linguagem objetiva;
- evitar transformar historico em lista visualmente pesada.

## Filtros

### Direcao visual

Filtros devem ser compactos, persistentes e faceis de limpar.

Manter:

- portal;
- cidade;
- termo;
- data;
- etapa;
- documentos;
- revisao.

Adicionar no futuro:

- prioridade.

Regras:

- filtros em barra unica ou painel compacto;
- filtros ativos visiveis;
- botao de limpar sempre acessivel;
- filtros por prazo como atalhos rapidos;
- "Sem data" como opcao de filtro.

## Tabelas e listas

### Direcao visual

Usar Carbon/IBM como referencia principal para dados densos.

Regras:

- cabecalho claro;
- linhas com altura confortavel;
- acoes no final da linha;
- status perto do item que qualifica;
- valores alinhados;
- datas em formato consistente;
- vazios com texto simples e acao quando houver.

## Icones

### Direcao

Usar icones com legenda curta para facilitar leitura e reduzir peso visual.

Regras:

- icone nao substitui informacao critica sozinho;
- tooltip para icone menos obvio;
- manter familia visual unica;
- evitar excesso de icones no mesmo bloco;
- usar icones para categorias recorrentes: data, portal, municipio, orgao, valor, documentos, risco, tarefa.

## Temas

### Tema claro

Problema atual: visual insosso.

Direcao:

- fundo geral neutro levemente frio;
- cards com superficie clara e borda visivel;
- contraste melhor entre texto principal e secundario;
- badges com fundos suaves;
- headers com presenca sem ficar pesados;
- menos branco puro sem separacao.

### Tema escuro

Problema atual: escuro demais.

Direcao:

- evitar preto absoluto;
- criar camadas de superficie;
- cards ligeiramente mais claros que o fundo;
- colunas com diferenca perceptivel;
- texto secundario mais legivel;
- reduzir saturacao de alertas;
- manter bordas discretas.

## Tokens visuais recomendados

### Espacamento

```text
4px    micro ajustes
8px    espacamento interno compacto
12px   grupos dentro de card
16px   padding padrao de card/secao
24px   separacao entre blocos
```

### Radius

```text
4px    controles pequenos
6px    inputs, badges, filtros
8px    cards e modais compactos
```

### Bordas

Usar borda para separar superficies, principalmente no tema claro.

Regras:

- borda normal discreta;
- borda de hover levemente mais presente;
- borda de alerta por semantica;
- evitar depender apenas de sombra.

### Sombras

Usar pouco.

Regras:

- cards normais sem sombra forte;
- hover com sombra leve;
- modal com sombra clara de profundidade;
- alertas destacados por cor e borda.

## Microinteracoes

Direcao:

- hover discreto em cards;
- foco visivel para acessibilidade;
- feedback de salvamento por campo;
- drag-and-drop com indicacao clara de destino;
- carregamento com skeleton simples;
- transicoes curtas e suaves.

## Aplicacao por prioridade

Ordem recomendada para atualizar o layout:

1. Definir tokens de tema claro e escuro.
2. Padronizar badges, metricas, alertas e icones.
3. Redesenhar card de edital.
4. Redesenhar colunas do pipeline.
5. Padronizar modal/popup do edital.
6. Reorganizar aba Informacoes.
7. Reorganizar aba Itens.
8. Reorganizar aba Documentacao.
9. Ajustar calendario.
10. Refinar historico, tarefas e notificacoes.

As instrucoes operacionais de implementacao ficam detalhadas em `05-especificacao-implementacao-layout.md`.

## Checklist visual de revisao

Antes de aceitar uma tela:

- A data esta facil de encontrar?
- O status atual esta claro?
- Riscos estao separados de informacoes comuns?
- O card continua compacto?
- Informacoes parecidas estao agrupadas?
- O usuario consegue entender a proxima acao?
- O tema claro tem mais presenca?
- O tema escuro ficou menos pesado?
- O layout funciona para uso prolongado?
- A tela parece um CRM operacional de licitacoes?
