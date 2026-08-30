#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_ARGS=(--env-file .env.prod -f docker-compose.prod.yaml)

cd "$ROOT_DIR"
docker compose "${COMPOSE_ARGS[@]}" config -q
docker compose "${COMPOSE_ARGS[@]}" ps
curl --fail --show-error --silent http://127.0.0.1:8080/api/health
echo
curl --fail --show-error --silent http://127.0.0.1:8080/api/health/ready
echo
