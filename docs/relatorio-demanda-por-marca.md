# Relatório de demanda por marca para fornecedores

Na branch `codex/inteligencia-produtos-hostinger`, abra CRM → Inteligência de mercado.
O painel **Relatório por marca para fornecedores** permite selecionar a marca do
catálogo e exportar os itens em CSV ou baixar um relatório HTML independente, que
pode ser aberto e impresso em PDF pelo navegador. Os filtros de categoria, UF,
busca e data de cadastro da página também se aplicam ao relatório.

A entrega separa marca declarada no edital, direcionamento explicitamente
registrado, vínculo de catálogo/match confirmado e associação por modelo exato.
Grupos podem se sobrepor; o total de itens é deduplicado. Componentes de kits não
somam novamente a demanda do item principal. Quantidades são totalizadas por
unidade, sem somar metros com unidades. Dados ausentes permanecem N/C.

Ganhos com a marca exigem o resultado do item com vencedor **nós** e a marca
vencedora correspondente. O valor ganho exige preço e quantidade vencedora
registrados. A marca de um candidato vinculado não prova a marca vendida; o
resultado geral do edital não é propagado aos itens sem resultado.

Na aba **Itens** do edital, abra **Detalhes** → **Resultado do item**. Para um item
perdido para concorrente, registre **Motivo da perda do item**. Preço, requisito
técnico, documentação, prazo e outro motivo são opções independentes das
observações. Histórico sem classificação permanece não classificado; diferença
entre nossa oferta e preço vencedor não é automaticamente motivo de perda.

O relatório externo contém demanda, vínculos, resultados, preço de referência,
nossa oferta e preço vencedor. Custos, margens, notas de match e observações
livres ficam fora da exportação. Textos são escapados para HTML e células CSV
são protegidas contra fórmulas. Demanda observada não representa pedido firme.
Se catálogo, resultados ou vínculos não puderem ser consultados, exportação é
bloqueada para evitar apresentar dados parciais como completos.

## Implementação e validação

Os dados vêm das consultas CRM existentes, autenticadas e restritas ao tenant.
Não há nova tabela nem migration. O motivo estruturado é armazenado como marcador
`[motivo_perda:price|technical|documentation|deadline|other]` em `notice_item_results.notes`.
O editor oculta o marcador das observações e o preserva ao editar o texto; trocar
o motivo preserva as observações. A exportação lê somente o código classificado.
Integrações externas que substituam `notes` precisam preservar esse marcador.

Testes de cálculo e componentes cobrem vínculos versus sugestões, compatibilidade,
resultados parciais, valores ausentes, unidades distintas, kits, deduplicação,
escape e privacidade das exportações. O teste HTTP/navegador usa PostgreSQL de
QA, catálogo e resultados fictícios, filtros e downloads nativos CSV/HTML.

Validação desta entrega: 26 testes de frontend aprovados, TypeScript e ESLint dos
novos módulos aprovados, build Docker do CRM/portal aprovado. Navegador Chromium
com PostgreSQL real aprovou seleção de marca, recorte com três itens, valor ganho
R$ 225,00 (dados fictícios), motivo de preço, downloads CSV/HTML, largura móvel e
preservação do motivo ao editar as observações logo após salvar. A implantação
na Hostinger não foi realizada.
