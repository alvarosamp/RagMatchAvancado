#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/opt/backups/ragmatch}"
COMPOSE_ARGS=(--env-file .env.prod -f docker-compose.prod.yaml)
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

cd "$ROOT_DIR"
[[ -f .env.prod ]] || { echo '.env.prod nao encontrado.' >&2; exit 1; }
mkdir -p "$BACKUP_DIR"
umask 077

docker compose "${COMPOSE_ARGS[@]}" exec -T db \
  sh -ec 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' \
  > "$BACKUP_DIR/postgres-$STAMP.dump"

MINIO_CONTAINER="$(docker compose "${COMPOSE_ARGS[@]}" ps -q minio)"
[[ -n "$MINIO_CONTAINER" ]] || { echo 'Container MinIO nao esta em execucao.' >&2; exit 1; }
docker run --rm --volumes-from "$MINIO_CONTAINER" alpine:3.20 \
  tar -C /data -czf - . > "$BACKUP_DIR/minio-$STAMP.tgz"

sha256sum "$BACKUP_DIR/postgres-$STAMP.dump" "$BACKUP_DIR/minio-$STAMP.tgz" \
  > "$BACKUP_DIR/checksums-$STAMP.sha256"

if [[ "${SKIP_OFFSITE_BACKUP:-0}" == "1" ]]; then
  echo "AVISO: copia externa ignorada por SKIP_OFFSITE_BACKUP=1." >&2
  OFFSITE_STATUS="sem copia externa"
else
  docker compose "${COMPOSE_ARGS[@]}" run --rm --no-deps -T \
    -v "$BACKUP_DIR:/backup:ro" \
    -e BACKUP_STAMP="$STAMP" \
    backup-uploader
  OFFSITE_STATUS="copia externa verificada"
fi

echo "Backup criado em $BACKUP_DIR (PostgreSQL, MinIO, checksums; $OFFSITE_STATUS)."
