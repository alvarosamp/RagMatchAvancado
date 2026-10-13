#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
[[ -f .env.prod ]] || { echo '.env.prod nao encontrado.' >&2; exit 1; }

# Uma unica tag identifica API, workers, frontend e MLflow.
IMAGE_TAG="${IMAGE_TAG:-$(sed -n 's/^IMAGE_TAG=//p' .env.prod | tail -n 1)}"
if [[ ! "$IMAGE_TAG" =~ ^sha-[0-9a-f]{40}$ ]]; then
  echo 'IMAGE_TAG invalida. Use sha- seguido pelo SHA completo de 40 caracteres.' >&2
  exit 1
fi
DEPLOY_COMMIT="${DEPLOY_COMMIT:-${IMAGE_TAG#sha-}}"
[[ "$IMAGE_TAG" == "sha-${DEPLOY_COMMIT}" ]] || {
  echo 'DEPLOY_COMMIT e IMAGE_TAG devem identificar o mesmo commit.' >&2; exit 1;
}

# Nao avanca para a ponta da main: codigo e imagens pertencem ao mesmo commit.
git fetch origin "$DEPLOY_COMMIT"
git checkout --detach "$DEPLOY_COMMIT"
export IMAGE_TAG
COMPOSE_ARGS=(--env-file .env.prod -f docker-compose.prod.yaml)

# Baixa todas as imagens antes de alterar a versao persistida ou os containers.
docker compose "${COMPOSE_ARGS[@]}" config -q
docker compose "${COMPOSE_ARGS[@]}" pull

# Grava atomicamente a tag desejada; o arquivo nao fica truncado em caso de erro.
env_tmp="$(mktemp .env.prod.XXXXXX)"
trap 'rm -f "$env_tmp"' EXIT
cp -p .env.prod "$env_tmp"
awk -v tag="$IMAGE_TAG" '
  /^IMAGE_TAG=/ { if (!seen++) print "IMAGE_TAG=" tag; next }
  { print }
  END { if (!seen) print "IMAGE_TAG=" tag }
' .env.prod > "$env_tmp"
mv "$env_tmp" .env.prod

# --wait confirma running/healthy; servicos sem healthcheck so confirmam running.
docker compose "${COMPOSE_ARGS[@]}" up -d --remove-orphans --wait --wait-timeout "${DEPLOY_WAIT_TIMEOUT:-600}"
docker compose "${COMPOSE_ARGS[@]}" ps
printf 'Deploy concluido: IMAGE_TAG=%s\n' "$IMAGE_TAG"
