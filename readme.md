# Edital Matcher API

Sistema inteligente de matching entre produtos de catálogo e requisitos técnicos de editais de licitação pública.

---

## O que o sistema faz

1. Recebe um PDF de edital de licitação
2. Extrai o texto com OCR (Docling)
3. Divide em chunks e gera embeddings vetoriais (Ollama + pgvector)
4. Compara cada produto do catálogo contra os requisitos do edital
5. Usa regras, heurísticas e LLM local (Ollama) para gerar um score de matching
6. Exporta os resultados em XLSX, PDF ou CSV

---

## Arquitetura

```
Usuário
  │
  ▼
FastAPI (API Gateway)
  │
  ├── PostgreSQL + pgvector  (banco transacional + busca vetorial)
  ├── Ollama                 (embeddings + LLM local)
  │
  ├── Pipeline
  │     Docling (OCR/Parser) → Chunker → Embedder → pgvector
  │
  └── Motor de Matching
        Busca vetorial (RAG) + Heurísticas + LLM → Score + Relatório
```

---

## Estrutura de pastas

```
edital-matcher/
├── docker-compose.yaml
├── .env                        ← criado a partir do .env.example
│
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    └── app/
        ├── main.py
        ├── core/
        │   └── config.py       ← settings do banco (lê .env)
        ├── db/
        │   ├── models.py       ← tabelas: Product, Edital, Chunk, Requirement, MatchingResult
        │   ├── session.py      ← engine e get_db
        │   └── init_db.py      ← startup: pgvector + tabelas + catálogo
        ├── logs/
        │   └── config.py       ← logger
        ├── pipeline/
        │   ├── docling_parser.py  ← OCR e extração estruturada do PDF
        │   ├── chunker.py         ← sliding window com overlap
        │   └── embedder.py        ← nomic-embed-text via Ollama
        ├── vector/
        │   └── pgvector_store.py  ← salvar e buscar chunks por similaridade
        ├── services/
        │   ├── catalog_loader.py      ← carrega all_devices.json no banco
        │   ├── requirements_checker.py ← regras por atributo
        │   ├── matching_engine.py      ← RAG + heurísticas + LLM
        │   └── export_service.py      ← geração de XLSX, PDF e CSV
        └── routers/
            ├── health.py    ← GET /health
            ├── switches.py  ← GET /switches
            ├── editais.py   ← upload, requisitos, matching
            └── export.py    ← download XLSX, PDF, CSV
```

---

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) e Docker Compose
- Pelo menos **8 GB de RAM** disponível para o Ollama rodar os modelos
- Os modelos `nomic-embed-text` e `llama3` são baixados automaticamente na primeira execução

---

## Como rodar

### 1. Clonar e configurar

```bash
git clone <seu-repositorio>
cd edital-matcher

cp .env.example .env
# edite o .env se quiser mudar senhas ou porta
```

### 2. Subir tudo

```bash
docker compose up --build
```

Na **primeira execução**, o serviço `ollama-setup` vai baixar os modelos automaticamente. Isso pode levar alguns minutos dependendo da internet. Depois fica salvo no volume `ollama_data`.

### 3. Acessar

| Serviço | URL |
|---|---|
| API (Swagger) | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |
| Ollama | http://localhost:11434 |

---

## Fluxo de uso

### Passo 1 — Fazer upload do edital

```
POST /editais/upload
Content-Type: multipart/form-data

file: <arquivo.pdf>
tenant_id: empresa_x  (opcional)
```

Retorna o `edital_id` gerado.

### Passo 2 — Cadastrar os requisitos

```
POST /editais/{edital_id}/requirements
Content-Type: application/json

[
  {
    "attribute": "Portas RJ45",
    "raw_value": "mínimo 16 portas RJ-45",
    "parsed_value": "16",
    "unit": "portas"
  },
  {
    "attribute": "PoE",
    "raw_value": "deve possuir PoE",
    "parsed_value": "True"
  }
]
```

### Passo 3 — Rodar o matching

```
POST /editais/{edital_id}/match
```

Avalia todos os produtos do catálogo contra os requisitos e retorna ranking com scores.

### Passo 4 — Exportar os resultados

```
GET /editais/{edital_id}/export/xlsx   → planilha Excel
GET /editais/{edital_id}/export/pdf    → relatório PDF
GET /editais/{edital_id}/export/csv    → CSV (separado por ;)
```

---

## Endpoints disponíveis

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Status da API |
| GET | `/switches` | Lista produtos do catálogo |
| GET | `/verify-switches` | Verifica requisitos básicos dos switches |
| POST | `/editais/upload` | Faz upload e processa PDF do edital |
| POST | `/editais/{id}/requirements` | Cadastra requisitos do edital |
| POST | `/editais/{id}/match` | Executa o matching |
| GET | `/editais/` | Lista todos os editais |
| GET | `/editais/{id}/results` | Resultados de matching salvos |
| GET | `/editais/{id}/export/xlsx` | Download da planilha |
| GET | `/editais/{id}/export/pdf` | Download do relatório PDF |
| GET | `/editais/{id}/export/csv` | Download do CSV |

---

## Catálogo de produtos

O catálogo fica em `data/Produtos/all_devices.json`. O sistema carrega automaticamente no startup. Para adicionar novos produtos, basta adicionar entradas ao JSON e reiniciar a API — produtos duplicados são ignorados.

Formato esperado:

```json
{
  "MODELO-XYZ": {
    "Tipo de Gerenciamento": "Managed (CLI/Web)",
    "Managed Web": true,
    "Portas RJ45": "24x 1G",
    "PoE": true,
    "Portas PoE": "24",
    "Budget PoE (W)": "384",
    "Power Requirement / Tensão de Entrada": "100–240 VAC, 50/60 Hz"
  }
}
```

---

## Comandos úteis

```bash
# Subir pela primeira vez
docker compose up --build

# Subir sem rebuild (código Python tem hot reload)
docker compose up

# Ver logs da API
docker compose logs -f api

# Ver logs do Ollama
docker compose logs -f ollama

# Parar tudo
docker compose down

# Parar e apagar banco (cuidado!)
docker compose down -v

# Rodar testes
docker compose exec api pytest tests/ -v
```

---

## Variáveis de ambiente

| Variável | Descrição | Padrão |
|---|---|---|
| `POSTGRES_DB` | Nome do banco | `edital_matcher` |
| `POSTGRES_USER` | Usuário do banco | `postgres` |
| `POSTGRES_PASSWORD` | Senha do banco | — |
| `POSTGRES_HOST` | Host do banco | `db` |
| `POSTGRES_PORT` | Porta do banco | `5432` |
| `APP_PORT` | Porta da API no host | `8000` |
| `OLLAMA_HOST` | URL do Ollama | `http://ollama:11434` |

---

## Modelos Ollama utilizados

| Modelo | Uso | Tamanho aprox. |
|---|---|---|
| `nomic-embed-text` | Geração de embeddings (768d) | ~270 MB |
| `llama3` | Motor de matching e raciocínio | ~4.7 GB |

Para trocar o modelo LLM, edite a variável `LLM_MODEL` em `app/services/matching_engine.py`.

---

## Roadmap

- [x] Pipeline OCR → Chunk → Embed
- [x] Busca vetorial com pgvector
- [x] Motor de Matching (RAG + Heurísticas + LLM)
- [x] Exportação XLSX / PDF / CSV
- [ ] Auth / Multi-tenant
- [ ] Orquestrador de jobs assíncrono (Celery/ARQ)
- [ ] Frontend web