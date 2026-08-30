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

## Backups

Agende `BACKUP_DIR=/opt/backups/ragmatch bash scripts/backup-production.sh` uma vez
ao dia via cron/systemd timer. Ele salva dump lógico PostgreSQL, dados do MinIO e
checksums. Copie esses arquivos para um destino externo e execute restores de teste
regularmente; snapshots semanais da VPS não substituem esse processo.

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
