# Publicação: importação de JSONs e documentos — 14/10/2026

As quatro imagens foram publicadas em `alvarocareli/ragmatch-api`, `alvarocareli/ragmatch-frontend`, `alvarocareli/ragmatch-market-worker` e `alvarocareli/ragmatch-mlflow`. Mesma tag em todas:

```
sha-8b170e12e60f3f5e9c303580985d0a6b8d097415
```

Os digests remotos foram conferidos com os descritores das imagens testadas. [Manifesto](catalog-json-import-20261014.json). [Variáveis para implantação](catalog-json-import-20261014.env).

Inclui a importação em lote de JSONs de produtos e datasheets, associação por SHA-256, preservação de preços e atributos revisados, validação de arquivos e limite de upload por rota. Inclui também o ciclo de validade/revisão da LPU e abertura do match pela descrição original do item. JSONs/PDFs locais, banco e dados de demonstração não foram incorporados às imagens.

Código congelado pelo commit `8b170e12e60f3f5e9c303580985d0a6b8d097415`. Plataforma Linux amd64. API usa `backend/Dockerfile.release` e dependências anteriores fixadas por digest, sem alteração de requirements. Worker mantém a base de dependências fixada; frontend usa `frontend/Dockerfile`. MLflow permanece sem alterações, retaggeado na mesma versão das demais imagens.

Validação: 33 testes direcionados na prévia, cinco testes unitários do importador na versão final, 43 testes HTTP contra a API final, cenários isolados de importação/LPU/descrição do match, 74 hashes de artefatos CRM, readiness da API, Nginx, CLI do worker e MLflow 2.12.1. Migração verificada: `20261014_01`. O teste pela interface atualizou `PRE-XFP-B23-40` e anexou seu datasheet.

## Hostinger

Use `docker-compose.prod.yaml` e atualize `IMAGE_TAG` para a tag acima nas variáveis existentes. API, frontend, MLflow, bootstrap, migração e workers resolvem a mesma versão. Mantenha as demais variáveis e volumes existentes. O arquivo `.env` desta release contém somente referências de versão e não substitui as credenciais/configurações da instalação.

A VPS não foi implantada por esta publicação. As imagens finais também foram validadas na prévia Docker local. Não houve push de código no GitHub.
