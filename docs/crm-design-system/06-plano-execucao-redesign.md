# CRM Design System - Plano de Execucao do Redesign

## Objetivo

Este arquivo e o checklist operacional do redesign do CRM.

Ele deve ser usado para acompanhar a implementacao sem precisar reconstruir o contexto pelo historico da conversa ou reler todos os documentos do design system.

## Status atual

Branch do repositorio principal:

```text
codex/crm-design-system-layout
```

Ultimo commit conhecido no repositorio principal:

```text
3d1ee1e
```

Branch do CRM fonte:

```text
codex/crm-layout-redesign
```

Ultimo commit conhecido no CRM fonte:

```text
771d663
```

Ambiente de validacao:

```text
http://127.0.0.1:8081/crm/editais?preview=1
```

Pull requests de acompanhamento:

```text
Repositorio principal: https://github.com/alvarosamp/RagMatchAvancado/pull/24
CRM fonte: https://github.com/LuizH-Paiva/bid-buddy/pull/4
```

Fluxo de implementacao:

```text
1. Alterar fonte em bid-buddy
2. Rodar npx tsc --noEmit em bid-buddy
3. Rodar npm run build:crm em frontend
4. Validar no preview /crm
5. Commitar bid-buddy
6. Commitar repositorio principal com o gitlink e build sincronizado
```

## Mudancas ja realizadas nesta conversa

### Funcionais do CRM

- [x] Padronizacao de datas nos cards de edital em formato `DD/MM/YYYY`.
- [x] Exibicao de `Sem data` quando o edital nao possui data cadastrada.
- [x] Data exibida tambem nas etapas a partir de julgamento, quando houver data cadastrada.
- [x] Cards de edital em etapas de julgamento em diante podem ser movimentados pelo pipeline.
- [x] Avanco de etapa dentro do edital funciona tambem para etapas de julgamento em diante.
- [x] Nomenclatura alinhada: o que aparecia como "processo" no card foi tratado como edital/oportunidade do funil.
- [x] Valor total de referencia por item adicionado no detalhe do edital.
- [x] Valor total de referencia do item calculado como valor de referencia unitario vezes quantidade, quando nao houver total explicito.
- [x] Valor total do item exposto na visualizacao dos itens.
- [x] Calendario ajustado para abrir edital em popup/modal ao clicar no edital.
- [x] Popup do calendario passou a ter opcao de abrir o edital em nova janela.
- [x] Fluxo de calendario preserva o contexto da data/lista lateral ao consultar um edital.

### Documentacao e direcao de produto

- [x] Analise da estrutura geral do CRM.
- [x] Identificacao de pontas soltas, incongruencias e informacoes faltantes.
- [x] Definicao do usuario principal: analista de editais de licitacao.
- [x] Definicao do objetivo operacional: funil de vendas para editais vindos do analisador.
- [x] Definicao das informacoes indispensaveis do card/detalhe: data do pregao, portal, municipio, resumo dos itens, orgao, alertas de risco, lista de itens, lote, preco dos itens, preco total e documentos pendentes.
- [x] Priorizacao definida como manual inicialmente, com possibilidade futura de ranking por estrelas.
- [x] Definicao de alertas fortes: data vencida, pregao nas proximas 24h, documento sem assinatura, analise tecnica atrasada, item sem produto vinculado, proposta nao cadastrada antes da disputa e tarefa com prazo expirando.
- [x] Definicao de tarefas e notificacoes como conceitos separados: tarefas atribuidas a pessoas e notificacoes geradas por tarefas ou eventos relevantes.
- [x] Decisao de manter modo claro e modo escuro.
- [x] Decisao visual registrada: modo claro precisa ter mais presenca; modo escuro precisa ser menos pesado.
- [x] Decisao de manter "Suspensos" como nomenclatura do setor.
- [x] Decisao de manter pipeline e calendario como duas visualizacoes dos mesmos dados.
- [x] Decisao de estabelecer Editais como modulo principal, com escolha de visualizacao por Pipeline ou Calendario.
- [x] Decisao de tratar ganhos e perdidos separados por abrirem caminho para modulo futuro de pos-venda/atas/pedidos/faturamento.
- [x] Criacao dos documentos de design system:
  - `01-estrategico-conceitual.md`
  - `02-tecnico-implementavel.md`
  - `03-guia-consolidado.md`
  - `04-manual-visual-layout.md`
  - `05-especificacao-implementacao-layout.md`
- [x] Revisao registrada: etapas atuais do pipeline devem ser preservadas; atividades intermediarias podem ser acoes, status, checklists, tarefas ou alertas.
- [x] Branch de trabalho separada criada para o redesign, evitando interferir diretamente na `main`.

### Redesign ja implementado

- [x] Rodada de ajustes do Pipeline apos revisao detalhada:
  - filtros principais simplificados para busca, datas, portal, prioridade e ordenacao por proximidade/recencia;
  - primeira faixa reservada a busca e datas, com campos de data de largura fixa ao estreitar a tela;
  - portal e prioridade organizados em uma segunda faixa;
  - atalhos de data mantidos na faixa inferior, com ordenacao e limpeza alinhadas ao canto direito;
  - filtro de etapa removido do painel principal de filtros;
  - filtro de cidade removido do painel principal de filtros;
  - estrelas de prioridade nos cards transformadas em controle clicavel;
  - prioridade passa a alimentar o filtro de prioridade;
  - avanco rapido permanece concentrado no menu de tres pontos do card.
- [x] Aba Itens: adotar a ficha operacional como padrao de detalhes.
  - separar preco LPU, minimo operacional editavel, referencia e totais;
  - calcular minimo de kits a partir dos componentes;
  - tornar o vinculo de catalogo visivel no resumo e estruturado dentro dos detalhes;
  - reduzir repeticoes de valores e metadados no card do item.
- [x] Tabela de disputa: reorganizar por edital e explicitar referencia, LPU, minimo operacional e totais.
  - remover o uso visual ambiguo de "preco catalogo";
  - suportar minimo editado e soma de kits;
  - garantir leitura responsiva e impressao operacional;
  - disponibilizar download compativel com Excel, alem de impressao/PDF.
- [x] Aba Informacoes redesenhada como ficha operacional.
- [x] Edicao campo a campo por icone, sem modo geral de edicao.
- [x] Icones de edicao discretos, aparecendo por hover/foco.
- [x] Valor total do item mantido na parte inferior dos cards de item.
- [x] Card do pipeline voltou a exibir resumo detalhado dos itens, priorizando os dois itens de maior valor total.
- [x] Resumo dos itens no card exibe quantidade, valor de referencia unitario e valor total.
- [x] Contador de itens restantes ajustado para refletir corretamente `+N itens`.
- [x] Produtos anexados ao mesmo item passaram a ser tratados visualmente como `Kit`, sem fragmentar a leitura do item principal no card.
- [x] Acoes do edital reorganizadas no topo.
- [x] "Suspender edital" movido para o menu de tres pontos.
- [x] "Enviar para pos-disputa" movido para o menu de tres pontos.
- [x] "Abrir tabela de disputa" com icone relacionado a disputa.
- [x] Analise tecnica com icone de ferramenta.
- [x] Aba Itens reorganizada por lote.
- [x] Itens em disputa aparecem primeiro.
- [x] Itens retirados ficam em bloco recolhivel.
- [x] Lote totalmente retirado aparece como linha compacta.
- [x] Item retirado mostra contexto suficiente para reabertura.
- [x] Alerta para item em disputa sem produto vinculado.
- [x] Correcao de rotulo duplicado de lote.
- [x] Cards do pipeline reorganizados em blocos compactos.
- [x] Data do card do pipeline mantida em `DD/MM/YYYY` e com mais destaque visual.
- [x] Contexto do edital agrupado no card: portal, cidade, orgao, valor e documentacao.
- [x] Resumo de itens do card transformado em bloco compacto.
- [x] Alertas fortes separados das informacoes comuns.
- [x] Indicador discreto para pendencias anteriores no topo do card.
- [x] Icones e nomenclaturas do card alinhados com a pagina do edital: agendamento/data, documentacao, analise tecnica, orgao e numero do pregao/licitacao.
- [x] Checagens operacionais do card padronizadas como icones compactos: Documentacao, Tecnica, Proposta e Habilitacao.
- [x] Estados de checagem padronizados: neutro/branco quando pendente e verde quando concluido.
- [x] `Proposta cadastrada` adicionada como checagem operacional oficial, junto de documentacao e analise tecnica.
- [x] `Habilitacao anexada` adicionada como checagem operacional oficial.
- [x] Pendencias anteriores do card passam a considerar proposta nao cadastrada e habilitacao nao anexada conforme a etapa do edital.
- [x] Prioridade por estrelas adicionada tambem ao cabecalho do edital, permitindo definir ou redefinir prioridade sem voltar ao pipeline.
- [x] Pipeline ajustado para abrir edital em popup sem sair da tela.
- [x] Popup do pipeline inclui opcao de abrir edital em nova janela.
- [x] Popup do pipeline carrega a pagina do edital em modo embutido, sem menu lateral esquerdo.
- [x] Popup do calendario tambem carrega a pagina do edital em modo embutido, sem menu lateral esquerdo.
- [x] Modo embutido do edital remove o botao "Voltar para o pipeline" para evitar navegacao interna no popup.
- [x] Menu de acoes do card alinhado com a pagina do edital: abrir agendamento do edital, abrir tabela de disputa, avancar etapa, marcar documentacao analisada, marcar analise tecnica realizada, enviar para pos-disputa, suspender edital, descartar, reabrir e excluir edital.
- [x] Tokens globais do modo claro e modo escuro revisados para dar mais presenca ao claro e suavizar o escuro.
- [x] Modulo Editais iniciou unificacao visual com cabecalho compartilhado e alternancia Pipeline/Calendario.
- [x] Calendario removido como item independente do menu lateral e tratado como visualizacao dentro de Editais.
- [x] Cards da lista lateral do Calendario unificados com o layout dos cards do Pipeline.
- [x] Filtros de Editais extraidos para painel e regra compartilhados entre Pipeline e Calendario.
- [x] Fonte de editais compartilhada entre Pipeline e Calendario por hook comum.
- [x] Filtros preservados na URL ao alternar entre Pipeline e Calendario.
- [x] Revisao visual inicial do Calendario: legenda enquadrada em superficie consistente, lista lateral sem card dentro de card e estado vazio padronizado.
- [x] Contagem dos filtros ajustada para singular/plural.

## Pausado para revisao posterior

- [ ] Aba Documentacao como checklist + biblioteca.

Motivo:

- a primeira proposta visual nao ficou adequada;
- antes de redesenhar novamente, e necessario detalhar melhor as regras de negocio e o fluxo real de documentacao.

## Proximos passos

### 1. Calendario com popup de edital

Objetivo:

- manter a experiencia ja iniciada no calendario: clicar no edital deve abrir popup, nao exigir selecionar e depois abrir.

Implementar:

- clique direto no edital abre popup;
- botao de abrir em nova janela dentro do popup;
- lista lateral fica mais limpa;
- cards da lista mostram data e contexto.

Criterios de aceite:

- usuario nao perde a data selecionada;
- fluxo fica mais direto;
- calendario e pipeline usam comportamento parecido para abrir edital.

### 2. Revisao de temas claro e escuro

Objetivo:

- deixar o modo claro menos insosso e o modo escuro menos pesado.

Implementar:

- revisar tokens de fundo, card, borda, texto secundario e acento;
- manter contraste adequado;
- evitar paleta monotematica;
- preservar leitura durante uso prolongado.

Criterios de aceite:

- modo claro tem mais presenca visual;
- modo escuro tem camadas mais suaves;
- cores semanticas continuam reconheciveis;
- o CRM parece mais agradavel para uso diario.

Status:

- aplicado e validado no preview;
- manter em observacao durante a revisao visual geral para ajustes finos de contraste e densidade.

### 3. Unificacao estrutural do modulo Editais

Objetivo:

- tratar Editais como modulo principal do CRM;
- permitir alternar entre visualizacao por Pipeline e visualizacao por Calendario dentro do mesmo modulo;
- reduzir duplicacao de regras, filtros, componentes, acoes e popups.

Implementar:

- criar uma estrutura comum para o modulo Editais;
- manter filtros compartilhados entre Pipeline e Calendario;
- manter o mesmo popup de edital nas duas visualizacoes;
- compartilhar nomenclaturas, icones, acoes e regras de card/evento;
- preservar URLs diretas para pipeline e calendario quando forem uteis.

Criterios de aceite:

- usuario entende que Pipeline e Calendario sao duas formas de ver os mesmos editais;
- filtros e acoes funcionam de forma consistente nas duas visualizacoes;
- abrir edital em popup nao faz o usuario perder o contexto da visualizacao atual;
- o codigo fica mais simples de manter por reduzir duplicacoes entre telas.

Status:

- concluido em primeira versao;
- cabecalho, alternancia de visualizacao, popup, cards da lista lateral, filtros, fonte de dados e regras de filtragem/sort foram compartilhados;
- filtros sao preservados na URL ao alternar entre Pipeline e Calendario;
- manter em observacao: volume real de editais no Calendario e necessidade futura de paginacao, carregamento por intervalo mensal ou filtro server-side.

### 4. Revisao visual geral

Objetivo:

- eliminar incongruencias deixadas pelas fases anteriores.

Checklist operacional:

- [x] 4.1. Base visual global
  - revisar tokens de cor ainda inconsistentes nos temas claro e escuro;
  - conferir contraste de textos, bordas, superficies, badges e alertas;
  - padronizar sombras, bordas, radius e densidade das superficies do CRM.

- [x] 4.2. Layout principal e navegacao
  - revisar menu lateral, cabecalho interno, largura maxima das telas e respiros;
  - reduzir arredondamentos exagerados onde nao combinam com o design system;
  - garantir que Editais, Suspensos, Resultados e demais modulos tenham estrutura visual coerente.

- [x] 4.3. Modulo Editais: cabecalho e alternancia de visualizacao
  - revisar cabecalho compartilhado de Editais;
  - validar botoes Pipeline/Calendario como selecao de visualizacao;
  - conferir se a descricao e as acoes do topo nao competem com os filtros.

- [x] 4.4. Filtros e controles operacionais
  - compactar o painel de filtros sem esconder informacoes importantes;
  - padronizar inputs, selects, botoes de preset, limpar filtros e contagem;
  - avaliar se filtros avancados devem ficar recolhiveis em uma segunda etapa.

- [x] 4.5. Pipeline e colunas
  - revisar altura minima, largura, cabecalho das colunas e estados vazios;
  - melhorar hierarquia visual dos contadores por etapa;
  - garantir boa leitura em tela grande sem desperdicar espaco.

- [x] 4.6. Card do edital no Pipeline e no Calendario
  - revisar densidade do card para ficar compacto sem ficar truncado demais;
  - conferir agrupamento de informacoes por contexto: prazo, portal/cidade/orgao, valor, documentacao, itens e alertas;
  - manter icones e nomenclaturas congruentes com a pagina do edital;
  - validar prioridade no topo direito como area reservada para ranking manual futuro.

- [x] 4.7. Calendario: estrutura visual inicial
  - legenda enquadrada em superficie consistente;
  - lista lateral sem card dentro de card;
  - estado vazio padronizado;
  - contagem dos filtros ajustada para singular/plural.

- [x] 4.8. Calendario: refinamento visual completo
  - revisar celulas do calendario, marcadores de evento, hierarquia de sessoes e prazos;
  - conferir como dias com muitos editais se comportam;
  - validar visualizacao em tela menor e em tela grande.

- [x] 4.9. Popup de edital
  - revisar tamanho, respiro, header, fechamento e botao de abrir em nova janela;
  - garantir que o modo embutido nao mostre menu lateral nem botao de voltar ao pipeline;
  - validar que a experiencia funciona igual saindo do Pipeline e do Calendario.

- [x] 4.10. Pagina do edital: cabecalho e acoes
  - revisar hierarquia do titulo, etapa, data, portal/orgao e acoes principais;
  - padronizar menu de tres pontos;
  - verificar se as acoes atuais tem nome, icone e posicao adequados.

- [x] 4.11. Aba Informacoes
  - revisar ficha operacional, agrupamentos, labels, campos editaveis e icones de edicao;
  - manter edicao campo a campo por icone;
  - conferir hover/foco dos icones de editar e acessibilidade por teclado.

- [x] 4.12. Aba Itens
  - revisar layout por lote, itens em disputa, itens retirados e total do item;
  - manter valor total na parte inferior do card;
  - deixar pendente a nova solucao para lotes totalmente retirados ate detalharmos melhor as regras de negocio.

- [x] 4.13. Aba Documentacao
  - revisar como mistura de checklist com biblioteca de arquivos;
  - garantir sinalizacao clara de documentos pendentes e assinatura solicitada;
  - manter como demanda futura o refinamento das regras especificas de fluxo documental.

- [x] 4.14. Abas internas restantes
  - revisar Historico, sessoes/agendamento, disputa, pos-disputa, resultados e abas em implementacao;
  - padronizar cabecalhos internos, tabelas, listas, formularios e estados vazios;
  - verificar nomenclaturas e icones.

- [x] 4.15. Botoes, icones, menus e tooltips
  - garantir que botoes de ferramenta usem icones consistentes;
  - incluir tooltips em icones que possam gerar duvida;
  - padronizar acoes primarias, secundarias, destrutivas e menus de tres pontos.

- [x] 4.16. Badges, alertas e status
  - diferenciar informacao comum, status operacional e alerta forte;
  - padronizar cores e pesos para risco, pendencia, vencimento, assinatura e tarefas;
  - evitar alertas vermelhos misturados com dados comuns.

- [x] 4.17. Estados vazios, loading e erro
  - padronizar mensagens de nenhum resultado, nenhum edital, sem documentos, sem itens e falhas de carregamento;
  - revisar loaders para nao parecerem desconectados do restante do layout;
  - garantir que estados vazios indiquem proximidade operacional sem virar texto explicativo longo.

- [x] 4.18. Responsividade e telas menores
  - validar Pipeline, Calendario, popup e pagina do edital em larguras menores;
  - garantir que textos nao estourem botoes, cards, abas ou filtros;
  - conferir scroll horizontal do pipeline e comportamento do popup.

- [x] 4.19. Acessibilidade basica
  - revisar foco visivel, aria-labels de botoes iconicos e navegacao por teclado;
  - conferir contraste dos estados de hover/focus;
  - garantir que tooltips nao sejam a unica forma de entender a acao;
  - revisar comportamento de foco e teclado na barra de abas, especialmente em telas menores.

- [x] 4.20. Revisao final de consistencia
  - percorrer telas principais do CRM em modo claro e escuro;
  - comparar Pipeline, Calendario e pagina do edital lado a lado;
  - atualizar checklist com excecoes e novas demandas encontradas;
  - validar build e preview antes do commit final da revisao.

Criterios de aceite:

- telas principais parecem pertencer ao mesmo sistema;
- informacoes importantes continuam acessiveis;
- interface fica mais fluida e organizada.

Status:

- Demanda de item composto registrada e tratada na tabela de disputa;
- quando um item original possui dois ou mais produtos vinculados, a tabela de disputa passa a exibir uma unica linha para o item original;
- produtos anexados ao item deixam de aparecer como subitens separados na tabela de disputa;
- valores operacionais de LPU/minimo sao somados por unidade e o total minimo usa a quantidade do item original;
- descricoes, marcas, modelos, SKUs e produtos do catalogo passam a ser expostos em conjunto na mesma linha operacional.
- Card do pipeline refinado para retomar o resumo operacional de itens:
  - os dois itens exibidos sao os de maior valor total;
  - cada item mostra quantidade, referencia unitaria e total;
  - itens com produtos anexados recebem identificacao visual como `Kit`;
  - contador `+N itens` passa a considerar os itens efetivamente exibidos.
- Checks operacionais refinados e ampliados:
  - Documentacao, Tecnica, Proposta e Habilitacao usam a mesma linguagem visual;
  - pendentes ficam neutros;
  - concluidos ficam verdes;
  - Proposta e Habilitacao podem ser marcadas dentro do edital e pelo menu do card.
- Prioridade por estrelas adicionada ao cabecalho do edital, preservando a mesma logica do card:
  - 1 estrela = baixa;
  - 2 estrelas = media;
  - 3 estrelas = alta;
  - clicar na estrela ativa remove a prioridade.
- Backend do resumo do card passou a priorizar os itens comercialmente mais relevantes, ordenando por valor total de referencia.
- PRs atualizadas:
  - `bid-buddy` PR #4 com commit `771d663`;
  - repositorio principal PR #24 com commit `3d1ee1e`.
- Item 4.13 concluido e validado no preview;
- Aba Documentacao reorganizada como checklist operacional por categoria, com resumo de conferidos, pendentes e assinaturas;
- cada documento passou a separar identificacao/status, arquivo vinculado e acoes de biblioteca em blocos proprios;
- assinatura pendente e documento sem arquivo ficaram sinalizados como atencao operacional sem se misturar com metadados comuns;
- categorias documentais principais receberam exibicao com nomenclatura normalizada.
- Item 4.18 concluido e validado no preview responsivo;
- cards do pipeline passaram a empilhar metricas e status em telas menores, preservando leitura sem esconder informacoes;
- acoes do card ficam visiveis em interfaces de toque e continuam discretas com hover/foco em telas maiores;
- filtros, cabecalho do modulo, calendario, popup e detalhe do edital foram ajustados para reduzir estouros e compressao visual;
- observacao para 4.19: revisar foco e navegacao por teclado nas abas depois da validacao visual;
- Item 4.19 concluido e validado no preview;
- calendario passou a anunciar data e quantidade de eventos para leitores de tela, com foco visivel nos dias e controles mensais rotulados;
- filtros, seletores e acoes iconograficas receberam rotulos acessiveis onde o texto visivel nao era suficiente;
- barra de abas usa navegacao manual: setas, Home e End movem o foco; Enter ou Espaco abre a aba; Page Up e Page Down preservam a rolagem da pagina;
- ao editar um campo, o foco segue para o controle de edicao e retorna ao botao ao concluir;
- popup do edital permite fechar com Esc mesmo com foco dentro da pagina incorporada e devolve o foco ao elemento que o abriu.
- Item 4.20 concluido e validado no preview;
- Pipeline, Calendario, detalhe do edital e popup foram conferidos em modo claro e escuro;
- filtros do modulo passaram a usar tres colunas em larguras de desktop com menu lateral, mantendo todos os valores legiveis; a grade completa fica reservada para telas muito largas;
- cabecalho do edital passou a distribuir suas metricas em duas linhas fora de telas muito largas, com orgao ocupando mais espaco para evitar truncamento desnecessario;
- build e verificacao de tipos concluidos; o lint continua com um erro e um aviso preexistentes em `src/lib/local-preview.ts` e `src/hooks/useCrmNotices.ts`, fora do escopo desta revisao.
- Item 4.17 concluido e validado no preview;
- componente reutilizavel EmptyState/LoadingState aplicado a pipeline, calendario, detalhe do edital, disputa, sessoes, concorrentes, match e resultados;
- estados vazios passaram a usar superficie, icone, titulo e descricao curta, preservando a proximidade operacional;
- loaders passaram a usar a mesma linguagem visual das superficies do CRM;
- Item 4.16 concluido e validado no preview;
- badges de etapa e resultado foram alinhados ao radius do design system;
- card do edital passou a separar alertas fortes de metadados de pos-disputa;
- alertas de data, risco de instalacao, assinatura pendente, documentos pendentes e direcionamento de marca foram padronizados por severidade;
- status do Match passou a usar tokens semanticos em vez de cores soltas;
- Item 4.15 concluido e validado no preview;
- botoes iconograficos revisados com descricoes por tooltip, title ou aria-label conforme o componente;
- acoes de sessao, concorrente, documento, links externos e remocao de item receberam rotulos mais claros;
- nomenclaturas visiveis remanescentes foram revisadas para manter acentos e linguagem consistente;
- Item 4.14 concluido e validado no preview;
- abas Sala de disputa, Match, Sessoes, Pos-disputa, Concorrentes e Historico receberam cabecalhos operacionais, superficies consistentes e revisao de nomenclaturas;
- Historico passou a ser exibido como timeline compacta;
- estado vazio de Pos-disputa foi alinhado com o padrao das demais abas;
- Item 4.12 concluido e validado no preview;
- Aba Itens recebeu revisao de nomenclaturas, acentos e consistencia visual dos cards de item;
- valor total do item permanece no rodape do card, como decisao preservada;
- itens retirados e lotes totalmente retirados seguem com a solucao atual; a nova solucao visual permanece como demanda separada ate detalhamento das regras de negocio;
- Item 4.11 concluido e validado no preview;
- Aba Informacoes refinada como ficha operacional com grupos mais leves, grid em ate tres colunas em telas largas e edicao campo a campo preservada por icone;
- labels revisados para manter nomenclatura mais consistente com card e cabecalho do edital;
- campos existentes mas pouco visiveis foram expostos: titulo/objeto e link da proposta do fornecedor;
- textos multilineares importantes deixam de ser cortados visualmente nesta aba;
- Item 4.10 concluido e validado no preview;
- cabecalho da pagina do edital reorganizado em identificacao, faixa de resumo operacional e acoes;
- altura do cabecalho reduzida mantendo informacoes importantes visiveis: numero, UASG, portal, localidade, orgao, sessao e valor total;
- acoes principais e marcadores de documentacao/analise tecnica ficaram visualmente separados, preservando tooltips e aria-labels;
- Lote 3 concluido e validado no preview;
- Calendario refinado com celulas mais legiveis, contagem de eventos por dia, ordenacao por horario e lista lateral mantendo o card compartilhado do edital;
- popup do edital refinado com header mais informativo, data em destaque, etapa/status e botao de abrir em nova janela;
- modo embutido conferido no popup sem menu lateral esquerdo e sem botao "Voltar para o pipeline";
- Lote 2 concluido e validado no preview;
- filtros, atalhos do funil, colunas e card compartilhado do edital revisados;
- diretriz reforcada: compactar sem esconder informacoes operacionais; tooltips podem complementar, mas nao substituir informacao essencial visivel;
- Lote 1 concluido e validado no preview;
- base visual global, layout principal, navegacao e cabecalho do modulo Editais revisados;
- Calendario recebeu ajustes de estrutura visual e consistencia de superficies;
- ainda falta revisar detalhe do edital, abas internas, botoes, tooltips, estados vazios e responsividade basica.

Demandas novas identificadas durante a revisao:

- [x] Ajustar a tabela de disputa para tratar produtos anexados como composicao do item original, sem criar subitens separados.
- [ ] Revisar a representacao visual de itens compostos na aba Itens e na Sala de disputa, garantindo que produto principal e produtos anexados fiquem claros sem poluir o card.
- [ ] Revisar a solucao visual dos itens retirados e lotes totalmente retirados apos detalhar regras de negocio e fluxo.
- [ ] Avaliar, nos proximos lotes, se algum componente ficou visualmente aglutinado apos a compactacao do Pipeline.

## Regras para atualizar este arquivo

- Marcar um item como concluido somente depois de validar no preview.
- Registrar decisoes novas que alterem a direcao do redesign.
- Manter os proximos passos em ordem operacional.
- Nao transformar este arquivo em documento conceitual longo; ele deve continuar pratico.

## Referencias internas

- `docs/crm-design-system/01-estrategico-conceitual.md`
- `docs/crm-design-system/02-tecnico-implementavel.md`
- `docs/crm-design-system/03-guia-consolidado.md`
- `docs/crm-design-system/04-manual-visual-layout.md`
- `docs/crm-design-system/05-especificacao-implementacao-layout.md`
