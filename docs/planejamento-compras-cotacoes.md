# Planejamento de compras e cotações

No CRM, abra **Planejar compras e cotações** no dashboard ou a aba **Planejamento e cotações** da Inteligência Comercial.

1. Aplique o recorte de demanda e escolha o produto. A origem é única por recorte; o sistema não soma fontes que possam descrever o mesmo negócio.
2. Declare quantidade física, quantidade reservada, unidade, data e evidência da conferência. O saldo disponível é físico menos reservado. Somente conferências dos últimos sete dias, com produto identificado, quantidades completas e unidade compatível, permitem calcular uma quantidade a avaliar. Saldo desconhecido permanece desconhecido.
3. Confirme manualmente a quantidade para cotar, prazo desejado e orientações que serão compartilhadas com o fornecedor. A solicitação preserva o recorte original e a situação observada; o relatório atual não altera essa fotografia.
4. Baixe a solicitação HTML, que pode ser impressa como PDF. Ela inclui produto, quantidade, unidade, prazo e orientações compartilhadas. Estoque, propostas concorrentes, justificativas internas, custos e reservas não são exportados.
5. Registre propostas de fornecedores vinculados ao produto. Nomes e aliases seguem a normalização central; uma consolidação aprovada atualiza o vínculo da proposta e conserva o nome original na evidência.
6. Compare a mesma quantidade e unidade em BRL. Total = quantidade × preço unitário + frete total + impostos adicionais totais. Zero confirma valor incluído ou não aplicável; campo em branco mantém a condição desconhecida. O prazo é contado em dias corridos a partir de hoje. O destaque de menor total considera somente propostas válidas com frete, impostos, disponibilidade, lote mínimo e prazo documentados, sem violação de quantidade ou prazo desejado.
7. Registre a justificativa para selecionar uma proposta para negociação. Pendências ficam no histórico; propostas vencidas exigem novo registro. Seleção não cria pedido, contrato ou reserva. CSV permite exportar planejamento e comparação.

A demanda observada pode incluir oportunidades sem compra confirmada. A sugestão demanda menos estoque é um apoio à revisão, não uma ordem de compra nem previsão. A área de Predição continua separada e exige histórico elegível; o cenário da apresentação ao fornecedor continua identificado como hipótese.

Administradores e usuários com permissão de escrita podem registrar dados; leitores consultam e exportam. Solicitações e propostas são isoladas por empresa, com RLS e referências compostas no PostgreSQL. A lista apresenta 25 solicitações por página; filtros comerciais recortam a demanda, e o histórico de solicitações permanece no âmbito da empresa.

Migração necessária: `20261009_02`. Executar com conta de migração, manter a aplicação e o worker com conta sem SUPERUSER/BYPASSRLS. Backup e restauração devem incluir `core.procurement_requests` e `core.supplier_quotes`. O ensaio local de backup foi atualizado para incluir essas tabelas. Bling continua desabilitado por padrão.

## Acompanhamento das negociações

Os indicadores abrangem todo o histórico da empresa: solicitações sem propostas ou com escolha, propostas vencidas, propostas que vencem de hoje até sete dias e propostas com frete, impostos, disponibilidade, lote mínimo ou prazo não informado. Os limites são datas do calendário de Brasília. Uma proposta válida até hoje ainda está vigente. Uma mesma proposta pode aparecer em mais de um indicador; versões registradas são contadas separadamente.

Clique em um indicador para filtrar as solicitações. Também é possível filtrar por fornecedor que já registrou proposta, estado, nome do produto ou referência da solicitação. A busca trata caracteres como `%` e `_` como texto. A seleção de fornecedor exige uma proposta desse fornecedor, por isso solicitações ainda sem resposta não aparecem nesse recorte. Esses filtros têm escopo próprio e não alteram o recorte de demanda.

**Propostas por fornecedor** consolida a identidade normalizada e mostra solicitações respondidas, versões de propostas, vencimentos e campos desconhecidos. A tabela limita a exibição aos 200 fornecedores com mais propostas e informa quando há mais; os indicadores gerais abrangem todos. Os números não representam compras ou desempenho de entrega. A comparação detalha preço unitário, unidade, evidência e data do registro da proposta.

## Relatório interno e composição do custo

A comparação agora separa valor dos produtos (quantidade confirmada × preço unitário), frete e impostos adicionais. O total só está disponível quando frete e impostos estão documentados. A diferença para o menor total elegível é calculada com decimais, somente entre propostas com condições elegíveis da mesma solicitação. Empates são preservados; propostas vencidas/incompletas ou sem disponibilidade/prazo adequados ficam sem diferença comparável. Diferença não representa economia realizada.

**Baixar relatório interno de negociação** gera HTML imprimível em PDF, com propostas, evidências, composição de custos, pendências atuais e histórico de escolhas. O relatório é identificado como interno, pois contém concorrência e justificativas da empresa. Para o fornecedor, continue usando **Baixar solicitação para fornecedor**, que preserva a lista restrita de campos compartilháveis. O histórico mostra valores/condições do momento da escolha; condições atuais são reavaliadas na data de geração.
