# Release de match manual e sessões — 13/10/2026

Código executável: `70a2c8734965e1b0de11b95e4b50997c6d29faea`, na branch `codex/technical-match-v8`.

Tag publicada nos quatro repositórios Docker Hub, com manifestos remotos conferidos para Linux amd64:

```text
sha-70a2c8734965e1b0de11b95e4b50997c6d29faea
```

- `alvarocareli/ragmatch-api`
- `alvarocareli/ragmatch-frontend`
- `alvarocareli/ragmatch-mlflow`
- `alvarocareli/ragmatch-market-worker`

Os digests estão em [manual-match-20261013.json](manual-match-20261013.json). As variáveis da release estão em [manual-match-20261013.env](manual-match-20261013.env); esse arquivo não contém credenciais e não substitui o restante da configuração da VPS.

## Alterações

Match manual por item na aba Match do edital: tabelas de itens, requisitos e produtos, colunas por característica filtrada, JSON carregado do item sem download, importação externa opcional, comparação completa antes de confirmação e validação documental no servidor. Normalização por aliases explícitos, preservando SFP/SFP+, PoE/PoE+ e identificadores técnicos distintos. Dados incompletos permanecem pendentes.

Sessões renováveis com cookies HttpOnly e revogação no banco. Sem Manter conectado, sessão de navegador limitada a 12 horas; com a opção, persistência de até 30 dias. A expiração absoluta não é estendida pelo refresh. Logout e alterações de senha invalidam a sessão.

Migration incluída: `20261013_01`, posterior ao head unido `20261012_02`. Aplicar com o serviço migrate do compose de produção.

## Construção e validação

A publicação foi feita pelo Docker local, não pelo Actions. API construída com `backend/Dockerfile.release`: dependências da imagem publicada fixadas por digest, mesmas da prévia validada, e código/migrações do commit desta release. Os requirements não mudaram em relação à base. O inicializador QA e os dados de demonstração não integram a imagem de produção.

Frontend: imagem validada no navegador, construída de `frontend/Dockerfile`, com CRM embarcado e 74 hashes conferidos. Fonte privada fixada em `463f56b104b2dbadde7824c60f3b348fd7516ba2`, patches reproduzíveis versionados. MLflow: `mlflow/Dockerfile`, versão 2.12.1. Worker: base da release anterior fixada no digest registrado no manifesto, sobreposta com `backend/app` e `analytics` do commit atual; requirements analíticos sem mudanças.

116 testes de normalização, match e autenticação/sessão passaram contra a API final em execução com dois workers, PostgreSQL e Redis locais. Os 88 testes anteriores de regressão do motor, adaptador, exportação e extração também passaram. Readiness, migration head, configuração Nginx, versão MLflow e CLI do worker passaram. JSON direto e tabelas foram conferidos no navegador. Não representa execução de toda a suíte do Actions nem teste na Hostinger.

## Compose de produção

`docker-compose.prod.yaml` foi conferido com a tag desta release: API, workers, migrate, bootstrap, frontend e MLflow usam a mesma `IMAGE_TAG`. Para analytics, usar também `MARKET_WORKER_IMAGE` do arquivo de variáveis acima. Preservar os valores e credenciais existentes da VPS.

A VPS não foi implantada nesta publicação. O script `scripts/deploy-production.sh` exige que o commit publicado pertença ao histórico de `main`; a branch deve ser integrada preservando esse commit antes de usar o script. A publicação no Docker Hub não integra a branch nem muda o banco da VPS.
