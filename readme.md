# 📄 Edital Matcher — SaaS de Matching para Licitações

Sistema inteligente para matching automático entre produtos do catálogo e requisitos de editais de licitação, com pipeline OCR → Embeddings → RAG → LLM, autenticação multi-tenant, jobs assíncronos e camada de MLOps.

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

O Edital Matcher analisa PDFs de editais de licitação, extrai os requisitos técnicos e verifica automaticamente quais produtos do catálogo atendem ao que foi pedido. O resultado é um ranking com score, justificativas geradas por LLM e exportação em XLSX, PDF e CSV.

**Problema resolvido:** analistas gastam horas lendo editais e comparando com catálogos manualmente. O sistema automatiza isso em minutos com rastreabilidade total via MLflow.

---

## Stack Tecnológica

| Camada | Tecnologia | Função |
|--------|-----------|--------|
| **API** | FastAPI 0.5.0 | Gateway REST, routers, auth e jobs |
| **Banco** | PostgreSQL 16 + pgvector | Dados relacionais + busca vetorial |
| **OCR/Parser** | Docling | Extração de texto estruturado de PDFs |
| **Embeddings** | Ollama `nomic-embed-text` (768d) | Vetorização de chunks |
| **LLM Matching** | Ollama `phi3` | Avaliação semântica dos requisitos |
| **Autenticação** | JWT + bcrypt | Multi-tenant e RBAC |
| **Experiment Tracking** | MLflow | Rastreamento de runs, métricas e artefatos |
| **Drift Monitoring** | Evidently | Detecção de mudanças nos scores ao longo do tempo |
| **Frontend** | React 18 + Vite 5 + Tailwind 3 | SPA web |
| **Exportação** | openpyxl + reportlab | XLSX, PDF, CSV |

> Observação: o fluxo de matching usa `phi3` por padrão no código. O `docker-compose.yaml` ainda faz pull de `llama3` no serviço de setup do Ollama.

---

## Arquitetura

```
Usuário / Cliente
    │
    ▼
Frontend React (3000)
    │  Login • Upload • Dashboard • Jobs • Analytics
    ▼
FastAPI (8000)
    │  auth • editais • jobs • exports • analytics • switches
    ├── PostgreSQL + pgvector
    ├── Ollama (embeddings + LLM)
    └── MLflow + Evidently
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
[3] LLM phi3             → raciocínio semântico + justificativa JSON (peso: 70%)
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
RagMatchAvancado/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py
│   │   ├── auth/
│   │   ├── core/
│   │   ├── db/
│   │   ├── jobs/
│   │   ├── logs/
│   │   ├── mlops/
│   │   ├── pipeline/
│   │   ├── routers/
│   │   ├── services/
│   │   ├── vector/
│   │   └── workers/
│   └── scripts/
├── frontend/
│   ├── package.json
│   └── src/
│       ├── api/
│       ├── components/
│       ├── contexts/
│       └── pages/
├── data/
│   └── Produtos/all_devices.json
├── Pncp/
│   ├── AnaliseAtaGPT/pipelinegpt.py
│   └── AnaliseAtaLLM/
├── apiPncp/
├── tests/
│   └── test_requirements.py
└── docker-compose.yaml
```

O diretório Pncp contém utilitários e experimentos paralelos de análise de atas. O fluxo principal do produto está em backend/ e frontend/.

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
    llm_model="phi3",
)
```

Métricas logadas: `score_medio`, `score_maximo`, `score_minimo`, `pct_atende`, `pct_verificar`, `pct_nao_atende`, `tempo_execucao_segundos`

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

### Autenticação e Multi-tenant
- **POST** `/auth/register` — cria tenant + usuário admin e retorna JWT
- **POST** `/auth/login` — autenticação com JWT
- **GET** `/auth/me` — dados do usuário atual
- **POST** `/auth/users` — admin cria usuário no mesmo tenant
- **GET** `/auth/users` — lista usuários do tenant autenticado

### Editais e Matching
- **POST** `/editais/upload` — PDF → OCR → chunks → embeddings, retorna `job_id` com HTTP 202
- **GET** `/editais` — lista editais do tenant
- **POST** `/editais/{id}/requirements` — cadastra requisitos técnicos
- **POST** `/editais/{id}/match` — executa matching e retorna `job_id` com HTTP 202
- **GET** `/editais/{id}/results` — consulta resultados do edital

### Jobs Assíncronos
- **GET** `/jobs/{job_id}` — status, progresso, resultado e erro do job
- **GET** `/jobs` — lista jobs do tenant com paginação

### Exportação
- **GET** `/editais/{id}/export/xlsx` — planilha Excel com resumo e detalhes
- **GET** `/editais/{id}/export/pdf` — relatório PDF
- **GET** `/editais/{id}/export/csv` — CSV UTF-8 BOM

### Analytics e Produtos
- **GET** `/analytics/overview` — KPIs gerais
- **GET** `/analytics/produtos` — ranking de produtos
- **GET** `/analytics/requisitos` — requisitos com maior taxa de falha
- **GET** `/analytics/evolucao` — evolução de score por edital
- **GET** `/analytics/distribuicao` — distribuição de scores
- **GET** `/switches` — lista produtos de switch
- **GET** `/verify-switches` — verifica switches contra requisitos
- **GET** `/matching-results` — resultados brutos de matching

### Saúde
- **GET** `/health` — health check

Swagger: **http://localhost:8000/docs**

---

## Como Rodar

**Pré-requisitos:** Docker + 8GB RAM + 15GB de disco livre

```bash
# 1. Clone e configure
git clone <repo>
cd RagMatchAvancado

# 2. Configure variáveis de ambiente
# O docker-compose já traz valores padrão, mas você pode criar backend/.env

# 3. Suba os serviços
docker compose up --build
```

Na primeira vez, o serviço `ollama-setup` baixa os modelos automaticamente (~5 min).

| Serviço | URL |
|---------|-----|
| API REST | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Frontend | http://localhost:3000 |
| MLflow UI | http://localhost:5000 |
| Ollama | http://localhost:11434 |

---

## Fluxo de Uso

```
1. POST /auth/register ou /auth/login
    → cria o tenant inicial ou autentica o usuário com JWT

2. POST /editais/upload
    → envia o PDF do edital
    → retorna um `job_id` para acompanhamento assíncrono

3. POST /editais/{id}/requirements
    → cadastra os requisitos técnicos exigidos

4. POST /editais/{id}/match
    → executa matching completo
    → retorna `job_id` e registra métricas no MLflow quando disponível

5. GET /jobs/{job_id}
    → acompanha progresso até concluir

6. GET /editais/{id}/export/xlsx
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
✅  Motor de Matching RAG + heurísticas + LLM (phi3)
✅  Catálogo de produtos (data/Produtos/all_devices.json)
✅  Exportação XLSX / PDF / CSV
✅  Autenticação JWT com multi-tenant
✅  Jobs assíncronos com polling
✅  MLOps Layer (MLflow + Evidently)

⬜  Orquestração externa de jobs
    → executar workers dedicados fora do processo da API
    → desligar polling no frontend quando houver push events

⬜  Monitoramento (Prometheus + Grafana)
    → latência, error rate e score médio por tenant
    → alertas automáticos de drift

⬜  Hardening de produção
    → secrets manager, rate limit e row-level security
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

## Arquivos-Chave

- [backend/app/main.py](backend/app/main.py) — inicialização da API e registro dos routers
- [backend/app/services/match_engine.py](backend/app/services/match_engine.py) — matching 3 camadas com score ponderado
- [backend/app/auth/router.py](backend/app/auth/router.py) — registro, login e gestão de usuários
- [backend/app/jobs/router.py](backend/app/jobs/router.py) — polling de jobs assíncronos
- [backend/app/mlops/tracker.py](backend/app/mlops/tracker.py) — tracking no MLflow
- [backend/app/mlops/drift_monitor.py](backend/app/mlops/drift_monitor.py) — monitoramento de drift
- [frontend/src/main.jsx](frontend/src/main.jsx) — bootstrap do frontend
- [frontend/src/pages/Dashboard.jsx](frontend/src/pages/Dashboard.jsx) — dashboard principal
- [Pncp/AnaliseAtaGPT/pipelinegpt.py](Pncp/AnaliseAtaGPT/pipelinegpt.py) — pipeline GPT de análise de atas

*Projeto privado — todos os direitos reservados.*