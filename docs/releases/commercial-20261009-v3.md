# Release commercial-20261009-v3

Incremento sobre v2: acompanhamento das negociações com solicitações sem resposta/com escolha, propostas vencidas/vencendo em até sete dias e condições não informadas. Indicadores filtram a lista; estado, fornecedor e produto/referência têm filtros próprios. Resumo por identidade normalizada de fornecedor e comparação com preço unitário, unidade, referência e data da proposta.

## Validação de código

88 testes analíticos aprovados, incluindo agregações sob role PostgreSQL 16 sem SUPERUSER/BYPASSRLS, FORCE RLS, busca literal, calendário de Brasília, paginação e isolamento entre empresas. 74 testes frontend aprovados, incluindo navegação pelos indicadores, filtro por fornecedor e aplicação explícita de busca. TypeScript, lint dos arquivos de código e build embarcado aprovados.

## Uso e semântica

Acesse CRM → Planejar compras e cotações → Acompanhamento das negociações. O resumo abrange o histórico inteiro da empresa; os filtros comerciais continuam aplicados à demanda. Indicadores contam versões de propostas e podem se sobrepor. Campos não informados são frete, impostos, disponibilidade, lote mínimo ou prazo. Esses números não representam compras nem desempenho de entrega.

Validade inclui o dia final; próximos vencimentos são de hoje até hoje + 7 dias no calendário de Brasília. A busca interpreta `%` e `_` como texto. Um filtro de fornecedor só inclui solicitações com proposta daquele fornecedor. Resumo de fornecedores limita a exibição aos 200 com mais propostas, com aviso de truncamento; indicadores gerais abrangem todos.

Guia: [planejamento e acompanhamento](../planejamento-compras-cotacoes.md). A migração permanece `20261009_02`; esta versão não altera tabelas nem o formato do backup. Bling continua desabilitado por padrão.

```powershell
$env:MARKET_RELEASE_TAG = 'commercial-20261009-v3'
docker compose -p ragmatch-market-test -f docker-compose.analytics.test.yaml -f docker-compose.analytics.release-test.yaml up -d --no-deps api worker-data frontend
```

Atualização de um banco anterior à v2 exige a cadeia de migrações até `20261009_02` e provisionamento de roles. API/worker continuam usando contas restritas. As imagens são empacotadas a partir do working tree; o label `io.ragmatch.source-sha256` identifica o conteúdo incorporado, sem alegar um commit Git. O worker reutiliza a base compatível publicada v2; MLflow mantém a imagem anterior com nova tag comum.

## Homologação Docker

API, frontend e worker v3 executados sem montagens de código. Login, cargas CRM, relatórios e CSV das duas empresas passaram pelo proxy. Edge confirmou contagens completas, filtros de solicitações sem resposta/condições incompletas, fornecedor normalizado, busca literal, referência/preço unitário e layout sem transbordamento horizontal em desktop e celular.

Regressão de estoque/cotações, escolha persistente, solicitação HTML/PDF, dashboard, apresentação ao fornecedor/cenário e ambas as avaliações de previsão pelo worker aprovada. Dados demo permanecem fictícios e sem histórico elegível para previsão. Capturas locais: `analytics/.validation/negotiations-desktop.png` e `negotiations-mobile.png`.

## Publicação confirmada em 09/10/2026

| Imagem | Digest remoto verificado |
|---|---|
| `alvarocareli/ragmatch-api:commercial-20261009-v3` | `sha256:4db5460dd4090dbc28ebcf972ea7216b6e00b7363750f613c5a5b3bfcd8de755` |
| `alvarocareli/ragmatch-frontend:commercial-20261009-v3` | `sha256:bed5edf16cd34c5ff8c077cc7c0927f81e905d3a52354dcc00c63ec227b410b0` |
| `alvarocareli/ragmatch-market-worker:commercial-20261009-v3` | `sha256:efb4358540c34fd9e0571e9e8000e18a279598d5c3212d55125611dbd8f83651` |
| `alvarocareli/ragmatch-mlflow:commercial-20261009-v3` | `sha256:ce91a612c58c1272bf444ff1839302146902ff9097daed58ab059d5c06f43961` |

Hashes do conteúdo incorporado: API `55b2b8bda24257b265422a781e63c1761966e1a682a19db412f795f83e713742`; frontend `f5ed7c1f3c3289a490cb8560b1d095949a4942876f5655b005d7812b11362243`; worker `bedfeb18ceae7f2c0d8456b99b1db78b54aa32d2548250a24307815c29c6033a`. Manifesto: `analytics/.validation/releases/commercial-20261009-v3/manifest.json`.

Tags verificadas como inexistentes antes de publicar. Os digests foram comparados com as imagens finais testadas, e nenhuma tag anterior foi substituída. MLflow preserva o digest da imagem existente. Para a composição de produção, a versão comum é `IMAGE_TAG=commercial-20261009-v3`, com `MARKET_WORKER_IMAGE=alvarocareli/ragmatch-market-worker:commercial-20261009-v3` no overlay analítico e as credenciais/tenants do ambiente. Esta publicação não realizou implantação na VPS.
