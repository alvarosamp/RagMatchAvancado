# commercial-20261009-v5

Atualização das telas de início, análise de editais, performance de produtos e inteligência competitiva. Inclui filtro do chat ConLicitação por item/lote, mantendo mensagens sem identificação visíveis e descartando respostas atrasadas ao trocar a licitação.

O empacotador agora inclui o build completo do frontend e o CRM; a imagem limpa os arquivos antigos antes de copiar o build. O Dockerfile do frontend usa Node 24.

## Validação

- 32 testes do frontend passaram (12 arquivos), incluindo as quatro telas com dados preenchidos, erro da API de analytics, expansão dos contrapontos e filtro de categoria.
- Build de produção passou.
- Homologação das imagens empacotadas no Docker sem volumes de código; login e telas em desktop e celular.
- Análise de editais e inteligência competitiva continuam seguindo a configuração existente de habilitação das funções de IA; seus componentes foram validados nos testes, sem ativar essas funções no ambiente local.

## Imagens

Todas usam a tag `commercial-20261009-v5` no namespace `alvarocareli`.

Publicação confirmada no Docker Hub com verificação dos digests remotos:

- `alvarocareli/ragmatch-api:commercial-20261009-v5`: `sha256:8a9fe6a879d67585bcf1dbfde8dc3dcadfa5c6d8596d91676a9459fd113a91b2`
- `alvarocareli/ragmatch-frontend:commercial-20261009-v5`: `sha256:25af7427f5cab9c4728bd9be8b4bdc8965aa7611530e37861b5d0ee2e934799e`
- `alvarocareli/ragmatch-market-worker:commercial-20261009-v5`: `sha256:4c72675127e91b917a854b1f724c50599c0a69c82dc041065900de6ae8f7df04`
- `alvarocareli/ragmatch-mlflow:commercial-20261009-v5`: `sha256:ce91a612c58c1272bf444ff1839302146902ff9097daed58ab059d5c06f43961`
