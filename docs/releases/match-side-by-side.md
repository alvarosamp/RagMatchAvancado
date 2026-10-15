# Publicação do match lado a lado

Tag comum verificada nos quatro repositórios alvarocareli/ragmatch-api, alvarocareli/ragmatch-frontend, alvarocareli/ragmatch-market-worker e alvarocareli/ragmatch-mlflow:

```
IMAGE_TAG=sha-5c4b643c6d0859be096ae6fffc590bb774b738bb
```

[Manifesto com digests remotos](match-side-by-side.json). [Variáveis da implantação](match-side-by-side.env). [Comportamento e validação](../match-side-by-side.md).

Frontend Linux amd64 construído de uma exportação Git congelada do commit 5c4b643c6d0859be096ae6fffc590bb774b738bb. API, worker e MLflow foram publicados sem alterações com a mesma tag. Os oito testes pertinentes, replay do patch, build, 72 hashes CRM e conferência visual do match passaram.

Na Hostinger, atualize IMAGE_TAG mantendo as demais variáveis e volumes, e reimplante docker-compose.prod.yaml. A VPS não foi implantada por esta publicação. Documentos e banco locais não integram as imagens.
