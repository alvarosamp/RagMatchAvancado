# Consolidação comercial + comparação técnica

O código da branch `codex/technical-match-v8` foi unido ao trabalho de `codex/conlicitacao-fases-1-2`. O CRM está fixado em `463f56b104b2dbadde7824c60f3b348fd7516ba2`.

- Histórico Alembic completo preservado. A revisão `20261012_02` une `20261010_03` e `20261012_01`, sem substituir identificadores no banco. O bootstrap autorizado de banco novo registra o snapshot operacional `20261012_01` e executa as migrações analíticas até o head unido.
- Proteções contra exclusão por omissão, perda de referências/anotações e retorno à triagem continuam no importador. A tela de recuperação e o rascunho de Novo edital continuam no CRM.
- ConLicitacao e comparação técnica coexistem nas rotas. Foram incorporadas exportação de metadados, ficha técnica, filtros e comparação por regras, mantendo as funcionalidades dos dashboards comerciais.
- CRM reconstruído da fonte privada. O bundle público conserva a revisão e os hashes dos arquivos. O CI público valida esse bundle e o executa com a API real em testes de navegador, sem divulgar o restante da fonte privada ou guardar credenciais pessoais no Actions. Testes unitários privados do CRM foram executados localmente; o workflow de integridade do bundle não afirma executar esses testes.
- Corrigida a dependência openpyxl ausente dos testes analíticos no Actions, e o uso do fuso de São Paulo na fixture de validade de cotações.

Validação local: 106 testes selecionados de backend, 99 testes analíticos (cinco opcionais PostgreSQL dependem do ambiente), 88 testes do CRM e 41 testes do frontend. TypeScript, lint sem erros, compilação Python e builds aprovados.

O CI inclui um teste de atualização PostgreSQL a partir de `20260926_01`, `20261010_03` e `20261012_01`, em bancos descartáveis exclusivos, verificando registros preservados e a coluna técnica. Inclui também testes de navegador para recuperação de rota, rascunho e a página ConLicitacao. A execução desses testes e a publicação das imagens serão registradas após a conclusão do CI. Docker Linux local está indisponível nesta sessão; nenhuma validação com dados reais da VPS foi executada.

Para atualização, preservar volumes e fazer backup verificável. Não executar reset de banco, `down -v` ou stamp para esconder revisões pendentes. API, frontend e workers precisam usar a mesma release publicada. Bling continua em desenvolvimento; Vercel aguarda conexão da conta.
