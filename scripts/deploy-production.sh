#!/usr/bin/env bash
set -euo pipefail

DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_ARGS=(-f docker-compose.prod.yaml)

cd "$ROOT_DIR"

[[ -f .env.prod ]] || { echo '.env.prod nao encontrado.' >&2; exit 1; }

# O CI envia IMAGE_TAG=sha-<commit>. Quando o script for executado
# manualmente, reutiliza a tag ja persistida no arquivo da VPS.
IMAGE_TAG="${IMAGE_TAG:-$(sed -n 's/^IMAGE_TAG=//p' .env.prod | tail -n 1)}"
if [[ ! "$IMAGE_TAG" =~ ^sha-[0-9a-f]{40}$ ]]; then
  echo 'IMAGE_TAG invalida. Use sha- seguido pelo SHA completo de 40 caracteres.' >&2
  exit 1
fi

export IMAGE_TAG

COMPOSE_ARGS=(--env-file .env.prod "${COMPOSE_ARGS[@]}")

git fetch origin "$DEPLOY_BRANCH"
git checkout "$DEPLOY_BRANCH"
git pull --ff-only origin "$DEPLOY_BRANCH"

# Valida variaveis obrigatorias e a composicao antes de trocar containers.
docker compose "${COMPOSE_ARGS[@]}" config -q
docker compose "${COMPOSE_ARGS[@]}" pull
# Nao remover outros containers do mesmo projeto (ex.: CRM da VPS).
docker compose "${COMPOSE_ARGS[@]}" up -d

# So persiste a tag depois de o Compose aceitar a atualizacao.
if grep -q '^IMAGE_TAG=' .env.prod; then
  sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=${IMAGE_TAG}/" .env.prod
else
  printf '\nIMAGE_TAG=%s\n' "$IMAGE_TAG" >> .env.prod
fi
docker compose "${COMPOSE_ARGS[@]}" ps
