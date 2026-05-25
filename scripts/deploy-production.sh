#!/usr/bin/env bash
set -euo pipefail

DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_ARGS=(-f docker-compose.prod.yaml)

cd "$ROOT_DIR"

if [[ -f .env.prod ]]; then
  COMPOSE_ARGS=(--env-file .env.prod "${COMPOSE_ARGS[@]}")
fi

git fetch origin "$DEPLOY_BRANCH"
git checkout "$DEPLOY_BRANCH"
git pull --ff-only origin "$DEPLOY_BRANCH"

docker compose "${COMPOSE_ARGS[@]}" pull api frontend mlflow
docker compose "${COMPOSE_ARGS[@]}" up -d --remove-orphans db mlflow api frontend ollama
docker image prune -f
