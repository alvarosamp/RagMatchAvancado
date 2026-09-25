# Produção na VPS

Este guia considera a VPS Hostinger atual, que já usa Docker Compose e Traefik.
O Traefik é o único serviço público nas portas 80/443; não instale Caddy.

## Atualização da VPS existente

1. Faça um snapshot no hPanel antes de qualquer mudança em uma base existente.
2. No diretório `/docker/sistemator`, mantenha as variáveis existentes e adicione
   as novas variáveis do `.env.prod.example`. Confira `APP_DOMAIN`, `API_DOMAIN`
   e a rede externa `traefik-proxy` antes de substituir o Compose atual.
3. Atualize o `docker-compose.yml` com a versão de produção e valide com
   `docker compose config -q`.
4. Execute `docker compose pull` e depois `docker compose up -d --remove-orphans`.
5. Confira `docker compose ps` e `docker compose logs --tail=200`.

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
snapshot atual dos modelos, habilita as políticas RLS e marca a revisão
`20260922_02`. Esse caminho é deliberadamente fixado nessa revisão: quando uma
nova migration virar `head`, o bootstrap recusará um banco vazio até o snapshot
ser atualizado e testado. Não aponte o bootstrap para um banco parcialmente
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
Para rollback, restaure o `docker-compose.yml` salvo ou use uma tag SHA anterior e
execute o mesmo comando.

## Antes de abrir para clientes

- Rode um fluxo real: upload, OCR, embeddings, match e exportação.
- Meça CPU, RAM, fila Redis e tempo por tipo de edital antes de aumentar a VPS.
- Monte um conjunto congelado de casos revisados por especialista e acompanhe
  precisão, recall e falsos positivos de `ATENDE` no MLflow.
- Valide isolamento entre tenants, autorização e limite de requisições antes de
  atender empresas independentes.
