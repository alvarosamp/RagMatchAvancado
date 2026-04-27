# =============================================================================
# Makefile — RagMatch Avançado
#
# CONCEITO MLOPS: "Developer Experience"
# Um Makefile padroniza todos os comandos do projeto em um lugar.
# Em vez de lembrar flags e variáveis, você só digita: make test, make up, etc.
#
# Como ver todos os comandos disponíveis:
#   make help
# =============================================================================

.PHONY: help up down logs build rebuild test test-cov test-all \
        lint lint-fix format mlflow-ui evaluate drift-check promote \
        shell-api shell-db

# ── Cores para output legível ─────────────────────────────────────────────────
BOLD  := \033[1m
RESET := \033[0m
GREEN := \033[32m
BLUE  := \033[34m

# ─────────────────────────────────────────────────────────────────────────────
help:
	@printf "\n$(BOLD)RagMatch Avançado — Comandos Disponíveis$(RESET)\n\n"
	@printf "$(BLUE)Docker$(RESET)\n"
	@printf "  make up           Sobe todos os serviços (api, db, mlflow, ollama, frontend)\n"
	@printf "  make down         Para e remove os containers\n"
	@printf "  make logs         Tail dos logs da API\n"
	@printf "  make build        Build das imagens sem cache\n"
	@printf "  make rebuild      Down + Build + Up\n"
	@printf "  make shell-api    Shell interativo dentro do container da API\n"
	@printf "  make shell-db     psql dentro do PostgreSQL\n"
	@printf "\n$(BLUE)Qualidade de Código$(RESET)\n"
	@printf "  make lint         Verifica estilo com ruff (sem corrigir)\n"
	@printf "  make lint-fix     Corrige automaticamente com ruff\n"
	@printf "  make format       Formata com black + ruff\n"
	@printf "\n$(BLUE)Testes$(RESET)\n"
	@printf "  make test         Roda testes unitários (rápido, sem infra)\n"
	@printf "  make test-cov     Testes + relatório de cobertura HTML\n"
	@printf "  make test-all     Todos os testes incluindo integração\n"
	@printf "\n$(BLUE)MLOps$(RESET)\n"
	@printf "  make mlflow-ui    Abre o dashboard MLflow\n"
	@printf "  make evaluate     Analisa qualidade dos runs recentes\n"
	@printf "  make drift-check  Verifica drift nos scores\n"
	@printf "  make promote      Promove modelo (MODEL= VERSION= STAGE=)\n"
	@printf "\n$(BLUE)Exemplos$(RESET)\n"
	@printf "  make promote MODEL=edital_matching VERSION=3 STAGE=Production\n"
	@printf "  make drift-check HISTORY=/data/drift_history\n\n"

# ── Docker ────────────────────────────────────────────────────────────────────

up:
	docker compose up -d
	@printf "\n$(GREEN)✓ Serviços no ar:$(RESET)\n"
	@printf "  API      → http://localhost:8000/docs\n"
	@printf "  Frontend → http://localhost:3000\n"
	@printf "  MLflow   → http://localhost:5000\n\n"

down:
	docker compose down

logs:
	docker compose logs -f api

build:
	docker compose build --no-cache api frontend

rebuild: down build up

shell-api:
	docker compose exec api bash

shell-db:
	docker compose exec db psql -U postgres -d edital_matcher

mlflow-ui:
	@printf "$(GREEN)MLflow disponível em: http://localhost:5000$(RESET)\n"
	@open http://localhost:5000 2>/dev/null || start http://localhost:5000 2>/dev/null || true

# ── Qualidade de Código ───────────────────────────────────────────────────────

lint:
	ruff check backend/app tests mlops/scripts

lint-fix:
	ruff check --fix backend/app tests mlops/scripts

format:
	black backend/app tests mlops/scripts
	ruff check --fix backend/app tests mlops/scripts

# ── Testes ────────────────────────────────────────────────────────────────────
# PYTHONPATH=backend permite que os testes importem de 'app.*'

test:
	PYTHONPATH=backend pytest tests/unit tests/test_password_policy.py tests/test_requirements.py \
	  -v --tb=short

test-cov:
	PYTHONPATH=backend pytest tests/unit tests/test_password_policy.py tests/test_requirements.py \
	  --cov=backend/app \
	  --cov-report=html \
	  --cov-report=term-missing \
	  -v
	@printf "\n$(GREEN)✓ Relatório HTML: htmlcov/index.html$(RESET)\n"

test-all:
	PYTHONPATH=backend pytest tests/ -v --tb=short

# ── MLOps Scripts ─────────────────────────────────────────────────────────────

EXPERIMENT    ?= edital_matching
HISTORY       ?= /data/drift_history
MODEL         ?= edital_matching
VERSION       ?= 1
STAGE         ?= Staging
MLFLOW_URI    ?= http://localhost:5000

evaluate:
	PYTHONPATH=backend MLFLOW_TRACKING_URI=$(MLFLOW_URI) \
	  python mlops/scripts/evaluate.py --experiment $(EXPERIMENT)

drift-check:
	PYTHONPATH=backend \
	  python mlops/scripts/drift_check.py --history $(HISTORY)

drift-report:
	PYTHONPATH=backend \
	  python mlops/scripts/drift_check.py --history $(HISTORY) --report evidently

promote:
	@test -n "$(MODEL)"   || (echo "Erro: MODEL não definido. Ex: make promote MODEL=edital_matching VERSION=1 STAGE=Production" && exit 1)
	@test -n "$(VERSION)" || (echo "Erro: VERSION não definido" && exit 1)
	PYTHONPATH=backend MLFLOW_TRACKING_URI=$(MLFLOW_URI) \
	  python mlops/scripts/promote_model.py \
	    --model $(MODEL) --version $(VERSION) --stage $(STAGE)

promote-best:
	PYTHONPATH=backend MLFLOW_TRACKING_URI=$(MLFLOW_URI) \
	  python mlops/scripts/promote_model.py --auto-best --model $(MODEL) --stage $(STAGE)

list-models:
	PYTHONPATH=backend MLFLOW_TRACKING_URI=$(MLFLOW_URI) \
	  python mlops/scripts/promote_model.py --list --model $(MODEL)
