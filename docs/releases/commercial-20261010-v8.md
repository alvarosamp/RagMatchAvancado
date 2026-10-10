# CRM: recuperação de falhas e preservação da triagem — v8

Tag: `commercial-20261010-v8`. Sem nova migração; mantém o head `20261010_03`.

## Comportamento

- Falhas de renderização ou de carregamento de uma rota mostram uma tela de recuperação. A recuperação exige clique para não recarregar automaticamente um formulário em edição.
- Respostas 401 levam ao login real do portal. O prazo da sessão permanece inalterado. A causa da tela vazia observada em produção não foi confirmada por logs autenticados; a falha de uma rota foi reproduzida e tratada localmente.
- O formulário **Novo edital** guarda imediatamente um rascunho em `sessionStorage`, separado por usuário. Recarregar e autenticar novamente na mesma aba recupera o preenchimento. Validade de sete dias, sujeita à disponibilidade do armazenamento do navegador. Fechar a aba/navegador pode eliminar esse rascunho. Outros formulários ainda não receberam essa proteção.
- O rascunho é removido após confirmação da criação principal. Falha em tarefas adicionais não transforma uma criação confirmada em um pedido para criar novamente. Não há repetição automática de escritas após falha de rede.
- Reimportação de JSON preserva itens omitidos, etapa, resultado, responsável, autoria, status comercial, anotações e campos extraídos que vierem ausentes. Remover um item exige exclusão operacional explícita. Valores novos presentes podem atualizar as referências; omissão não representa pedido de apagar dados. Preços e quantidades parciais conservam uma referência total consistente quando há dados suficientes.
- Dados estruturados da triagem alimentam a camada analítica mesmo sem vínculo ao catálogo: quantidade, categoria, referências, características BI, garantia, prazo e riscos. Os detalhes dos indicadores mostram o contexto da triagem. Quantidade solicitada não representa venda; preço de referência não representa faturamento; falta de avaliação não comprova atendimento ou lacuna.
- O JSON e a sincronização do CRM são gravados na transação da requisição. Uma falha antes do commit mantém a última versão persistida. O fechamento da sessão SQLAlchemy reverte transações não confirmadas. Isso não recupera alterações já sobrescritas em versões antigas nem substitui um backup.

## Validação

Testes de interface: 82 aprovados. Analítica: 94 aprovados, cinco testes opcionais de PostgreSQL não executados nesta suíte. TypeScript, lint (zero erros; três avisos anteriores) e build embed.

Validação adicional nas imagens do Docker local, sem montagem do código-fonte: login e sincronização de duas empresas, falha de carregamento de rota, recuperação da interface, rascunho após reload e sessão expirada/relogin. Testes usam exclusivamente dados fictícios.

Dump PostgreSQL local restaurado com sucesso em um banco separado (`restore_v8_20261010204048`), com as mesmas contagens de dois editais, dois itens e nove fatos. O banco original não foi sobrescrito. Não foi configurado nem verificado um backup de produção nesta entrega. O projeto já dispõe de `scripts/backup-production.sh`, com PostgreSQL, MinIO, checksums e cópia externa; é necessário conferir a execução e a restauração na VPS para garantir recuperação de volumes perdidos.

## Atualização

Atualizar API, frontend e market-worker juntos para a tag v8, preservando volumes. Não executar `docker compose down -v`. Fazer backup antes da atualização. O agendador da inteligência continua necessário para refletir novas importações nos relatórios.

Vercel TorTecDash continua aguardando conexão da conta. Bling continua em desenvolvimento.
