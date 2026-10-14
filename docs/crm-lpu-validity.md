# Validade e substituição de LPU

A importação no CRM exige validade e um usuário ativo da organização como responsável.
Antes de gravar, a interface mostra uma prévia dos produtos ausentes da nova planilha.
A prévia é revertida por completo no banco. A confirmação executa a importação novamente.

A LPU fica válida até o fim da data informada, no horário de Brasília. Depois disso,
um aviso aparece na entrada do CRM, inclusive no dashboard. O vencimento não exclui
produtos nem preços. Administradores podem aumentar a validade e escolher o responsável;
as prorrogações registram usuário, data e validade anterior.

Produtos da LPU anterior que não aparecem na nova, inclusive de categorias inteiras
que desapareceram, recebem uma pendência atribuída ao responsável da importação.
O prazo é de um mês de calendário, ajustado ao último dia do mês quando necessário.
Novas importações não reiniciam esse prazo. Produtos manuais não entram nessa revisão.
O responsável pode conferir preços e abrir a LPU antiga antes de confirmar a retirada.
O prazo vencido mantém o aviso e os dados; não existe exclusão automática.

Confirmar a retirada arquiva o produto e o oculta do catálogo ativo. O registro, suas
referências, documentos e links continuam disponíveis aos processos. A exclusão genérica
é bloqueada para produtos de LPU e para produtos vinculados a processos. Antes de uma
atualização de preço ou retirada, processos existentes recebem uma cópia dos dados do
catálogo. Novas vinculações também registram essa cópia. Se o produto voltar em outra
LPU, o mesmo ID é reativado e as cópias antigas dos processos permanecem preservadas.

## Aplicação e verificação

Aplicar a migração Alembic `20261014_01` e publicar backend e CRM juntos. LPUs anteriores
não recebem uma validade inventada: a próxima importação registra validade e responsável.
Essa mudança não recupera automaticamente produtos já excluídos por importações antigas.

A validação `qa/lpu_lifecycle_checks.py` executa o fluxo com os modelos reais em SQLite
isolado, dentro da imagem com as dependências de produção. Cobre prévia sem gravação,
retenção de categoria ausente, isolamento entre organizações, expiração, prorrogação,
confirmação, preços e links históricos, ocultação no catálogo e retorno de um produto.
Os testes do frontend cobrem os avisos, a escolha do responsável e a confirmação explícita.
