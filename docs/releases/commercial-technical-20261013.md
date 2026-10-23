# Consolidação comercial + comparação técnica

O código da branch `codex/technical-match-v8` foi unido ao trabalho de `codex/conlicitacao-fases-1-2`. O CRM está fixado em `463f56b104b2dbadde7824c60f3b348fd7516ba2`.

- Histórico Alembic completo preservado. A revisão `20261012_02` une `20261010_03` e `20261012_01`, sem substituir identificadores no banco. O bootstrap autorizado de banco novo registra o snapshot operacional `20261012_01` e executa as migrações analíticas até o head unido.
- Proteções contra exclusão por omissão, perda de referências/anotações e retorno à triagem continuam no importador. A tela de recuperação e o rascunho de Novo edital continuam no CRM.
- ConLicitacao e comparação técnica coexistem nas rotas. Foram incorporadas exportação de metadados, ficha técnica, filtros e comparação por regras, mantendo as funcionalidades dos dashboards comerciais.
- CRM reconstruído da fonte privada. O bundle público conserva a revisão e os hashes dos arquivos. O CI público valida esse bundle e o executa com a API real em testes de navegador, sem divulgar o restante da fonte privada ou guardar credenciais pessoais no Actions. Testes unitários privados do CRM foram executados localmente; o workflow de integridade do bundle não afirma executar esses testes.
- Corrigida a dependência openpyxl ausente dos testes analíticos no Actions, e o uso do fuso de São Paulo na fixture de validade de cotações.

Validação local: 106 testes selecionados de backend, 99 testes analíticos (cinco opcionais PostgreSQL dependem do ambiente), 88 testes do CRM e 41 testes do frontend. TypeScript, lint sem erros, compilação Python e builds aprovados.

O CI inclui um teste de atualização PostgreSQL a partir de `20260926_01`, `20261010_03` e `20261012_01`, em bancos descartáveis exclusivos, verificando registros preservados e a coluna técnica. Inclui também testes de navegador para recuperação de rota, rascunho de Novo edital e a página ConLicitacao. Docker Linux local está indisponível nesta sessão; a validação foi executada nos containers do GitHub Actions, sem dados reais da VPS.

Validação completa do commit `5257acabb4b0dc34417fe66138d59cc1588a956d`: [execução aprovada](https://github.com/alvarosamp/RagMatchAvancado/actions/runs/38347755589). Foram aprovados 476 testes unitários de backend, 5 de integração HTTP, 105 analíticos, 228 de API/banco/fluxos, 21 de serviços com bibliotecas reais, 124 de navegador (Chromium/Firefox, desktop/celular) e 41 do frontend: 1.000 testes no CI. Os 88 testes da fonte privada do CRM foram executados localmente. Transformações dbt, integridade do bundle e smoke tests das quatro imagens também passaram.

Cobertura combinada de todo o backend: **66,91%**. Foi corrigida a divergência entre o gate global do script (90%) e os dois documentos de CI (50%), mantendo a política global documentada de 50% e todos os limites críticos. Foram adicionados 13 testes que verificam os limites globais, individuais e a ausência de cobertura crítica. Resultados críticos: autenticação 97,22% (mínimo 90%), dependências de autorização 85,51% (85%), proteção HTTP 96,77% (95%), sessão de banco 100% (85%) e dashboard CRM 100% (95%). Existem lacunas de testes no restante do backend; o resultado não significa 90% de cobertura global.

As quatro imagens foram publicadas no namespace `alvarocareli`, com a mesma tag:

```text
sha-5257acabb4b0dc34417fe66138d59cc1588a956d-38347755589-1
```

Imagens: `ragmatch-api`, `ragmatch-frontend`, `ragmatch-market-worker` e `ragmatch-mlflow`. O manifesto [commercial-technical-20261013.json](commercial-technical-20261013.json) registra referências completas, digests, commit e execução. O artifact `dockerhub-release` do Actions contém esse manifesto e `deploy.env`. A publicação executou smoke tests antes do push e conferiu os digests após o push. A VPS **não foi implantada** por essa execução.

Também foi removido apenas do índice Git `_worktrees/pr23-fix`, um checkout local registrado como submódulo sem configuração. Os arquivos locais foram preservados e `_worktrees/` passou a ser ignorado. O submódulo privado `bid-buddy` permanece fixado e intacto. Esse ajuste e o registro da release são posteriores ao commit das imagens e não alteram o código executável publicado.

Para atualização, preservar volumes e fazer backup verificável. Não executar reset de banco, `down -v` ou stamp para esconder revisões pendentes. API, frontend e workers precisam usar a mesma release publicada. O script de deploy exige que o commit da release pertença ao histórico de `main`: integrar a branch preservando o histórico com merge commit, ou publicar uma nova release do commit final de `main` após squash/rebase. As branches de trabalho atualizadas não alteram automaticamente `main` ou a VPS.

O log inicial mostrou o contêiner de migração encerrando antes de API/frontend iniciarem; a mensagem interna da VPS ainda não foi fornecida. A compatibilidade das revisões foi corrigida e testada, mas a causa exata desse erro em produção e domínio/TLS/Traefik precisam ser confirmados na VPS após a atualização. Bling continua em desenvolvimento; Vercel aguarda conexão da conta.
