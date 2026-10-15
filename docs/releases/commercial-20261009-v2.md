# Release commercial-20261009-v2

Entrega incremental sobre v1: planejamento de compras a partir de demanda e estoque documentado, solicitações para fornecedores, registro e comparação de propostas, seleção com justificativa e histórico. Nomes de fornecedores seguem a normalização central; cotações mantêm a evidência original após consolidação.

## Validação

- 85 testes analíticos aprovados, incluindo PostgreSQL 16 descartável com RLS obrigatório e referências compostas entre empresas; 72 testes frontend aprovados.
- TypeScript, lint Python/ESLint e build embarcado aprovados.
- API, frontend e worker executados no Docker local sem montagem de código; login, cargas CRM, relatórios e CSV de duas empresas passaram pelo proxy.
- Edge verificou demanda 10 UN, estoque físico 3 UN e reserva 1 UN, resultando em 8 UN para avaliar; propostas com totais 4050/4150 BRL; destaque do menor total elegível; escolha com justificativa persistente após reload; HTML/PDF sem campos internos; isolamento das solicitações.
- Regressão do dashboard, apresentação de demanda/cenário e avaliações de demanda/preço pelo worker aprovada. O histórico demo permanece insuficiente para gerar previsão elegível.

## Migração e uso

Migração necessária: `20261009_02`, após `20261009_01`. Executar migrações com a conta responsável e manter API/worker com contas sem SUPERUSER/BYPASSRLS. Novas tabelas: `core.procurement_requests` e `core.supplier_quotes`, incluídas no ensaio local de backup. Provisionar roles e ACLs separadamente após restauração.

```powershell
$env:MARKET_RELEASE_TAG = 'commercial-20261009-v2'
docker compose -p ragmatch-market-test -f docker-compose.analytics.test.yaml -f docker-compose.analytics.release-test.yaml run --rm migrate
docker compose -p ragmatch-market-test -f docker-compose.analytics.test.yaml -f docker-compose.analytics.release-test.yaml run --rm db-bootstrap
docker compose -p ragmatch-market-test -f docker-compose.analytics.test.yaml -f docker-compose.analytics.release-test.yaml up -d --no-deps api worker-data frontend
```

Para a composição de produção existente, usar a tag comum `IMAGE_TAG=commercial-20261009-v2` e `MARKET_WORKER_IMAGE=alvarocareli/ragmatch-market-worker:commercial-20261009-v2` no overlay analítico, com credenciais e tenants do ambiente. A publicação das imagens não implanta a VPS.

API e portal reutilizam as dependências validadas da base `sha-97a06d2e21c0ae69ecc971a7f42d7f76147a703a`. Worker reutiliza a imagem compatível publicada v1. Os labels `io.ragmatch.source-sha256` identificam o conteúdo incorporado do working tree; não representam commit Git.

## Uso funcional e limites

[Guia de planejamento e cotações](../planejamento-compras-cotacoes.md). O cálculo usa a mesma unidade e saldo de até sete dias. Quantidades precisam de confirmação; seleção não cria pedido nem reserva. Proposta desconhecida ou vencida não recebe destaque de menor total elegível. Prazo é contado em dias corridos a partir de hoje. Bling permanece uma integração futura, desabilitada por padrão.

Backup e restauração independente concluídos com conferência de contagens/valores, versão Alembic e RLS de duas empresas. Incluídos 2 registros de solicitação e 4 propostas fictícias. Manifesto local: `analytics/.validation/backups/market-local-0d80dc88f637.json`; SHA-256 do dump: `e63f745901459f39e98ea8e34ca7cca6184699d9e3283c5e084de283b60dea52`. O banco temporário foi removido, mantendo o demo original.

## Publicação confirmada em 09/10/2026

| Imagem | Digest remoto verificado |
|---|---|
| `alvarocareli/ragmatch-api:commercial-20261009-v2` | `sha256:2a321ea9aa161ba14fdd01975f92bd1f672b4f23372e51fcf11e53bb288a5de1` |
| `alvarocareli/ragmatch-frontend:commercial-20261009-v2` | `sha256:2aebae0cf0ecc200b60290caea349522e2038a416098c3bcadf308dba8c437c9` |
| `alvarocareli/ragmatch-market-worker:commercial-20261009-v2` | `sha256:bac34dbcd50e13815f1b3b533866014950307a9bd6702d1ea948e3e7e043dc29` |
| `alvarocareli/ragmatch-mlflow:commercial-20261009-v2` | `sha256:ce91a612c58c1272bf444ff1839302146902ff9097daed58ab059d5c06f43961` |

Hashes do conteúdo incorporado (`io.ragmatch.source-sha256`): API `e307ce9119b46a71a2f7c9bb5e30ef9e70c67e1a6792f752606884e3c0c0f688`; frontend `2a94d4c113b7b500d4bb6f3f62bfabcc4bee3d177cd3c1e3d6c00a5ad67188c5`; worker `64cc6b8566cd8d2044ba6e5805458fb42798b1ad4ab2fad2d755deaf5f68cfe4`. O manifesto local registra imagens, bases, hashes e digests em `analytics/.validation/releases/commercial-20261009-v2/manifest.json`.

Todas as tags foram verificadas como inexistentes antes da publicação. Nenhuma tag anterior foi substituída. MLflow recebeu apenas a nova tag comum, com digest idêntico ao da v1. O ambiente demo permanece executando v2; esta entrega não realizou implantação na VPS.
