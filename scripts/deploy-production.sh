#!/usr/bin/env bash
set -euo pipefail

DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_ARGS=(-f docker-compose.prod.yaml)

cd "$ROOT_DIR"

[[ -f .env.prod ]] || { echo '.env.prod nao encontrado.' >&2; exit 1; }
COMPOSE_ARGS=(--env-file .env.prod "${COMPOSE_ARGS[@]}")

git fetch origin "$DEPLOY_BRANCH"
git checkout "$DEPLOY_BRANCH"
git pull --ff-only origin "$DEPLOY_BRANCH"

# Valida variaveis obrigatorias e a composicao antes de trocar containers.
docker compose "${COMPOSE_ARGS[@]}" config -q
docker compose "${COMPOSE_ARGS[@]}" pull
docker compose "${COMPOSE_ARGS[@]}" up -d --remove-orphans
docker compose "${COMPOSE_ARGS[@]}" ps
