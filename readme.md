# 📄 Edital Matcher — SaaS de Matching para Licitações

Sistema inteligente que faz o matching automático entre produtos do catálogo e requisitos de editais de licitação, com pipeline OCR → Embeddings → RAG → LLM e camada completa de MLOps.

---

## 📌 Índice

- [Visão Geral](#visão-geral)
- [Stack Tecnológica](#stack-tecnológica)
- [Arquitetura](#arquitetura)
- [Estrutura de Pastas](#estrutura-de-pastas)
- [MLOps Layer](#mlops-layer)
- [API Endpoints](#api-endpoints)
- [Como Rodar](#como-rodar)
- [Fluxo de Uso](#fluxo-de-uso)
- [Exportação](#exportação)
- [Roadmap](#roadmap)

---

## Visão Geral

O Edital Matcher analisa PDFs de editais de licitação e verifica automaticamente quais produtos do catálogo atendem aos requisitos técnicos exigidos. O resultado é um ranking scored com justificativas geradas por LLM e exportação em XLSX, PDF e CSV.

**Problema resolvido:** analistas gastam horas lendo editais e comparando com catálogos manualmente. O sistema automatiza isso em minutos com rastreabilidade total via MLflow.

---

## Stack Tecnológica

| Camada | Tecnologia | Função |
|--------|-----------|--------|
| **API** | FastAPI | Gateway REST, endpoints, roteamento |
| **Banco** | PostgreSQL + pgvector | Dados relacionais + busca vetorial |
| **OCR/Parser** | Docling | Extração de texto estruturado de PDFs |
| **Embeddings** | Ollama `nomic-embed-text` (768d) | Vetorização de chunks |
| **LLM Matching** | Ollama `llama3` | Avaliação semântica dos requisitos |
| **Experiment Tracking** | MLflow | Rastreamento de runs, métricas, comparação de modelos |
| **Orquestração** | Prefect *(next step)* | Pipeline assíncrono como DAG |
| **Drift Monitoring** | Evidently | Detecção de mudanças nos dados ao longo do tempo |
| **Exportação** | openpyxl + reportlab | XLSX, PDF, CSV |

---

## Arquitetura

```
Usuário / Cliente
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│                    FastAPI (porta 8000)                  │
│   /editais/upload  /editais/{id}/match  /export/*        │
└────────────────────────┬────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
   ┌─────────────┐ ┌──────────┐ ┌────────────────┐
   │  Pipeline   │ │ Matching │ │  MLOps Layer   │
   │  OCR→Chunk  │ │  Engine  │ │                │
   │  →Embed     │ │ RAG+LLM  │ │ tracker.py     │
   └──────┬──────┘ └────┬─────┘ │ evaluator.py   │
          │             │       │ drift_monitor  │
          ▼             ▼       └───────┬────────┘
   ┌─────────────────────────┐          │
   │  PostgreSQL + pgvector  │          ▼
   │  chunks / embeddings    │   ┌─────────────┐
   │  editais / resultados   │   │   MLflow    │
   └─────────────────────────┘   │ (porta 5000)│
                                 └─────────────┘
          │
          ▼
   ┌─────────────┐
   │   Ollama    │
   │ (porta 11434)│
   │ nomic-embed │
   │   llama3    │
   └─────────────┘
```

### Motor de Matching — 3 Camadas

```
Requisito do Edital
        │
        ▼
[1] RAG (pgvector)       → busca chunks relevantes do edital
        │
        ▼
[2] Heurísticas/Regras   → score rápido baseado em atributos (peso: 30%)
        │
        ▼
[3] LLM llama3           → raciocínio semântico + justificativa JSON (peso: 70%)
        │
        ▼
Score Final
  >= 0.75  →  ATENDE
  0.45–0.75 →  VERIFICAR
  < 0.45   →  NÃO ATENDE
```

---

## Estrutura de Pastas

```
edital-matcher/
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example
│   └── app/
│       ├── main.py                        # FastAPI app, registra todos os routers
│       ├── core/config.py                 # pydantic-settings, env vars
│       ├── db/
│       │   ├── models.py                  # Product, Edital, DocumentChunk, Requirement, MatchingResult
│       │   ├── session.py                 # engine + get_db
│       │   └── init_db.py                 # pgvector + tabelas + seed do catálogo
│       ├── logs/config.py                 # logger com FileHandler + StreamHandler
│       ├── pipeline/
│       │   ├── docling_parser.py          # OCR + estrutura markdown
│       │   ├── chunker.py                 # sliding window, overlap=150, max_chars=1000
│       │   └── embedder.py                # nomic-embed-text, batch=32, retry exponencial
│       ├── vector/pgvector_store.py       # save_chunks, search_similar (cosine <=>)
│       ├── services/
│       │   ├── catalog_loader.py          # carrega all_devices.json → banco
│       │   ├── requirements_checker.py    # regras por atributo
│       │   ├── matching_engine.py         # RAG + heurísticas + LLM
│       │   └── export_service.py          # XLSX, PDF, CSV
│       │
│       ├── mlops/                         # ← NOVO: camada MLOps
│       │   ├── __init__.py
│       │   ├── tracker.py                 # MLflow: runs, params, métricas, artefatos
│       │   ├── evaluator.py               # saúde do matching, distribuição, gaps
│       │   └── drift_monitor.py           # Evidently: drift em embeddings e scores
│       │
│       ├── workers/                       # ← NOVO: preparação para Job Orchestrator
│       │   ├── __init__.py
│       │   └── pipeline_worker.py         # Prefect flows/tasks (síncrono hoje, async em breve)
│       │
│       └── routers/
│           ├── health.py
│           ├── switches.py
│           ├── editais.py
│           └── export.py
│
├── mlflow/mlruns/                         # artefatos e metadata (persistido via volume)
├── monitoring/                            # planejado: Prometheus + Grafana
├── notebooks/                             # planejado: análise exploratória
├── data/
│   ├── all_devices.json                   # catálogo de produtos
│   └── uploads/
├── tests/test_requirements.py
└── docker-compose.yaml
```

---

## MLOps Layer

A camada MLOps foi desenhada para crescer junto com o projeto.

### tracker.py — Experiment Tracking

Registra cada execução do matching como um **run** no MLflow.

```python
from app.mlops import MatchingTracker

tracker = MatchingTracker()
tracker.log_matching_run(
    edital_id="42",
    resultados=resultados,
    llm_model="llama3",
)
```

M�tricas logadas: `score_medio`, `score_maximo`, `score_minimo`, `pct_atende`, `pct_verificar`, `pct_nao_atende`, `tempo_execucao_segundos`

**UI:** http://localhost:5000

---

### evaluator.py — Avaliação de Qualidade

Analisa a saúde do matching sem ground truth.

```python
from app.mlops import MatchingEvaluator

relatorio = MatchingEvaluator().gerar_relatorio_completo(
    edital_id="42",
    resultados=resultados,
)
# relatorio["saude_geral"]  → 0 a 100
# relatorio["distribuicao"]["alertas"]  → avisos automáticos
# relatorio["cobertura"]["requisitos_problematicos"]  → gaps no catálogo
```

Detecta: zona de incerteza alta, scores sem discriminação, requisitos sistematicamente mal avaliados.

---

### drift_monitor.py — Monitoramento de Drift

Detecta quando embeddings ou scores mudam ao longo do tempo.

```python
from app.mlops import DriftMonitor

monitor = DriftMonitor()
monitor.registrar_scores(edital_id="42", resultados=resultados)

analise = monitor.detectar_drift_scores(janela_runs=10)
# analise["drift_detectado"]  → True/False
# analise["delta"]            → variação na média

# Relatório HTML interativo (requer Evidently)
monitor.gerar_relatorio_evidently()
```

---

### pipeline_worker.py — Orquestração (Prefect-ready)

Pipeline estruturado como flows e tasks do Prefect. Hoje síncrono, assíncrono na próxima etapa.

```python
from app.workers import PipelineWorker

worker = PipelineWorker()
worker.executar_pipeline_completo(edital_id="42", pdf_path="/data/edital.pdf")
worker.executar_matching_com_tracking(edital_id="42", resultados_matching=resultados)
```

---

## API Endpoints

```
GET  /health
GET  /switches
GET  /verify-switches
GET  /matching-results

POST /editais/upload                 → PDF → OCR → chunks → embeddings
GET  /editais/                       → lista editais
POST /editais/{id}/requirements      → cadastra requisitos
POST /editais/{id}/match             → executa matching + MLOps tracking
GET  /editais/{id}/results           → consulta resultados

GET  /editais/{id}/export/xlsx       → planilha Excel (Resumo + Detalhes)
GET  /editais/{id}/export/pdf        → relatório PDF A4
GET  /editais/{id}/export/csv        → CSV UTF-8 BOM
```

Swagger: **http://localhost:8000/docs**

---

## Como Rodar

**Pré-requisitos:** Docker + 8GB RAM + 15GB disco

```bash
# 1. Clone e configure
git clone <repo>
cd edital-matcher
cp backend/.env.example backend/.env

# 2. Suba os serviços
docker compose up --build
```

Na primeira vez o `ollama-setup` baixa os modelos automaticamente (~5 min).

| Serviço | URL |
|---------|-----|
| API REST | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| MLflow UI | http://localhost:5000 |
| Ollama | http://localhost:11434 |

---

## Fluxo de Uso

```
1. POST /editais/upload
   → envia o PDF do edital
   → retorna: { edital_id, n_chunks }

2. POST /editais/{id}/requirements
   → cadastra os requisitos técnicos exigidos

3. POST /editais/{id}/match
   → executa matching completo
   → loga automaticamente no MLflow

4. GET /editais/{id}/export/xlsx
   → baixa planilha com ranking + justificativas
```

---

## Exportação

| Formato | Conteúdo |
|---------|---------|
| **XLSX** | Aba Resumo (ranking colorido) + Aba Detalhes (produto × requisito × justificativa LLM) |
| **PDF** | Cabeçalho, tabela de ranking, detalhes dos top 5 produtos |
| **CSV** | Separador `;`, UTF-8 BOM — `edital_id`, `modelo`, `score_geral`, `status_geral`, `requisito`, `score_item`, `justificativa_llm` |

---

## Variáveis de Ambiente

```env
DATABASE_URL=postgresql://postgres:postgres@db:5432/edital_matcher
OLLAMA_HOST=http://ollama:11434
MLFLOW_TRACKING_URI=http://mlflow:5000
```

---

## Roadmap

```
✅  Pipeline OCR → Chunk → Embed (Docling + nomic-embed-text)
✅  Motor de Matching RAG + Heurísticas + LLM (llama3)
✅  Catálogo de produtos (all_devices.json)
✅  Exportação XLSX / PDF / CSV
✅  MLOps Layer (MLflow + Evidently + Prefect-ready)

⬜  Auth / Multi-tenant
    → JWT + tabela tenants
    → tenant_id entra no tracker automaticamente

⬜  Job Orchestrator assíncrono
    → Prefect ativo (já comentado no docker-compose)
    → POST /upload retorna job_id imediatamente
    → GET /jobs/{id}/status mostra progresso

⬜  Frontend Web
    → Dashboard de licitações + upload + resultados

⬜  Monitoramento (Prometheus + Grafana)
    → Latência, error rate, score médio por tenant
    → Alertas de drift automáticos
```

---

## Catálogo — Chaves dos Produtos

```
Tipo de Gerenciamento | Unmanaged | Managed Web | Família (oficial) | Camada
Static Route / Rota Estática | Portas RJ45 | Uplinks | PoE | Portas PoE
Budget PoE (W) | Capacidade de Comutação | Taxa de Encaminhamento | Tabela MAC
VLANs | QinQ | IGMP / MLD | QoS | Recursos L3 | Segurança (802.1X/ACL/ARP)
Proteção Surto/ESD | Ventilação | Power Requirement / Tensão de Entrada | Aplicação típica
```

---

*Projeto privado — todos os direitos reservados.*