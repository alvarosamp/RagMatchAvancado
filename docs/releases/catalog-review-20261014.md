# Publicação da revisão documental — 14/10/2026

As quatro imagens foram publicadas e seus digests remotos conferidos na conta alvarocareli:

```
IMAGE_TAG=sha-c4f9745bc4e28634e4eed150efa60fdb9634dccd
```

Repositórios: ragmatch-api, ragmatch-frontend, ragmatch-market-worker e ragmatch-mlflow. [Manifesto](catalog-review-20261014.json), [variáveis](catalog-review-20261014.env), [comportamento e validação](../catalog-extraction-review-20261014.md).

A imagem frontend Linux amd64 foi construída de uma exportação Git congelada do commit `c4f9745bc4e28634e4eed150efa60fdb9634dccd`. API, worker e MLflow foram republicados sem mudanças com a mesma tag. Arquivos de produtos, PDFs locais e banco não integram as imagens.

Inclui descrição separada da tabela, grupos por documento/escopo, limites legíveis, rótulos em português, alerta XFP/SFP+ e adoção de atributos em rascunho preservando fonte e estado de revisão. Passaram 22 testes de frontend, replay do patch e build limpo. Foram conferidos 72 hashes dos artefatos CRM e o fluxo de adoção no navegador.

Para a Hostinger, preserve as demais variáveis e volumes, atualize IMAGE_TAG e reimplante docker-compose.prod.yaml. A publicação no Docker Hub não atualizou a VPS.
