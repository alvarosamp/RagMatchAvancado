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
| **API** | FastAPI | Gateway REST, routers, auth e jobs |
| **Banco** | PostgreSQL 16 + pgvector | Dados relacionais + busca vetorial |
| **OCR/Parser** | Docling | Extração de texto estruturado de PDFs |
| **Embeddings** | Ollama `nomic-embed-text` (768d) | Vetorização de chunks |
| **LLM Matching** | Ollama `llama3.2:1b` | Avaliação semântica dos requisitos |
| **Autenticação** | JWT + bcrypt | Multi-tenant e RBAC |
| **Experiment Tracking** | MLflow | Rastreamento de runs, métricas e artefatos |
| **Drift Monitoring** | Evidently | Detecção de mudanças nos scores ao longo do tempo |
| **Frontend** | React 18 + Vite 5 + Tailwind 3 | SPA web |
| **Exportação** | openpyxl + reportlab | XLSX, PDF, CSV |

> O modelo de LLM usado no matching é configurável via env var `OLLAMA_MODEL` (default `llama3.2:1b`, o mesmo que o `docker-compose.yaml` faz pull no serviço `ollama-setup`).

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
[3] LLM llama3.2:1b      → raciocínio semântico + justificativa JSON (peso: 70%)
        │
        ▼
Score Final
  >= 0.75  →  ATENDE
  0.45–0.75 →  VERIFICAR
  < 0.45   →  NÃO ATENDE
```

---

## Integração CRM (Bid Buddy)

O projeto pode publicar o CRM do diretório `bid-buddy/` dentro do site principal da Tor na rota `/crm/`.

### Como funciona

1. O repositório `bid-buddy/` continua separado.
2. O script `scripts/sync-bid-buddy.mjs` gera um build do CRM com base `/crm/`.
3. Os arquivos compilados são copiados para `frontend/public/crm/`.
4. O frontend principal incorpora esse build na rota `/crm` e o Nginx faz fallback para `/crm/index.html`.

### Fluxo recomendado de atualização

```bash
node ./scripts/sync-bid-buddy.mjs --pull
cd frontend
npm run build:all
```

### Build em container

O `docker-compose.yaml` e o `frontend/Dockerfile` agora constroem o site principal junto com o CRM embarcado, para que a publicação saia pronta no mesmo deploy.

### Operação e desempenho do CRM

- `GET /crm/notices` entrega uma lista paginada e leve para o pipeline, com contadores de documentos e produtos; use `cursor` para carregar a próxima página.
- O cache dessa lista é isolado por tenant no Redis e é invalidado nas operações de criação, edição e remoção feitas pela API.
- As inferências de matching do CRM rodam no worker `worker-ai`, separado do processamento regular de editais. O uso de LLM permanece opt-in por `CRM_MATCH_USE_LLM=1`.
- Datas vindas de clientes com fuso horário são normalizadas para o horário de Brasília antes de serem gravadas no CRM, evitando deslocamento de três horas.

### Health checks

- `GET /health` e `GET /health/live` verificam se a API está em execução.
- `GET /health/ready` também confirma a conectividade com PostgreSQL e, quando configurado, Redis. Use este endpoint em sondas de readiness do ambiente.

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
    llm_model="llama3.2:1b",
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
- **GET** `/health/live` — liveness probe da API
- **GET** `/health/ready` — readiness probe (PostgreSQL e Redis)

### CRM
- **GET** `/crm/notices` — pipeline de avisos paginado e resumido
- **POST** `/crm/matches/ground-truth/run` — enfileira itens rotulados para calibração do matching (admin/editor)
- **POST** `/crm/notice-products/{id}/match-review` — registra o veredito técnico humano do produto vinculado
- **GET** `/crm/matches/evaluation-dataset` — exporta o dataset versionado e métricas de avaliação do matching

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

Para produção, copie `.env.prod.example` para `.env.prod`, defina os segredos e
suba a composição de produção:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yaml up -d
```

A composição usa PgBouncer para as conexões da API e separa o worker de IA do
worker regular. Ajuste `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`,
`AI_WORKER_PROCESSES` e `AI_WORKER_THREADS` conforme a capacidade do servidor.
Em produção, use uma tag imutável do CI em `IMAGE_TAG` (por exemplo,
`sha-<commit>`), mantenha a VPS atrás do Traefik e consulte
[docs/production-vps.md](docs/production-vps.md) antes do primeiro deploy.

Na primeira vez, o serviço `ollama-setup` baixa os modelos automaticamente (~5 min).

| Serviço | URL |
|---------|-----|
| API REST | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Frontend | http://localhost:3000 |
| MLflow UI | http://localhost:5000 |
| Ollama | http://localhost:11434 |

---

## CI/CD com GitHub Actions

O repositorio agora possui um pipeline de CI/CD em `.github/workflows/ci.yml` com este fluxo:

1. roda lint, testes e build do frontend;
2. valida as imagens Docker de `backend`, `frontend` e `mlflow`;
3. no push da branch `main`, publica as imagens no Docker Hub;
4. depois conecta no VPS por SSH e executa o deploy automatico com `scripts/deploy-production.sh`.

### Secrets necessarios no GitHub

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`
- `VPS_HOST`
- `VPS_PORT` (opcional, padrao `22`)
- `VPS_USER`
- `VPS_SSH_KEY`
- `VPS_APP_DIR`

### Preparacao do servidor

1. clone este repositorio no VPS;
2. crie um `.env.prod` com os valores reais de producao;
3. deixe o Docker e o Docker Compose instalados;
4. garanta que o usuario do deploy tenha permissao para rodar Docker.

Com isso, cada push na `main` passa a publicar e atualizar o ambiente automaticamente.

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

## Avaliação contínua do matching

O CRM transforma vínculos de catálogo confirmados por pessoas em um dataset de
avaliação versionado. Depois de revisar o produto vinculado como `ATENDE`,
`VERIFICAR` ou `NAO_ATENDE`, exporte os registros em
`GET /crm/matches/evaluation-dataset` e acompanhe Recall@K, MRR, NDCG,
precisão, recall, macro-F1 e taxa de falso aceite.

O matcher mantém o resultado em `VERIFICAR` quando a inferência do LLM não está
disponível; ele não cria um score artificial. O contexto RAG também é calculado
uma única vez por requisito em cada execução, reduzindo chamadas repetidas.
Consulte [docs/crm-match-evaluation-dataset.md](docs/crm-match-evaluation-dataset.md)
para o formato do dataset, critérios de revisão e execução offline.

---

## Variáveis de Ambiente

```env
DATABASE_URL=postgresql://postgres:postgres@db:5432/edital_matcher
OLLAMA_HOST=http://ollama:11434
MLFLOW_TRACKING_URI=http://mlflow:5000
```

### Armazenamento de PDFs e exports (MinIO/S3)

Em produção, o Compose sobe o MinIO automaticamente e os PDFs de editais e
exports XLSX/PDF/CSV passam a ser guardados no volume persistente `minio_data`.
Defina credenciais fortes no `.env` do servidor antes de subir a stack:

```env
MINIO_ROOT_USER=troque-por-um-usuario
MINIO_ROOT_PASSWORD=troque-por-uma-senha-longa
S3_BUCKET=edital-matcher
```

O MinIO fica acessível apenas para os containers. Para usar AWS S3, Cloudflare
R2 ou outro serviço compatível no futuro, basta trocar `S3_ENDPOINT_URL`,
`S3_ACCESS_KEY` e `S3_SECRET_KEY` sem alterar o código.

---

## Roadmap

```
✅  Pipeline OCR → Chunk → Embed (Docling + nomic-embed-text)
✅  Motor de Matching RAG + heurísticas + LLM (llama3.2:1b)
✅  Catálogo de produtos (data/Produtos/all_devices.json)
✅  Exportação XLSX / PDF / CSV
✅  Autenticação JWT com multi-tenant
✅  Jobs assíncronos com Redis + worker dedicado e polling
✅  Recuperação automática de jobs interrompidos e retry com backoff
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

## Migração de servidor e backups

O projeto inclui scripts para gerar e validar um pacote de migração completo:
dump PostgreSQL, arquivos, objetos MinIO, XLSX de auditoria e manifesto com
hashes. Consulte [docs/migracao_servidor.md](docs/migracao_servidor.md) antes
de trocar de provedor ou desligar um servidor.

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
