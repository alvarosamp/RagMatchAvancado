# Declarações complementares Tor — 15/10/2026

As quatro imagens foram publicadas e os digests remotos conferidos no Docker Hub: API, frontend, market-worker e MLflow.

```env
IMAGE_TAG=sha-0822d57c2f8e8118b89ff38ff709ac762acd0394
```

[Manifesto e digests](tor-declaration-20261015.json). [Variáveis para implantação](tor-declaration-20261015.env). [Funcionalidade e validação](../complementary-declaration.md).

Código no commit `0822d57c2f8e8118b89ff38ff709ac762acd0394`, branch `codex/technical-match-v8`. API, frontend e worker Linux amd64 construídos de uma exportação Git congelada; MLflow reutilizado sem alteração. A declaração usa o papel timbrado Tor e conserva pendências, sem assinar ou confirmar atendimento automaticamente.

Validação: 13 testes documentais, nove testes frontend, teste HTTP contra a imagem final (geração/download, isolamento entre empresas e preservação do match), download nativo no navegador, revisão visual do Word, Nginx e inicialização do worker.

Na Hostinger, mantenha as demais variáveis e volumes, atualize IMAGE_TAG no ambiente e reimplante `docker-compose.prod.yaml`. Se usar o worker analítico, atualize também MARKET_WORKER_IMAGE conforme o arquivo de variáveis. A VPS não foi implantada por esta publicação. A prévia Docker local já usa as imagens desta release. Dados locais, credenciais de QA e documentos enviados não integram as imagens.
