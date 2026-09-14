# CRM - Backlog Imediato

Atualizado em 14/09/2026.

Este arquivo e a fila curta de trabalho do CRM. O plano de execucao (`06-plano-execucao-redesign.md`) mantem o historico, as decisoes e o roadmap completo; este backlog concentra somente as proximas acoes para evitar reler o documento inteiro em cada ciclo.

## Proximo ciclo de implementacao

- [x] Implementar encerramento explicito do edital.
  - Adicionar a acao `Encerrar edital` no menu de acoes do edital, com historico, confirmacao e resumo dos resultados por item.
  - Enquanto o edital estiver antes de Homologacao, permitir apenas a classificacao final `Cancelado`, com motivo obrigatorio.
  - Em Homologacao, permitir `Ganho`, `Perdido` ou `Cancelado`; Ganho deve permanecer Ganho mesmo quando apenas parte dos itens foi vencida.
  - Preservar resultados por item e usar o encerramento como unica acao que retira o edital do Pipeline e o envia para Resultados/Encerrados.
  - Manter uma unica tela de Resultados, com filtros para Ganho, Perdido e Cancelado.
  - Manter `Descartado` como decisao interna de Triagem na area separada Editais descartados; `Cancelado` representa encerramento externo de edital que entrou no fluxo e aparece em Resultados.
  - Tratar `Desclassificado` como estado provisório de item durante Julgamento ou Habilitacao; o edital permanece pendente e so pode ser encerrado como Perdido apos Homologacao.
  - Adicionar `Reabrir edital` em Resultados: exigir motivo, limpar a classificacao final, preservar os resultados por item e retornar o edital para Homologacao.
  - Permitir encerrar e reabrir a qualquer usuario com permissao de edicao.
  - Exigir resultado registrado para todos os itens ainda em disputa antes de permitir Ganho ou Perdido em Homologacao.
  - Solicitar motivo em texto livre para Cancelado e para Reabrir edital.
  - Implementado em 14/09/2026: encerramento, reabertura, validacoes de fase/itens, historico, filtros de Resultados e preview local.

- [x] Corrigir a continuidade do edital apos o Pregao.
  - O resultado de um item e uma informacao operacional da disputa; ele nao pode encerrar o edital nem desloca-lo automaticamente para `Resultados`.
  - Manter o edital no pipeline apos registrar itens vencidos, perdidos ou desclassificados, permitindo concluir Julgamento, Habilitacao, Recursos e contrarrazoes, Adjudicacao e Homologacao.
  - Definir o resultado geral do edital somente por encerramento explicito apos Homologacao, ou por uma regra futura aprovada para encerramento antecipado.
  - Corrigir o botao `Avancar etapa` para realizar `Pregao -> Julgamento`; hoje o frontend interpreta Pregao como a ultima etapa antes de chamar o backend.
  - Validar o mesmo comportamento por botao e por arrastar o card no Pipeline, incluindo edital com item ja marcado como vencido.
  - Implementado em 14/09/2026 nos commits `b1b9c02` (frontend) e `9bd1fac` (backend).

- [ ] Consolidar campos tecnicos dinamicos do BI na aba Itens.
  - Criar chaves canonicas para atributos recorrentes, incluindo Wi-Fi, portas, gerenciamento, PoE, uplink, camada e velocidade.
  - Priorizar fontes: campo estruturado do item, `bi_features`, `raw_payload` e inferencia tecnica.
  - Exibir uma unica caracteristica por conceito; quando houver conflito, manter o valor principal e tornar a divergencia consultavel.
  - Validar com dados que hoje repetem informacoes, como `Wi-Fi` e `Tecnologia Wi-Fi`.

- [ ] Validar com dados reais o fluxo de composicao de catalogo na aba Itens.
  - Tratar o item importado do edital como entidade principal: ele conserva numero, lote, descricao, quantidade, preco de referencia, situacao na disputa e resultado.
  - Tratar um ou mais produtos do catalogo como composicao do item. Dois ou mais produtos representam obrigatoriamente um Kit, isto e, componentes de uma unica solucao vendida em conjunto.
  - Substituir os caminhos separados de "Vincular a produto do catalogo" e "Anexar outro item" por uma unica acao orientada ao usuario: `Vincular produtos do catalogo`, com selecao de um ou mais produtos antes da confirmacao.
  - Reservar a criacao de item sem origem no edital para uma acao excepcional e explicitamente nomeada `Adicionar item manual`; ela nao deve concorrer com o fluxo normal de analise dos itens importados.
  - Exibir a composicao no proprio item, de forma compacta: produto, marca/modelo, SKU quando existir e Preco LPU individual. Componentes nao aparecem como itens, subitens ou linhas comerciais independentes.
  - Permitir adicionar, substituir ou remover componentes sem alterar a quantidade, a referencia ou a identidade do item do edital.
  - Para Kit, resolver o Minimo unitario por `Manual > soma das LPUs dos componentes > Referencia`. O Minimo total e o minimo unitario resolvido multiplicado pela quantidade original.
  - Quando faltar LPU em qualquer componente do Kit, nao somar valores parciais: sinalizar composicao incompleta e exigir minimo unitario manual ou a regularizacao da LPU faltante.
  - Validar os cenarios: sem vinculo, vinculo simples, Kit com LPUs diferentes, componente sem LPU, minimo manual, remocao de componente e criacao excepcional de item manual.
  - Implementado no frontend em 14/09/2026: seletor multiplo unico, composicao editavel, criacao excepcional de item manual, calculo de minimo de Kit e alerta para LPU incompleta. A validacao manual permanece pendente porque o catalogo do preview atual nao possui produtos ativos.

- [ ] Separar com mais clareza analise de itens e resultado da disputa.
  - A aba Itens ainda apresenta o resumo "Resultado por item" antes da analise operacional.
  - Definir se o resumo de ganho/perda deve migrar para Pos-disputa/Resultados ou ficar como bloco secundario e recolhivel.

- [ ] Consolidar componentes-base do Design System.
  - Formalizar contratos reutilizaveis para card de entidade, metrica, alerta, linha de item, linha documental, filtro e timeline.
  - Reduzir diferencas visuais entre Pipeline, Calendario e abas internas antes de novos redesenhos.

## Aguardando detalhamento de regra de negocio

- [ ] Reclassificar editais deslocados para Resultados pela regra anterior.
  - Identificar editais em `Resultado` sem fase pos-disputa, cujo resultado geral foi derivado de itens e que ainda precisam percorrer o fluxo administrativo.
  - A reclassificacao deve ser assistida ou confirmada pelo usuario; nao mover automaticamente editais historicos que possam estar realmente encerrados.

- [ ] Substituir os dados empresariais fixos do gerador de documentos por um cadastro de empresa por tenant.
  - O dialogo de geracao ja utiliza somente Modelo, Assinante e a justificativa quando o modelo for Declaracao de Exequibilidade.
  - Dados da empresa, edital e assinante devem ser preenchidos automaticamente; valores empresariais nao devem ficar fixos no codigo quando houver suporte a multiplas empresas.

- [ ] Redesenhar itens retirados e lotes totalmente retirados.
  - A solucao atual permanece por enquanto.
  - Definir antes de alterar: motivo da retirada, criterios de reabertura, quem pode reabrir, impacto no resultado e no retorno a disputa.

- [ ] Refinar a aba Documentacao como checklist e biblioteca de arquivos.
  - Mapear categorias, dependencias entre documentos, assinatura solicitada e estados de conferencia antes de mexer novamente no layout.

- [ ] Revisar a arquitetura de navegacao lateral.
  - Agrupar areas administrativas e de apoio para reduzir a lista plana atual.
  - Preservar Editais como centro operacional, com Pipeline, Calendario e Suspensos como visualizacoes relacionadas.

## Acompanhar em uso real

- [ ] Observar a compactacao do Pipeline com editais reais e registrar qualquer informacao operacional que tenha ficado escondida ou excessivamente aglutinada.
- [ ] Verificar se os filtros atuais precisam expor prioridade quando a classificacao por estrelas passar a ser usada de forma recorrente.
- [ ] Validar temas claro e escuro com editais reais, por uso prolongado.
  - Conferir contraste, legibilidade de texto secundario e diferenciação entre superficies.
  - Avaliar se neutros adicionais ajudam a reduzir a predominancia azul/grafite sem perder a identidade da Tor.
- [ ] Observar se alertas fortes cobrem os riscos operacionais reais.
  - Priorizar, quando a base de tarefas existir, prazo de tarefa expirando, analise parada e assinatura pendente.

## Qualidade tecnica

- [ ] Tornar o preview local persistente no navegador.
  - Salvar o estado simulado em `localStorage`, sem qualquer acesso ao banco ou ao ambiente de producao.
  - Preservar alteracoes durante recargas da pagina e disponibilizar uma acao explicita para restaurar os dados de exemplo.
  - Versionar o estado salvo para evitar que uma estrutura antiga quebre previews futuros.

- [ ] Ampliar testes para a tabela de disputa com Kits, incluindo produtos vinculados, quantidade original e minimo unitario manual.
- [ ] Cobrir o contrato entre backend e Sala de disputa para garantir o uso consistente de `minimum_unit_price` e evitar o retorno da nomenclatura legada na interface.

## Regra de priorizacao

Executar primeiro os itens em **Proximo ciclo de implementacao**. Itens que dependem de regra de negocio nao devem ser redesenhados ate que o fluxo seja definido.

## Avaliacao de aderencia ao Design System

Diagnostico registrado em 11/09/2026: aderencia geral estimada em **7/10**.

Pontos consolidados:

- Pipeline, cards, popup e aba Informacoes estao alinhados ao CRM operacional proposto: densos, legiveis e orientados a prazo, etapa e pendencia.
- A edicao por campo, os icones de checagem estaveis e o alerta discreto antes do ID TOR reforcam seguranca e memoria visual.
- Tema escuro evita preto absoluto; o claro ganhou superficies e contraste mais definidos.

Pontos que ainda afastam o produto da direcao visual:

- campos tecnicos duplicados do BI reduzem a leitura rapida;
- Documentacao continua funcionalmente rica, mas visualmente densa e deve ser retomada como proxima fase propria;
- a navegacao lateral ainda e mais plana e extensa que a arquitetura recomendada;
- alertas baseados em tarefa e tempo dependem da futura central de tarefas/notificacoes;
- tokens e padroes existem, mas a biblioteca de componentes do CRM ainda nao foi formalizada.
