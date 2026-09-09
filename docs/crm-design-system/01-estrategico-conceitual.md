# CRM Design System - Documento Estrategico e Conceitual

## Proposito

Este documento define a direcao de produto e experiencia para o Design System do CRM de editais. O objetivo e criar uma experiencia mais fluida, clara e agradavel para analistas de licitacao que operam um funil de vendas a partir de editais importados por um analisador.

O CRM deve funcionar como um cockpit operacional de licitacoes: organizado, denso o suficiente para analise, mas leve o bastante para uso diario.

## Usuario principal

O usuario principal e um analista de editais de licitacao. Ele recebe editais vindos de um analisador, realiza triagem, valida viabilidade tecnica e comercial, organiza documentacao, prepara proposta, acompanha disputa, julgamento, habilitacao e resultado.

Ao abrir a tela de Editais, o usuario deve entender rapidamente:

- quais editais existem;
- em que etapa cada edital esta;
- quais exigem acao imediata;
- quais possuem riscos ou pendencias;
- quais possuem maior urgencia de prazo;
- quais informacoes sao necessarias para decidir o proximo passo.

## Direcao oficial de referencias

O Design System sera guiado pela seguinte mistura de referencias:

```text
40% Atlassian
25% Salesforce
25% Carbon/IBM
10% Linear
```

Interpretacao:

- Atlassian: pipeline, etapas, status, badges, pendencias e fluxo operacional.
- Salesforce: estrutura de CRM, pagina do edital, acoes por registro, historico e gestao do processo.
- Carbon/IBM: dados densos, tabelas, filtros, itens, documentacao, resultados e catalogo.
- Linear: polimento visual, leveza, tipografia, espacamento e refinamento dos temas claro/escuro.

## Principios de experiencia

### 1. Clareza operacional antes de decoracao

Cada tela deve responder uma pergunta operacional. O visual deve ajudar o usuario a decidir o que fazer, nao apenas apresentar dados.

### 2. Preservar contexto

Sempre que possivel, o usuario deve abrir e editar editais sem sair da tela atual. Pipeline e calendario devem permitir abertura de edital em popup, modal ou drawer, com opcao secundaria de abrir em tela propria.

### 3. Informacoes agrupadas por natureza

Informacoes parecidas devem ficar juntas. O card e o detalhe do edital devem separar identificacao, prazo, orgao/portal/local, itens, valores, riscos, pendencias e acoes.

### 4. Compacto, mas completo

Os cards nao devem parecer cheios demais. Ainda assim, as informacoes indispensaveis precisam estar presentes de forma organizada e escaneavel.

### 5. Status atual em primeiro plano

O usuario deve ver o estado atual do edital com facilidade. Etapas anteriores nao concluidas devem aparecer como alerta discreto, por exemplo uma bolinha vermelha com exclamacao e tooltip.

### 6. Alertas fortes so para risco operacional real

Alertas fortes devem indicar risco real de perda operacional, prazo ou execucao. Informacoes comuns devem usar visual neutro.

### 7. Edicao pontual, nao modo geral

A aba Informacoes deve abrir em modo leitura. Campos editaveis devem ter acao local de edicao por icone, com feedback claro de salvamento.

### 8. Tarefas movem trabalho; notificacoes chamam atencao

Tarefas devem ser criadas dentro de editais e atribuidas a pessoas. Notificacoes devem aparecer em uma central e podem ser geradas por tarefas, prazos, assinaturas pendentes ou etapas paradas por muito tempo.

### 9. Pipeline mostra macroestado; acoes mostram execucao

As etapas atuais do pipeline devem ser preservadas. O pipeline deve representar estados macro do edital, nao cada microatividade operacional. Atividades como agendar, classificar prioridade, conferir documentos, gerar proposta, baixar documentos, solicitar assinatura, registrar tarefa ou marcar uma confirmacao devem aparecer como acoes, checklists, status internos ou alertas dentro do edital.

## Funil operacional

O fluxo operacional ideal do edital e mais detalhado do que o pipeline visual. Ele descreve o trabalho real do analista, mas nem todas as atividades abaixo precisam virar uma etapa separada no pipeline.

```text
Chega do analisador
-> Triagem
-> Agendamento e classificacao inicial
-> Analise tecnica
-> Documentacao
-> Proposta
-> Disputa
-> Julgamento
-> Habilitacao
-> Adjudicacao
-> Homologacao
-> Ganho / Perdido / Descartado
```

Diretriz: o pipeline continua sendo uma visao executiva do estagio do edital. O detalhe do edital, suas abas, checklists, tarefas e alertas mostram o progresso operacional mais granular.

### Entrada do analisador

O edital chega ao CRM a partir de um analisador. O sistema deve preservar os dados extraidos e destacar o que precisa ser revisado por humanos.

### Triagem

O usuario realiza a primeira triagem e pode descartar editais com justificativa. Bases comuns de descarte:

- sem itens elegiveis;
- produtos identificados, mas sem condicao de competir;
- portais sem acesso;
- tipo de pregao inadequado;
- data passada.

### Agendamento e classificacao inicial

O usuario agenda a sessao/pregao e faz uma classificacao inicial. A classificacao pode ser alterada posteriormente.

### Analise tecnica

O usuario avalia itens, descarta itens inviaveis por caracteristicas tecnicas e vincula itens do catalogo aos itens que serao disputados. Ao concluir, marca analise tecnica como concluida.

### Documentacao

O usuario confere documentos, vincula documentos existentes na base, faz upload, baixa arquivos e solicita assinatura quando necessario. A etapa deve permitir marcar documentos conferidos.

### Proposta

O usuario gera a proposta pelo proprio sistema, usando dados extraidos pelo analisador. A proposta deve ser salva no computador e tambem no CRM, vinculada ao edital e aos documentos.

### Disputa

O usuario gera uma tabela de disputa com as informacoes necessarias para operar o pregao.

### Julgamento

O usuario avalia a proposta ofertada. Normalmente pode ser necessario enviar proposta readequada com os valores efetivamente vencedores da disputa.

### Habilitacao

O usuario envia ao orgao os documentos selecionados e elaborados. Os documentos devem poder ser selecionados e baixados a partir da aba Documentacao.

### Adjudicacao e homologacao

O usuario acompanha as etapas finais ate definicao do resultado.

### Ganhos, perdidos e descartados

Ganhos, perdidos e descartados devem permanecer separados, pois cada grupo tende a ter tratamento diferente no futuro. Ganhos podem evoluir para um modulo proprio com atas, pedidos, envio, faturamento e acompanhamento de execucao.

## Informacoes indispensaveis no card

O card de edital deve expor:

- data do pregao;
- portal;
- municipio;
- orgao;
- resumo dos itens;
- lista de itens;
- lote do item, se houver;
- preco dos itens;
- preco total;
- alertas de risco;
- documentos pendentes;
- assinatura pendente, quando houver;
- prioridade futura por estrelas.

## Prioridade

A prioridade deve ser prevista no Design System, mas nao detalhada neste momento.

Direcao inicial:

- ranking por estrelas;
- definido manualmente pelo usuario no inicio;
- no futuro, pode receber sugestao automatica por algoritmo;
- deve aparecer no topo direito do card;
- deve poder ser usada como filtro.

## Confirmacoes operacionais

As confirmacoes relevantes sao:

- Analise tecnica concluida;
- Documentos conferidos;
- Proposta cadastrada;
- Habilitacao enviada.

No card, deve aparecer principalmente o status atual. Etapas anteriores nao concluidas devem aparecer como alerta discreto.

## Alertas fortes

Devem gerar alerta forte:

- data do pregao vencida;
- pregao nas proximas 24h;
- documento sem assinatura;
- analise tecnica atrasada;
- item em disputa sem produto vinculado;
- proposta nao cadastrada antes da disputa;
- tarefa com prazo expirando.

## Navegacao

O menu lateral deve priorizar grandes areas de trabalho, nao cada recorte possivel dos editais.

Direcao sugerida:

```text
Editais
Catalogo
Documentacao
Inteligencia / Match
Resultados
Descartados
Administracao
```

Dentro de Editais, devem existir modos de visualizacao:

```text
Pipeline
Calendario
Suspensos
```

Observacao: "Suspensos" deve ser mantido como nomenclatura oficial por ser o termo utilizado no setor.

## Temas

O CRM deve manter modo claro e modo escuro.

O modo claro atual parece insosso; deve ganhar presenca, contraste e hierarquia. O modo escuro atual parece escuro demais; deve ganhar respiro, superficies mais bem separadas e contraste mais confortavel.

Direcao emocional dos temas:

- agradavel para uso prolongado;
- produtivo sem parecer agressivo;
- tranquilo sem parecer apagado;
- tecnico sem parecer frio demais.

## Criterios de sucesso

O redesign sera considerado bem-sucedido se:

- o CRM parecer mais agradavel e organizado;
- o usuario entender melhor o que fazer em seguida;
- houver menos necessidade de entrar e sair de telas;
- o usuario perder menos contexto ao consultar editais;
- os cards ficarem mais escaneaveis;
- itens e documentos ficarem mais faceis de analisar;
- riscos e pendencias ficarem visualmente separados;
- tarefas e notificacoes ajudarem a priorizar execucao.
