# Produção na VPS

Este guia considera a VPS Hostinger atual, que já usa Docker Compose e Traefik.
O Traefik é o único serviço público nas portas 80/443; não instale Caddy.

## Primeiro deploy

1. Faça um snapshot no hPanel antes de qualquer mudança.
2. No diretório `/docker/sistemator`, mantenha as variáveis existentes e adicione
   as novas variáveis do `.env.prod.example`. `APP_DOMAIN`, `APP_SUBDOMAIN` e
   `APP_INTERNAL_NETWORK=sistemator_app-internal` preservam o roteamento atual.
3. Atualize o `docker-compose.yml` com a versão de produção e valide com
   `docker compose config -q`.
4. Execute `docker compose pull` e depois `docker compose up -d --remove-orphans`.
5. Confira `docker compose ps` e `docker compose logs --tail=200`.

O frontend não publica portas no host: o Traefik o acessa pela rede externa
`traefik-proxy`. PostgreSQL, Redis, MinIO, MLflow e Ollama não têm portas
públicas. O serviço `ollama-init` baixa
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
e gravações nessas tabelas não retornam nem aceitam linhas. As tabelas CRM continuam
com os filtros explícitos atuais e devem receber RLS em uma migration posterior,
depois de adaptar cada rotina global/scheduler.

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
