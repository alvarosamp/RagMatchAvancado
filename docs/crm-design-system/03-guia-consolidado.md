# CRM Design System - Guia Consolidado

## Visao curta

O CRM deve ser um cockpit operacional para analistas de licitacao. Ele precisa ajudar o usuario a entender rapidamente quais editais existem, em que etapa estao, quais exigem acao e quais riscos podem comprometer a participacao.

Direcao visual oficial:

```text
40% Atlassian
25% Salesforce
25% Carbon/IBM
10% Linear
```

Traducao pratica:

- pipeline claro e operacional;
- pagina de edital com estrutura de CRM;
- abas densas e bem organizadas para itens, documentos e resultados;
- visual mais agradavel, com temas claro e escuro refinados.

Diretrizes visuais detalhadas devem ser mantidas no documento `04-manual-visual-layout.md`. Este guia consolidado registra a decisao; o manual visual orienta a atualizacao pratica do layout.

A especificacao tecnica para executar a atualizacao do layout deve ficar no documento `05-especificacao-implementacao-layout.md`.

## Regras de produto

1. O usuario principal e o analista de editais.
2. A tela de Editais e o centro de decisao do funil.
3. Cards devem ser compactos, mas completos.
4. Informacoes parecidas devem ficar agrupadas.
5. Data, status, risco e pendencias precisam ser visiveis.
6. Editais devem abrir em popup/modal sem perder contexto.
7. Acoes atuais devem ser mantidas, com nomes ajustados quando necessario.
8. Prioridade por estrelas deve ser prevista como campo futuro.
9. Tarefas sao mais importantes que responsavel fixo do edital.
10. Notificacoes devem chamar atencao; tarefas devem organizar execucao.
11. As etapas atuais do pipeline devem ser mantidas; o fluxo operacional detalhado nao precisa virar coluna.

## Funil oficial

O funil abaixo descreve o fluxo operacional completo do edital. Ele orienta status, acoes, checklists, tarefas e alertas, mas nao significa que cada ponto deva existir como etapa separada no pipeline.

```text
Analisador
-> Triagem
-> Agendamento / classificacao inicial
-> Analise tecnica
-> Documentacao
-> Proposta
-> Disputa
-> Julgamento
-> Habilitacao
-> Adjudicacao
-> Homologacao
-> Resultado
```

Resultados finais:

- ganho;
- perdido;
- descartado.

Ganhos, perdidos e descartados devem ficar separados. Ganhos podem virar modulo proprio no futuro.

## Card de edital

### Composicao recomendada

```text
Topo
  ID / numero
  Data do pregao
  Prioridade futura

Contexto
  Portal
  Municipio
  Orgao

Itens
  Resumo
  Itens principais
  Lote quando houver

Valores
  Preco dos itens
  Preco total

Status operacional
  Etapa atual
  Docs pendentes
  Assinatura pendente
  Risco
  Pendencia anterior

Acoes
  Menu compacto
```

### Informacoes indispensaveis

- data do pregao;
- portal;
- municipio;
- orgao;
- resumo dos itens;
- lista de itens;
- lote do item, se houver;
- preco dos itens;
- preco total;
- riscos;
- documentos pendentes;
- assinatura pendente;
- prioridade futura.

### Regras visuais

- data deve ter destaque maior que hoje;
- se nao houver data, mostrar "Sem data";
- documentos pendentes aparecem como numero;
- assinatura pendente aparece como alerta proprio;
- risco fica em grupo separado;
- responsavel pelo edital nao precisa aparecer no card por padrao;
- usar icones com legenda curta.

## Alertas

### Alertas fortes

Usar alerta forte quando houver risco real de perda operacional:

- data do pregao vencida;
- pregao nas proximas 24h;
- documento sem assinatura;
- analise tecnica atrasada;
- item em disputa sem produto vinculado;
- proposta nao cadastrada antes da disputa;
- tarefa com prazo expirando.

### Alertas discretos

Usar alerta discreto para:

- etapa anterior nao concluida;
- documentos pendentes sem assinatura;
- informacao incompleta sem bloqueio imediato.

Padrao recomendado:

```text
bolinha vermelha + exclamacao + tooltip
```

## Abas do edital

### Informacoes

Objetivo: visao geral do edital.

Regras:

- manter dados atuais;
- reorganizar visualmente;
- nao parecer formulario bruto;
- abrir em modo leitura;
- editar campo por campo via icone;
- evitar modo de edicao geral.

### Itens

Objetivo: analise e decisao sobre o que sera disputado.

Regras:

- agrupar por lote;
- mostrar itens em disputa primeiro;
- separar itens fora da disputa;
- permitir consultar e reabrir retirados;
- usar cards compactos;
- mostrar quantidade, preco unitario, preco total, produto vinculado e riscos relevantes.

### Documentacao

Objetivo: controle documental.

Formato: checklist + biblioteca.

Regras:

- cada documento deve ter status claro;
- acoes intuitivas para anexar, selecionar, baixar, fazer upload e solicitar assinatura;
- assinatura pendente deve ser sinalizada com atencao;
- documentos conferidos devem ter confirmacao visual.

### Historico

Objetivo: rastreabilidade.

Formato: timeline detalhada.

Cada evento deve mostrar:

- data;
- usuario;
- acao;
- detalhes relevantes.

## Navegacao

Menu lateral deve ser reduzido e orientado por areas de trabalho.

Estrutura recomendada:

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

"Suspensos" deve continuar com esse nome, pois e nomenclatura do setor.

## Pipeline e calendario

### Pipeline

Regras:

- preservar as etapas atuais;
- representar macroestados do edital;
- manter microatividades como acoes internas do edital;
- ordenacao padrao por data crescente;
- cards mais proximos primeiro;
- drag-and-drop por etapa;
- popup para abrir edital;
- opcao de abrir em tela propria.

Atividades como agendar, classificar prioridade, conferir documentos, gerar proposta, solicitar assinatura, baixar arquivos e criar tarefa devem aparecer dentro do edital como acoes, status, checklists ou alertas.

### Calendario

Regras:

- dia selecionado abre lista lateral;
- clique no edital abre popup;
- popup mostra pagina do edital;
- popup tem botao "Abrir em nova janela";
- nao exigir selecionar e depois abrir.

## Filtros

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

- filtros devem ser compactos;
- limpar filtros deve estar sempre visivel;
- filtros por prazo devem ser rapidos;
- "Sem data" deve continuar existindo.

## Prioridade

Direcao futura:

- ranking por estrelas;
- insercao manual pelo usuario;
- filtro por prioridade;
- exibicao no topo direito do card;
- no futuro, sugestao automatica por algoritmo.

Nao detalhar criterios agora.

## Tarefas e notificacoes

### Tarefas

Tarefas pertencem a editais e sao atribuidas a pessoas.

Campos minimos:

- titulo;
- responsavel;
- prazo;
- status;
- observacoes;
- origem.

### Notificacoes

Notificacoes aparecem em central propria.

Podem ser geradas por:

- tarefas;
- prazos proximos;
- assinatura pendente;
- analise parada ha muito tempo;
- tarefa com prazo expirando.

## Temas

### Tema claro

Problema atual: insosso.

Direcao:

- mais hierarquia;
- superficies com mais presenca;
- bordas mais legiveis;
- fundo neutro levemente frio;
- cores semanticas bem aplicadas.

### Tema escuro

Problema atual: escuro demais.

Direcao:

- menos preto absoluto;
- mais camadas;
- texto secundario mais legivel;
- bordas discretas;
- status menos saturados.

## Componentes a criar ou padronizar

- `CrmEntityCard`
- `CrmMetric`
- `CrmBadge`
- `CrmAlertDot`
- `CrmModalRecord`
- `CrmPipelineColumn`
- `CrmItemCard`
- `CrmDocumentRow`
- `CrmTimeline`
- `CrmFilterBar`
- `CrmTaskIndicator`
- `CrmPriorityStars`

## Ordem recomendada de implementacao

1. Tokens de tema claro/escuro.
2. Badges, metricas e alertas.
3. Card de edital.
4. Pipeline com popup de edital.
5. Calendario com popup de edital.
6. Aba Informacoes em modo leitura com edicao pontual.
7. Aba Itens reorganizada por lote.
8. Aba Documentacao como checklist + biblioteca.
9. Timeline de historico.
10. Base futura de tarefas, notificacoes e prioridade.

## Checklist final

Antes de aplicar qualquer mudanca:

- O usuario entende a etapa atual?
- A data esta visivel?
- O card continua compacto?
- Informacoes semelhantes estao agrupadas?
- Riscos e pendencias nao estao misturados com contexto?
- Existe uma acao clara para o proximo passo?
- O usuario preserva contexto ao abrir edital?
- O modo claro ficou mais vivo?
- O modo escuro ficou menos pesado?
- A mudanca ajuda o analista a trabalhar melhor?
