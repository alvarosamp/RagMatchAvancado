# CRM - Backlog Imediato

Atualizado em 11/09/2026.

Este arquivo e a fila curta de trabalho do CRM. O plano de execucao (`06-plano-execucao-redesign.md`) mantem o historico, as decisoes e o roadmap completo; este backlog concentra somente as proximas acoes para evitar reler o documento inteiro em cada ciclo.

## Proximo ciclo de implementacao

- [ ] Consolidar campos tecnicos dinamicos do BI na aba Itens.
  - Criar chaves canonicas para atributos recorrentes, incluindo Wi-Fi, portas, gerenciamento, PoE, uplink, camada e velocidade.
  - Priorizar fontes: campo estruturado do item, `bi_features`, `raw_payload` e inferencia tecnica.
  - Exibir uma unica caracteristica por conceito; quando houver conflito, manter o valor principal e tornar a divergencia consultavel.
  - Validar com dados que hoje repetem informacoes, como `Wi-Fi` e `Tecnologia Wi-Fi`.

- [ ] Revisar a leitura de Kits na aba Itens e na Sala de disputa.
  - Preservar o Kit como um unico item comercial, com a quantidade do item original.
  - Manter as descricoes, marca e modelo dos produtos vinculados acessiveis sem transforma-los em subitens comerciais.
  - Confirmar que o minimo unitario e editavel somente no item original e que a tabela de disputa usa esse mesmo valor resolvido.
  - Validar o layout com pelo menos um Kit real contendo mais de um produto vinculado.

## Aguardando detalhamento de regra de negocio

- [ ] Redesenhar itens retirados e lotes totalmente retirados.
  - A solucao atual permanece por enquanto.
  - Definir antes de alterar: motivo da retirada, criterios de reabertura, quem pode reabrir, impacto no resultado e no retorno a disputa.

- [ ] Refinar a aba Documentacao como checklist e biblioteca de arquivos.
  - Mapear categorias, dependencias entre documentos, assinatura solicitada e estados de conferencia antes de mexer novamente no layout.

## Acompanhar em uso real

- [ ] Observar a compactacao do Pipeline com editais reais e registrar qualquer informacao operacional que tenha ficado escondida ou excessivamente aglutinada.
- [ ] Verificar se os filtros atuais precisam expor prioridade quando a classificacao por estrelas passar a ser usada de forma recorrente.

## Qualidade tecnica

- [ ] Ampliar testes para a tabela de disputa com Kits, incluindo produtos vinculados, quantidade original e minimo unitario manual.
- [ ] Cobrir o contrato entre backend e Sala de disputa para garantir o uso consistente de `minimum_unit_price` e evitar o retorno da nomenclatura legada na interface.

## Regra de priorizacao

Executar primeiro os itens em **Proximo ciclo de implementacao**. Itens que dependem de regra de negocio nao devem ser redesenhados ate que o fluxo seja definido.
