# commercial-20261010-v6

O dashboard de entrada do CRM (/crm/) agora apresenta a empresa, indicadores reais, próximas disputas, ações e editais recentes. A exploração comercial fica aberta por padrão, com acesso direto a predição e apresentação para fornecedores.

O endpoint autenticado /api/crm/dashboard-data lê projeções dos campos necessários, sem carregar catálogo e relacionamentos completos. Cada consulta é isolada por empresa e por savepoint: falhas em uma seção retornam dados indisponíveis, preservando as demais. Requisitos extraídos dos documentos da empresa alimentam o indicador Pontos analisados; pendências de preparação do CRM são distintas de documentos aguardando assinatura.

Uma base analítica sem carga do CRM mostra instrução para carregar os dados, sem zeros que sugiram ausência de demanda. O erro operacional mantém a inteligência acessível e identifica o status HTTP.

## Validação

- CRM: 79 testes passaram, TypeScript e lint passaram; build de produção concluído.
- Analytics: 87 testes passaram; 5 testes PostgreSQL opcionais não foram executados nessa suíte local.
- Docker sem volumes de código: login, dashboard CRM e exploração interativa em 1440 e 390 pixels, sem overflow ou erros de JavaScript.
- Falha HTTP 500 simulada: quatro indicadores indisponíveis, dashboards e atalhos preservados.
- PostgreSQL real: dashboard-data sem erros de seção para duas empresas; isolamento dos editais confirmado. Jobs CRM, relatórios e CSV passaram pela API/worker reais.

## Atualização da VPS

A publicação no registry não atualiza automaticamente a VPS. Atualizar API e frontend juntos, além do worker de inteligência, usando:

```env
IMAGE_TAG=commercial-20261010-v6
MARKET_WORKER_IMAGE=alvarocareli/ragmatch-market-worker:commercial-20261010-v6
```

O diagnóstico da captura da VPS não confirma uma causa específica do erro anterior. A conexão ao host e a validação com seus dados reais permanecem pendentes.

## Publicação verificada

- `alvarocareli/ragmatch-api:commercial-20261010-v6`: `sha256:ef570798f4d3066d5eb3ea9bacc531878742ae8b7b81ca9f531fb6dbeb98d0ba`
- `alvarocareli/ragmatch-frontend:commercial-20261010-v6`: `sha256:66910ae97eae77acf2c606e137eac0edd5ccb0561af7bdcfeda6eea3b2e2aca5`
- `alvarocareli/ragmatch-market-worker:commercial-20261010-v6`: `sha256:62db36a9dbb04a262c8c3e9fb5a0c157b0d0abb02fbfc1348e3fd030b611926a`
- `alvarocareli/ragmatch-mlflow:commercial-20261010-v6`: `sha256:ce91a612c58c1272bf444ff1839302146902ff9097daed58ab059d5c06f43961`

CRM publicado no commit `9bd6942` da branch `codex/inteligencia-comercial-v4`. O repositório principal fixa esse commit no submódulo.
