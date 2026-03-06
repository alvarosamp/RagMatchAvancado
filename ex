# ── Banco de dados ────────────────────────────────
POSTGRES_DB=edital_matcher
POSTGRES_USER=edital
POSTGRES_PASSWORD=edital123
POSTGRES_HOST=db
POSTGRES_PORT=5432

# ── API ───────────────────────────────────────────
APP_PORT=8000

# ── Ollama ────────────────────────────────────────
# Dentro do Docker é setado automaticamente pelo docker-compose
# Para rodar local sem Docker, deixe como está:
OLLAMA_HOST=http://localhost:11434
