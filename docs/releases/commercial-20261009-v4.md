# Release commercial-20261009-v4

Incremento sobre v3: composição exata do custo de propostas, diferença para o menor total elegível da mesma solicitação e relatório interno imprimível em PDF, com evidências e histórico de escolhas. Propostas vencidas/incompletas não recebem diferença comparável. Valores de produtos, frete e impostos adicionais aparecem separadamente. Diferença não é economia realizada.

Validação de código: 85 testes analíticos e 76 testes frontend aprovados, TypeScript, lint e build embarcado aprovados. Os cinco testes PostgreSQL descartáveis não foram repetidos nesta alteração aritmética/de exportação; consultas, RLS e migrações permanecem os validados na v3. Não há mudança de schema ou backup; a migração continua `20261009_02`.

O relatório interno contém propostas concorrentes e justificativas e é identificado como interno. O arquivo compartilhável da solicitação para fornecedor mantém sua lista restrita de campos. O histórico conserva condições/total do momento da escolha; a tabela de propostas informa as condições atuais na geração.

Guia: [planejamento e negociação](../planejamento-compras-cotacoes.md). Worker usa a base compatível v3; MLflow mantém a imagem existente. Hashes das imagens incorporadas identificam o working tree e não um commit. Dados locais são fictícios, e Bling continua desabilitado por padrão.

```powershell
$env:MARKET_RELEASE_TAG='commercial-20261009-v4'
docker compose -p ragmatch-market-test -f docker-compose.analytics.test.yaml -f docker-compose.analytics.release-test.yaml up -d --no-deps api worker-data frontend
```

Bancos anteriores à v2 precisam da cadeia de migrações até `20261009_02` e provisionamento das contas restritas.

Homologação Docker: API, frontend e worker executados sem montagens do código. Login, cargas, relatórios/CSV e isolamento entre duas empresas aprovados pelo proxy. Edge confirmou a composição 4000 + 40 + 10 = 4050 BRL, diferença de 100 BRL entre propostas elegíveis, histórico e exportação HTML/PDF em A4 paisagem. O arquivo final usa rótulos legíveis para os filtros. Regressão de estoque/cotações, escolha persistente, solicitação compartilhável, acompanhamento e layout desktop/móvel aprovada.

Evidências locais: `analytics/.validation/negotiation-internal-report.html`, `.pdf` e `.png`. Essas verificações usam dados fictícios e não declaram homologação de produção ou de Bling.

## Publicação confirmada em 09/10/2026

| Imagem | Digest remoto verificado |
|---|---|
| `alvarocareli/ragmatch-api:commercial-20261009-v4` | `sha256:4ccf1131d0e60343ece8d5f0f99fc18858fa08fbce0a126c1f79a355b2548f02` |
| `alvarocareli/ragmatch-frontend:commercial-20261009-v4` | `sha256:a20c637930539e2f12e8ead79a5e627bc497ad15316ef01ec3257d8917742f57` |
| `alvarocareli/ragmatch-market-worker:commercial-20261009-v4` | `sha256:64e0366d99dbcb49df8af6f8902fb15fd512cd8df0fce05b08804316a075d10e` |
| `alvarocareli/ragmatch-mlflow:commercial-20261009-v4` | `sha256:ce91a612c58c1272bf444ff1839302146902ff9097daed58ab059d5c06f43961` |

Hashes de conteúdo incorporado: API `925278fe8ef3c4922cf3db546be6277e91cb6d6a5e99fe154321a79ef2086931`; frontend `e5ede4ff3a377a8a9bca8aad0ca1506cd9078cb62aacbab86fa8b17266d4e912`; worker `74d631319bcf390b836e9f8fcd4a353cbb952946fc44f875161b64ba67c7234e`. Manifesto: `analytics/.validation/releases/commercial-20261009-v4/manifest.json`.

As tags foram verificadas como inexistentes antes da publicação; nenhum release anterior foi substituído. Digests remotos conferidos com as imagens finais executadas sem montagens do código. MLflow recebeu a tag comum com o mesmo digest da imagem existente. O demo local está executando v4. A publicação não realizou implantação na VPS. Para a composição de produção, usar `IMAGE_TAG=commercial-20261009-v4` e o worker `alvarocareli/ragmatch-market-worker:commercial-20261009-v4` no overlay analítico, com a configuração do ambiente de destino.
