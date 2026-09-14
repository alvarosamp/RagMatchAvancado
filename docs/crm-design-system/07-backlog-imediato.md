# CRM - Backlog Imediato

Atualizado em 14/09/2026.

Este arquivo e a fila curta de trabalho do CRM. O plano de execucao (`06-plano-execucao-redesign.md`) mantem o historico, as decisoes e o roadmap completo; este backlog concentra somente as proximas acoes para evitar reler o documento inteiro em cada ciclo.

## Proximo ciclo de implementacao

- [ ] Corrigir a continuidade do edital apos o Pregao.
  - O resultado de um item e uma informacao operacional da disputa; ele nao pode encerrar o edital nem desloca-lo automaticamente para `Resultados`.
  - Manter o edital no pipeline apos registrar itens vencidos, perdidos ou desclassificados, permitindo concluir Julgamento, Habilitacao, Recursos e contrarrazoes, Adjudicacao e Homologacao.
  - Definir o resultado geral do edital somente por encerramento explicito apos Homologacao, ou por uma regra futura aprovada para encerramento antecipado.
  - Corrigir o botao `Avancar etapa` para realizar `Pregao -> Julgamento`; hoje o frontend interpreta Pregao como a ultima etapa antes de chamar o backend.
  - Validar o mesmo comportamento por botao e por arrastar o card no Pipeline, incluindo edital com item ja marcado como vencido.

- [ ] Consolidar campos tecnicos dinamicos do BI na aba Itens.
  - Criar chaves canonicas para atributos recorrentes, incluindo Wi-Fi, portas, gerenciamento, PoE, uplink, camada e velocidade.
  - Priorizar fontes: campo estruturado do item, `bi_features`, `raw_payload` e inferencia tecnica.
  - Exibir uma unica caracteristica por conceito; quando houver conflito, manter o valor principal e tornar a divergencia consultavel.
  - Validar com dados que hoje repetem informacoes, como `Wi-Fi` e `Tecnologia Wi-Fi`.

- [ ] Validar Kits na Sala de disputa com dados reais.
  - A aba Itens e o card do Pipeline ja tratam o Kit como um unico item comercial, mantendo a quantidade original e agregando referencia e minimo.
  - Produtos vinculados aparecem apenas dentro do item principal, em formato compacto com marca/modelo e minimo LPU.
  - Confirmar na tabela de disputa que a quantidade original e o minimo unitario resolvido do item principal sao usados sem criar subitens comerciais.
  - Cobrir o caso com pelo menos dois produtos vinculados e LPUs diferentes.

- [ ] Separar com mais clareza analise de itens e resultado da disputa.
  - A aba Itens ainda apresenta o resumo "Resultado por item" antes da analise operacional.
  - Definir se o resumo de ganho/perda deve migrar para Pos-disputa/Resultados ou ficar como bloco secundario e recolhivel.

- [ ] Consolidar componentes-base do Design System.
  - Formalizar contratos reutilizaveis para card de entidade, metrica, alerta, linha de item, linha documental, filtro e timeline.
  - Reduzir diferencas visuais entre Pipeline, Calendario e abas internas antes de novos redesenhos.

## Aguardando detalhamento de regra de negocio

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
