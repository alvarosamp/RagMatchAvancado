# Release commercial-20261009-v1

Versão comum da API, frontend e worker de inteligência comercial. Inclui dashboard CRM integrado, explorador produto × demanda, vínculos de fornecedores normalizados, apresentação de demanda para fornecedor, relatórios e área dedicada de previsão. Bling continua desabilitado por padrão e tratado como integração futura.

Publicação concluída no Docker Hub em 09/10/2026. Os digests remotos foram conferidos com os manifests das imagens construídas e testadas.

## Imagens

- `alvarocareli/ragmatch-api:commercial-20261009-v1`
- `alvarocareli/ragmatch-frontend:commercial-20261009-v1`
- `alvarocareli/ragmatch-market-worker:commercial-20261009-v1`
- `alvarocareli/ragmatch-mlflow:commercial-20261009-v1` — mesma imagem da versão anterior, apenas a tag comum para compatibilidade da composição.

| Componente | Digest remoto |
|---|---|
| API | `sha256:e850e2af1180540a73ce2c7ccb7c76c99812a6152520dafff158024672f6b6f6` |
| Frontend | `sha256:4540cfb4fa11a503edf163436e8bb1638894807f7ccdcd007ef41d75438bace2` |
| Worker analítico | `sha256:e4c431f731e0dd46609f71c805414006e45ec494da36a13753bdb27383711baa` |
| MLflow existente | `sha256:ce91a612c58c1272bf444ff1839302146902ff9097daed58ab059d5c06f43961` |

As imagens incorporam a implementação do working tree, inclusive alterações ainda não commitadas. O label `io.ragmatch.source-sha256` identifica os arquivos incorporados em cada componente; não é apresentado como SHA de commit. API e portal reutilizam as dependências das imagens já validadas `sha-97a06d2e21c0ae69ecc971a7f42d7f76147a703a`. O worker reutiliza o ambiente analítico compatível testado localmente, com FastAPI 0.116.1 e Starlette 0.47.3. A API inicia sem reload; o worker executa como usuário 10001.

## Validação da versão

69 testes analíticos e 71 testes frontend aprovados na entrega de funcionalidades. TypeScript, lint e build frontend aprovados. As três imagens foram construídas e executadas no Docker local **sem qualquer montagem do código**. Login, processamento das cargas CRM, isolamento entre duas empresas, relatório e CSV foram verificados pelo proxy. Edge confirmou o dashboard principal, exploração, escolha de fornecedor, cenário, exportação HTML/PDF e avaliações de demanda e preço processadas pelo worker.

Os dados de demonstração continuam indicando histórico insuficiente para previsão; não houve inserção de histórico artificial. A migração analítica necessária é `20261009_01`; o worker exige conta sem SUPERUSER/BYPASSRLS e tenants autorizados em `MARKET_TENANT_IDS`.

## Uso local das imagens

```powershell
$env:MARKET_RELEASE_TAG = 'commercial-20261009-v1'
docker compose -p ragmatch-market-test -f docker-compose.analytics.test.yaml -f docker-compose.analytics.release-test.yaml up -d --no-deps api worker-data frontend
```

O banco demo existente é preservado. O overlay de release remove as montagens do código. Esta publicação de imagens não executa implantação na VPS.

Para a composição publicada existente, a versão comum é `IMAGE_TAG=commercial-20261009-v1`. O overlay analítico usa `MARKET_WORKER_IMAGE=alvarocareli/ragmatch-market-worker:commercial-20261009-v1`, além das credenciais restritas e IDs de tenants configurados no ambiente de destino. O MLflow preserva o digest original `sha-97a06d2e21c0ae69ecc971a7f42d7f76147a703a`.

## Processo para as próximas entregas

Conforme autorizado pelo usuário em 09/10/2026, publicar novas versões no Docker Hub após avançar e validar implementações. Usar uma tag nova comum aos três componentes, registrar evidências e confirmar os digests remotos. Não substituir uma tag de versão existente; usar o número seguinte. A publicação das imagens e a implantação em outro ambiente são etapas distintas.

1. Executar os checks apropriados e gerar o CRM com `npm --prefix bid-buddy run build:embed`.
2. Construir com `.venv/Scripts/python.exe analytics/build_release.py --tag NOVA_TAG`. Para usar o worker publicado como base compatível: `--worker-base alvarocareli/ragmatch-market-worker:commercial-20261009-v1`. Alterações de dependências exigem reconstrução e nova homologação da base pelo Dockerfile analítico.
3. Definir `MARKET_RELEASE_TAG=NOVA_TAG`, executar o overlay e conferir a composição com `docker compose ... config --quiet`. Testar a release sem montagens, incluindo login, isolamento e fluxos alterados.
4. Conferir se as tags estão disponíveis e executar `docker push alvarocareli/ragmatch-api:NOVA_TAG`, `docker push alvarocareli/ragmatch-frontend:NOVA_TAG` e `docker push alvarocareli/ragmatch-market-worker:NOVA_TAG`.
5. Verificar cada imagem com `docker buildx imagetools inspect IMAGEM:TAG`, registrar os digests e o hash dos arquivos no manifesto. O builder gera o manifesto local em `analytics/.validation/releases/TAG/manifest.json`.
6. Quando a composição usar uma tag global também para MLflow, manter uma tag correspondente nesse repositório. Sem alteração de MLflow, copiar o manifesto já publicado para a nova tag e confirmar que o digest permanece igual.

Os workflows de testes continuam necessários para a publicação por CI. O workflow geral antigo publica API, frontend e MLflow; o worker analítico desta release exige o procedimento acima. Não assumir que um dispatch daquele workflow contém o working tree não commitado ou publica o novo worker.
