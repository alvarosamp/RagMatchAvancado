# Release de catálogo LPU e filtros progressivos — 14/10/2026

Código executável: `e02e0a0be0b567fc432c2b320e9d93052213bb20`.

Publicação concluída e digests remotos conferidos nos quatro repositórios, todos para Linux amd64 e com a mesma tag:

```text
sha-e02e0a0be0b567fc432c2b320e9d93052213bb20
```

- `alvarocareli/ragmatch-api`
- `alvarocareli/ragmatch-frontend`
- `alvarocareli/ragmatch-market-worker`
- `alvarocareli/ragmatch-mlflow`

[Manifesto com digests verificados](lpu-catalog-match-20261014.json). [Variáveis da release](lpu-catalog-match-20261014.env).

## Alterações revisadas

O popup de match abre a descrição completa e uma tabela com característica, valor do edital e escolhas disponíveis no catálogo. A seleção de categoria e valores reduz as demais opções progressivamente. Os filtros do catálogo não alteram as exigências do edital. A seleção permanece para revisão técnica.

A importação de LPU atualiza automaticamente o JSON técnico de cada produto, registra a origem e a versão, recalcula os atributos comerciais e preserva os atributos manuais/documentados. Ausência continua desconhecida. O editor de atributos do catálogo abre em uma tabela própria e preserva metadados e evidências dos valores não alterados.

Os scripts de coleta e estruturação de datasheets ficam versionados no código. Os JSONs/PDFs locais do usuário e os dados de demonstração não integram as imagens de produção.

## Validação e construção

108 testes unitários de regressão do backend, 42 testes do frontend, cinco testes do cliente de sessão, 97 testes HTTP contra a API final com dois workers e seis testes do coletor passaram. Os 74 hashes dos artefatos CRM conferem. A migração está em `20261013_01`; readiness, Nginx, CLI do worker e MLflow 2.12.1 passaram.

As imagens foram construídas a partir de um arquivo Git congelado do commit acima. API: `backend/Dockerfile.release`, com a base de dependências fixada; worker: base de produção anterior fixada por digest, com código atualizado, sem mudanças de requirements. Frontend: `frontend/Dockerfile`, com os patches reproduzíveis de sessão, match e edição de ficha. MLflow foi reutilizado sem alteração, mantendo seu digest anterior. Os hashes remotos foram comparados aos descritores locais testados.

## Hostinger — compose.prod

Foi validado `docker-compose.prod.yaml` com a tag desta release, usando valores de exemplo para as demais variáveis. API, serviços worker/scheduler, bootstrap, migração, frontend e MLflow resolvem a mesma `IMAGE_TAG`. O worker analítico separado também foi publicado com essa tag; o compose principal usa a imagem da API para seus workers.

No Docker Manager, atualize `IMAGE_TAG` nas variáveis existentes e implante o compose de produção. Preserve as demais variáveis, senhas, domínios e volumes da instalação. O arquivo `.env` desta release contém somente referências de versão; não substitui a configuração completa da Hostinger.

A publicação não implantou nem alterou a VPS da Hostinger. O código está commitado localmente; não houve push ou merge de branches no GitHub nesta publicação.
