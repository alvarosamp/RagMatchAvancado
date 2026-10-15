#!/usr/bin/env bash
set -euo pipefail

# Via SSH (bash -s), o Actions ja entra na pasta da aplicacao.
if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
  ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
else
  ROOT_DIR="$PWD"
fi
cd "$ROOT_DIR"
[[ -f .env.prod ]] || { echo '.env.prod nao encontrado.' >&2; exit 1; }

# Nao executar .env.prod como shell: ele contem configuracao, nao codigo.
read_setting() { sed -n "s/^${1}=//p" .env.prod | tail -n 1; }
IMAGE_TAG="${IMAGE_TAG:-$(read_setting IMAGE_TAG)}"
if [[ ! "$IMAGE_TAG" =~ ^sha-([0-9a-f]{40})(-[0-9]+-[0-9]+)?$ ]]; then
  echo 'IMAGE_TAG invalida: esperado sha-<commit>[-<run>-<attempt>].' >&2
  exit 1
fi
TAG_SHA="${BASH_REMATCH[1]}"
DEPLOY_SHA="${DEPLOY_SHA:-$TAG_SHA}"
[[ "$DEPLOY_SHA" == "$TAG_SHA" ]] || { echo 'Commit e tag nao correspondem.' >&2; exit 1; }
export IMAGE_TAG

# Bloqueia tambem deploys manuais concorrentes na VPS.
exec 9>"$ROOT_DIR/.deploy.lock"
flock -n 9 || { echo 'Outro deploy esta em andamento.' >&2; exit 1; }
git fetch origin main
git cat-file -e "${DEPLOY_SHA}^{commit}"
git merge-base --is-ancestor "$DEPLOY_SHA" origin/main || {
  echo 'O commit precisa pertencer ao historico de main.' >&2; exit 1;
}

# Usa os arquivos do commit publicado sem sobrescrever o checkout da VPS.
# --project-directory preserva os mounts e o nome padrao do projeto Compose.
RELEASE_DIR="$(mktemp -d)"
trap 'rm -rf -- "$RELEASE_DIR"' EXIT
FILES=(docker-compose.prod.yaml)
ENABLE_ANALYTICS="${DEPLOY_ANALYTICS:-$(read_setting DEPLOY_ANALYTICS)}"
if [[ "$ENABLE_ANALYTICS" == 1 ]]; then
  FILES+=(docker-compose.analytics.yaml docker-compose.analytics.prod.yaml)
  export MARKET_WORKER_IMAGE="alvarocareli/ragmatch-market-worker:${IMAGE_TAG}"
fi
git archive "$DEPLOY_SHA" "${FILES[@]}" | tar -x -C "$RELEASE_DIR"
COMPOSE_ARGS=(--project-directory "$ROOT_DIR" --env-file "$ROOT_DIR/.env.prod")
for file in "${FILES[@]}"; do COMPOSE_ARGS+=(-f "$RELEASE_DIR/$file"); done
compose() { docker compose "${COMPOSE_ARGS[@]}" "$@"; }

compose config -q
# Atualiza somente imagens da aplicacao; infraestrutura mantem a versao instalada.
SERVICES=(api worker worker-ai worker-conlicitacao scheduler migrate db-bootstrap frontend mlflow)
if [[ "$ENABLE_ANALYTICS" == 1 ]]; then SERVICES+=(worker-data data-scheduler); fi
compose pull "${SERVICES[@]}"
compose up -d --no-build --pull never --wait --wait-timeout 300

# --wait verifica containers; readiness verifica banco e Redis atraves da API.
ready=false
for attempt in $(seq 1 30); do
  if compose exec -T api python -c '
import os, urllib.request
host = os.environ["ALLOWED_HOSTS"].split(",")[0].strip()
request = urllib.request.Request("http://127.0.0.1:8000/health/ready", headers={"Host": host})
with urllib.request.urlopen(request, timeout=5) as response:
    assert response.status == 200
'; then ready=true; break; fi
  sleep 2
done
[[ "$ready" == true ]] || { echo 'API nao ficou pronta; release nao registrada como saudavel.' >&2; exit 1; }
compose exec -T frontend wget -q -O /dev/null http://127.0.0.1/

# Registra a release apenas apos as verificacoes. Nao faz rollback automatico
# de banco: migracoes podem exigir uma estrategia especifica de restauracao.
persist_setting() {
  if grep -q "^${1}=" .env.prod; then
    sed -i "s|^${1}=.*|${1}=${2}|" .env.prod
  else
    printf '\n%s=%s\n' "$1" "$2" >> .env.prod
  fi
}
persist_setting IMAGE_TAG "$IMAGE_TAG"
persist_setting DEPLOY_SHA "$DEPLOY_SHA"
if [[ "$ENABLE_ANALYTICS" == 1 ]]; then persist_setting MARKET_WORKER_IMAGE "$MARKET_WORKER_IMAGE"; fi
compose ps
echo "Deploy verificado: ${IMAGE_TAG}"
