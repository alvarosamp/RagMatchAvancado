# CI/CD: GitHub Actions → Docker Hub → VPS

Pull requests executam lint, testes de backend/frontend, testes de inteligência
comercial e build das quatro imagens, sem publicar ou acessar a VPS. Push em
`main` publica somente depois desses checks. O smoke test executa a mesma imagem
que será enviada ao Docker Hub; não há um segundo build para publicação.

Os testes incluem PostgreSQL/Redis reais, isolamento entre empresas e navegação
em Chromium/Firefox no desktop e celular. A publicação exige cobertura combinada
do backend de pelo menos 50%, além dos limites dos módulos críticos. Veja os
cenários, metas e comandos em [Testes automatizados](TESTES_AUTOMATIZADOS.md).

## Como receber a tag

Abra **Actions → CI → execução → Summary**. O job **Export Verified Release**
mostra, por exemplo:

```env
IMAGE_TAG=sha-<commit completo>-<run_id>-<run_attempt>
MARKET_WORKER_IMAGE=alvarocareli/ragmatch-market-worker:sha-<commit completo>-<run_id>-<run_attempt>
DEPLOY_SHA=<commit completo>
```

Na mesma execução, baixe o artifact **dockerhub-release**. Ele contém:

- `deploy.env`: tag e commit para integração com outro deploy.
- `release.json`: referências completas, digests das quatro imagens e URL da execução.

As imagens são `alvarocareli/ragmatch-api`, `ragmatch-frontend`, `ragmatch-mlflow`
e `ragmatch-market-worker`, todas com a mesma tag. Cada tentativa recebe uma tag
distinta para não substituir uma imagem de uma execução anterior. `latest` não
é atualizado. A saída de job `image_tag` passa a release verificada ao deploy,
sem copiar a tag manualmente. Configure a política de tags imutáveis no Docker
Hub se quiser impedir também alterações feitas fora deste workflow.

## Configuração do GitHub

Em **Settings → Secrets and variables → Actions**, crie os secrets de repositório:

| Secret | Valor |
| --- | --- |
| `DOCKERHUB_USERNAME` | Usuário com permissão de publicação no namespace `alvarocareli` |
| `DOCKERHUB_TOKEN` | Token de acesso do Docker Hub com permissão de escrita |

Crie o environment **production**, restrito à branch `main`, com estes secrets:

| Secret | Valor |
| --- | --- |
| `VPS_HOST` | IP ou hostname da VPS |
| `VPS_USER` | Usuário SSH que pode executar Docker e acessar o checkout |
| `VPS_PORT` | Porta SSH; opcional, padrão `22` |
| `VPS_SSH_KEY` | Chave privada dedicada ao deploy; chave pública em `authorized_keys` |
| `VPS_APP_DIR` | Caminho absoluto do checkout, por exemplo `/opt/ragmatch` (sem espaços) |
| `VPS_KNOWN_HOSTS` | Linha da chave de host SSH da VPS, conferida por um canal confiável |

Obtenha a linha de `known_hosts` com `ssh-keyscan -p PORT HOST` e confira sua
fingerprint com `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` no console
confiável da VPS antes de cadastrá-la. Para porta diferente de 22, preserve
`[HOST]:PORT` na linha. O workflow exige essa chave conhecida e falha se algum
secret obrigatório estiver ausente.

Para ativar deploy automático, crie a **variável de repositório**
`AUTO_DEPLOY_VPS=true`. Enquanto ela não estiver ativada, push em `main` publica
a release e entrega a tag, sem fazer deploy. Reviewers obrigatórios no environment
fazem o Actions aguardar aprovação; configure isso conforme o fluxo desejado.

Para execução manual, abra **Run workflow** na branch `main` e marque
`publish_images` e `deploy_vps`. Marcar só `publish_images` publica e entrega a
tag. Solicitar deploy sem publicação ou de outra branch falha explicitamente.

## Preparação da VPS

A conexão parte do runner do GitHub para a VPS por SSH. A VPS precisa acessar
GitHub e Docker Hub para buscar os arquivos e imagens; não precisa instalar um
runner do Actions ou consultar a API do GitHub.

Prepare uma VPS Linux **amd64**, Git, Bash, `flock`, Docker e Docker Compose
**2.24.4 ou mais recente** (o overlay analítico usa `!reset`). O usuário de deploy
precisa acessar o Docker, escrever no diretório da aplicação e fazer `git fetch`
no origin. Se o repositório for privado, configure uma deploy key de leitura na
VPS. Para imagens privadas, faça `docker login` na VPS com um token de leitura.

No checkout, configure `.env.prod` com as credenciais e domínios exigidos por
`docker-compose.prod.yaml`; restrinja sua leitura ao usuário de deploy. Prepare
a rede externa `traefik-proxy`, o Traefik e os diretórios persistentes. Na primeira
instalação, disponibilize também as imagens de infraestrutura antes do deploy:

```bash
IMAGE_TAG=sha-<tag completa publicada> docker compose --env-file .env.prod \
  -f docker-compose.prod.yaml pull db pgbouncer redis minio ollama ollama-setup
```

O deploy faz pull das imagens da aplicação e usa `--pull never` ao iniciar,
preservando as imagens de infraestrutura locais. Ative o overlay analítico com
`DEPLOY_ANALYTICS=1` em `.env.prod` e configure suas credenciais restritas e tenants
conforme `docker-compose.analytics.yaml`. Sem essa opção, somente a stack base
é implantada. Perfis adicionais, como BI, exigem preparação específica.

O script extrai os arquivos Compose do **commit da release**, preservando o
checkout existente. Os mounts relativos continuam apontando para `VPS_APP_DIR`.
Se a stack atual usa um nome explícito de projeto, configure o mesmo
`COMPOSE_PROJECT_NAME` em `.env.prod` para evitar criar uma segunda stack.

Um lock impede dois deploys simultâneos. Após subir os containers, o script
verifica `/health/ready` da API (banco e Redis) e a página do frontend. Somente
então persiste `IMAGE_TAG`, `DEPLOY_SHA` e, se ativado, `MARKET_WORKER_IMAGE`.
Essa verificação é interna; valide domínio, TLS e acesso externo na preparação
inicial da VPS. Falhas após a troca dos containers podem deixar a release nova
parcialmente aplicada: o arquivo de configuração mantém a última tag aprovada.

## Recuperação

Guarde o artifact da última release saudável e faça backup do banco antes de
migrações. Para reaplicar uma release anterior publicada por este pipeline:

```bash
IMAGE_TAG=sha-<commit>-<run>-<attempt> DEPLOY_SHA=<commit> \
  bash scripts/deploy-production.sh
```

O commit precisa pertencer ao histórico de `main`. Reverter imagens não reverte
migrações do banco: confirme compatibilidade ou restaure um backup conforme a
estratégia de recuperação. O workflow não faz rollback automático de migrações.

Referências: [saídas entre jobs do Actions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-variables),
[environments de deploy](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/deploy-to-environment)
e [Docker com GitHub Actions](https://docs.docker.com/build/ci/github-actions/).
