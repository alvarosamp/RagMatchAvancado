# Produção na VPS

Este guia considera a VPS Hostinger atual, que já usa Docker Compose e Traefik.
O Traefik é o único serviço público nas portas 80/443; não instale Caddy.

## CI/CD e tag compartilhada

Cada push na `main` executa os testes, publica as três imagens no Docker Hub com
`sha-<SHA completo de 40 caracteres>` e faz deploy por SSH depois de verificar que
as três imagens existem. API, frontend, MLflow, workers e migrations usam a mesma
variável `IMAGE_TAG`. `latest` continua disponível no Docker Hub, mas o deploy usa
sempre a tag SHA. A tag fica no resumo da execução em **Actions → CI → Summary**,
com links para as imagens, e no artefato `release-<SHA>` como `release.env`.

Cadastre em **Settings → Secrets and variables → Actions**:

| Secret | Valor |
| --- | --- |
| `DOCKERHUB_USERNAME` | Usuário com permissão de publicar em `alvarocareli` |
| `DOCKERHUB_TOKEN` | Token do Docker Hub com permissão de escrita |
| `VPS_HOST` | IP ou hostname da VPS Hostinger |
| `VPS_USER` | Usuário SSH com acesso ao Docker e ao checkout |
| `VPS_SSH_KEY` | Chave privada SSH desse usuário |
| `VPS_APP_DIR` | Caminho absoluto do clone Git na VPS, por exemplo `/docker/sistemator` |
| `VPS_PORT` | Opcional; padrão `22` |

Os secrets de VPS podem ficar no environment `production`. Se esse environment
exigir aprovação, o GitHub aguardará a aprovação antes do deploy. Secrets ausentes
fazem o deploy falhar explicitamente.

Na VPS, o diretório deve ser um clone deste repositório, com acesso de leitura ao
remote `origin`, Docker Compose v2 com suporte a `up --wait` e `.env.prod`
preenchido conforme `.env.prod.example`. Se as imagens forem privadas, execute
`docker login` na VPS com um token de leitura. As credenciais da aplicação ficam
no `.env.prod` da VPS. O pipeline não sobrescreve essas credenciais.

O deploy usa `docker-compose.prod.yaml` e checkout no commit exato das imagens.
Ele baixa as imagens antes de persistir `IMAGE_TAG` no `.env.prod` e aguarda os
containers ficarem running/healthy. Serviços sem healthcheck só têm o estado
running confirmado. Se o startup falhar, o pipeline falha e a tag desejada fica
registrada para diagnóstico; não há rollback automático de banco ou containers.

Para execução manual, use **Run workflow** na `main`: `publish_images` publica sem
deploy; `deploy_vps` publica e faz deploy mesmo com `publish_images` desmarcado.
Outras branches podem publicar imagens para testes, mas não fazem deploy em produção.

## Atualização da VPS existente

1. Faça um snapshot no hPanel antes de qualquer mudança em uma base existente.
2. No clone da VPS, mantenha as variáveis existentes no `.env.prod` e adicione as
   variáveis de `.env.prod.example`. Confira domínios e a rede `traefik-proxy`.
3. Preserve o nome do projeto Compose da stack atual para reutilizar volumes:
   defina `COMPOSE_PROJECT_NAME` no `.env.prod` com o nome existente, consultável
   por `docker compose ls`. A primeira adoção não deve criar uma segunda stack.
4. Confira também o certificado Traefik: este Compose usa `letsencrypt`; o
   resolver configurado na VPS deve corresponder aos labels do arquivo.
5. Depois da publicação, execute o workflow ou, no clone da VPS:

```bash
IMAGE_TAG=sha-<SHA_COMPLETO_PUBLICADO> bash scripts/deploy-production.sh
```

O Compose alternativo `deploy/docker-compose.hostinger-test.yml` também exige
`IMAGE_TAG` única, sem tags independentes por serviço.

O frontend não publica portas no host: o Traefik o acessa pela rede externa
`traefik-proxy`. PostgreSQL, Redis, MinIO, MLflow e Ollama não têm portas
públicas. O serviço `ollama-setup` baixa
`nomic-embed-text` e `llama3.2:1b` uma única vez no volume persistente antes de
API e workers iniciarem.

`DB_POOL_SIZE` e `DB_MAX_OVERFLOW` do `.env.prod` agora são injetados nos
processos que usam SQLAlchemy. Em uma VPS de 4 vCPU, comece com os valores de
exemplo (10/10) e ajuste-os apenas com base nas métricas de conexões e latência.

## Autenticação e recuperação de senha

Configure `SMTP_*` e `PASSWORD_RESET_URL_BASE` antes de disponibilizar a
recuperação de senha. O link expira em 30 minutos por padrão, é de uso único e
somente o hash do token fica no banco. Alterar ou redefinir a senha incrementa a
versão de autenticação do usuário e invalida todas as sessões anteriores.
Para Google Workspace, siga o procedimento de relay por IP e o teste operacional
em `docs/google-workspace-smtp-relay.md`.

O importador legado não contém mais senha padrão. Se ele precisar criar a conta
técnica durante uma migração, defina `SALES_IMPORT_BOOTSTRAP_PASSWORD` apenas
durante essa execução e remova a variável depois. Como versões antigas do código
continham uma credencial conhecida, altere imediatamente a senha de qualquer conta
criada por esse fluxo antes de expor o sistema a clientes.

## Isolamento de tenants e RLS

A migration `20260921_01` converte `editais.tenant_id` e `jobs.tenant_id` do slug
textual para a chave numérica de `tenants`, incluindo o `tenant_id` guardado no
payload dos jobs. Ela cancela a execução se encontrar qualquer slug sem empresa
correspondente; não descarta nem atribui dados automaticamente.

Faça essa atualização em janela de manutenção, depois de um backup verificado. A
migration recria colunas, índices e chaves estrangeiras dessas duas tabelas, então
pode obter locks enquanto estiver rodando. Embora workers novos consigam resolver
mensagens antigas que ainda carreguem slug, pause API, scheduler e workers durante
a migration e suba todos com a mesma versão logo depois.

As tabelas `editais` e `jobs` usam `FORCE ROW LEVEL SECURITY`. A autenticação grava
o ID do tenant na transação PostgreSQL e o contexto é reaplicado depois de cada
commit, inclusive com PgBouncer em modo `transaction`. Sem esse contexto, consultas
e gravações nessas tabelas não retornam nem aceitam linhas. A migration
`20260922_01` aplica a mesma política às 20 tabelas CRM com `tenant_id`; a revisão
`20260922_02` cobre outras sete tabelas de documentos, importação, decisões e
auditoria. O monitor de e-mails agendado agora processa cada tenant em seu próprio
contexto; a execução manual pela API permanece restrita ao tenant autenticado e
não marca mensagens como lidas na caixa compartilhada. Tabelas filhas sem
`tenant_id` direto ainda exigem auditoria de acesso por vínculo com o registro-pai.
`users` e tokens de recuperação também permanecem fora do RLS, pois a autenticação
precisa resolver o usuário antes de definir o contexto do tenant.

Defina `APP_DB_USER` e `APP_DB_PASSWORD` no `.env.prod`, com credenciais diferentes
de `POSTGRES_USER`/`POSTGRES_PASSWORD`. No Compose de produção, `migrate` usa a conta
administrativa; `db-bootstrap` cria/atualiza a conta restrita após a migration e
concede apenas DML nas tabelas e uso das sequências. API, PgBouncer, workers e
scheduler usam a conta restrita. Não execute esses processos com `postgres` nem
conceda `SUPERUSER` ou `BYPASSRLS` à conta da aplicação. O startup da API agora
verifica esses atributos e o RLS e falha se estiverem incorretos; ele não modifica
mais o esquema em produção. Em desenvolvimento, a inicialização automática atual
continua disponível. A senha é passada por `PGPASSWORD`, sem interpolação na
`DATABASE_URL`; use uma senha forte com caracteres especiais normalmente.

O serviço `migrate` distingue banco existente de banco totalmente vazio. No banco
existente, executa `alembic upgrade head`. No vazio, cria o esquema a partir do
snapshot operacional dos modelos, habilita as políticas RLS e marca a revisão
`20260926_01`. Em seguida aplica a migração analítica `20261009_01`, que usa
metadados próprios e não faz parte do snapshot operacional. Em produção, um banco
vazio exige `ALLOW_EMPTY_DATABASE_BOOTSTRAP=1`. Heads futuras não validadas são
recusadas até que o bootstrap seja atualizado e testado. Não aponte o bootstrap para um banco parcialmente
inicializado. O RLS também não substitui autorização na API: quem consegue executar
SQL arbitrário com a conta da aplicação pode definir o parâmetro de tenant da
própria transação.

## Backups

Configure `BACKUP_S3_*` no `.env.prod` com um bucket de outro provedor e
credenciais exclusivas de backup. Não reutilize o MinIO da mesma VPS. Ative no
bucket versionamento, retenção/imutabilidade e uma regra de ciclo de vida compatível
com o contrato do produto.

Agende `BACKUP_DIR=/opt/backups/ragmatch bash scripts/backup-production.sh` uma vez
ao dia via cron/systemd timer. Ele gera o dump lógico PostgreSQL, arquiva os dados
do MinIO, calcula SHA-256, envia o conjunto ao storage externo e valida tamanho e
checksum remoto. O comando falha se qualquer uma dessas etapas falhar. Apenas em
uma emergência operacional use `SKIP_OFFSITE_BACKUP=1`; essa execução ficará
explicitamente marcada como sem cópia externa.

Faça uma restauração mensal em ambiente isolado e registre data, duração e
resultado. Snapshots da VPS complementam, mas não substituem, a cópia externa nem
o teste de restauração.

## Atualização manual

O botão **Atualizar** do hPanel é apropriado apenas depois de a imagem Docker já
ter sido publicada. Alterações de Compose, como adicionar workers ou redes, devem
ser aplicadas no terminal da VPS com `docker compose up -d --remove-orphans`.
Para retornar às imagens de um commit anterior, execute o script com a tag SHA
anterior. Verifique antes a compatibilidade do banco: retornar imagens não desfaz
migrations e pode exigir a restauração de um backup.

## Antes de abrir para clientes

- Rode um fluxo real: upload, OCR, embeddings, match e exportação.
- Meça CPU, RAM, fila Redis e tempo por tipo de edital antes de aumentar a VPS.
- Monte um conjunto congelado de casos revisados por especialista e acompanhe
  precisão, recall e falsos positivos de `ATENDE` no MLflow.
- Valide isolamento entre tenants, autorização e limite de requisições antes de
  atender empresas independentes.
