# Publicação das correções do CRM — 14/10/2026

Tag comum publicada e conferida nos quatro repositórios `alvarocareli/ragmatch-api`, `alvarocareli/ragmatch-frontend`, `alvarocareli/ragmatch-market-worker` e `alvarocareli/ragmatch-mlflow`:

```
sha-273b400b76a8faae4b591948cc6ec7b2cb00f192
```

[Manifesto com digests remotos](crm-repairs-20261014.json). [Variáveis da implantação](crm-repairs-20261014.env). [Detalhes das correções](../crm-repairs-20261014.md).

Corrige a leitura operacional da inteligência de mercado, demanda atual na inteligência comercial, isolamento de falhas auxiliares, download nativo do JSON de um item, marca separada de tipo de produto, requisitos em linhas individuais e ficha técnica visível com fontes. Documentos de famílias com aplicabilidade pendente permanecem separados dos atributos do produto.

95 testes de backend, 19 testes das páginas/bibliotecas de inteligência e 44 testes HTTP passaram. O cenário completo também passou contra a imagem final de produção. Download real verificado no navegador e arquivo conferido em Downloads; telas de inteligência, filtros progressivos e ficha técnica conferidos visualmente. Os 72 hashes do CRM, Nginx, CLI do worker e compose de produção foram verificados. API pronta com a migração `20261014_01`.

Imagens Linux amd64 construídas de um arquivo Git congelado do commit `273b400b76a8faae4b591948cc6ec7b2cb00f192`, com as bases anteriores de dependências fixadas por digest. MLflow inalterado, publicado com a mesma tag. Documentos, JSONs locais de produtos e banco não integram as imagens.

Na Hostinger, preserve variáveis, credenciais e volumes existentes; atualize `IMAGE_TAG` e reimplante `docker-compose.prod.yaml`. API, frontend, MLflow, migração, bootstrap e workers usam a mesma tag. Se houver o worker analítico separado, atualize também `MARKET_WORKER_IMAGE`. A VPS não foi implantada por esta publicação. Não houve push de código no GitHub.
