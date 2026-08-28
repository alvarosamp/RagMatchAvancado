# Plano de arquitetura: CRM rápido e retomada das aplicações de IA

**Data:** 27/08/2026  
**Objetivo:** reduzir o tempo percebido para abrir e operar os editais no CRM, mantendo processamento de IA isolado da experiência transacional.

## Diagnóstico do estado atual

O projeto já contém uma boa base: FastAPI, PostgreSQL 16 + pgvector, Redis, MinIO, Dramatiq, worker e scheduler. A produção atual sobe a API com dois workers Uvicorn e um único processo Dramatiq.

O atraso ao abrir **Editais** tem uma causa de aplicação antes de ser um problema de balanceamento:

- A tela `bid-buddy/src/pages/Notices.tsx` busca todos os editais ativos de uma vez, sem `limit` nem paginação.
- A consulta de `notices` no backend carrega em cada linha órgão, portal, **todos os documentos**, **todos os itens/produtos** e **todas as sessões**.
- Esses relacionamentos são serializados integralmente em JSON, embora o quadro inicial use principalmente os contadores e poucos campos do edital.
- O navegador ainda faz filtros, ordenação e agrupamento sobre todo esse conjunto. Conforme a base cresce, a transferência, a consulta SQL e a renderização crescem juntas.

Portanto, adicionar um load balancer agora pode distribuir requisições, mas não reduz o trabalho excessivo de cada requisição. A sequência correta é: medir, reduzir o payload e o SQL, separar IA, e só então escalar horizontalmente quando a métrica justificar.

## Arquitetura-alvo

```text
Usuário
  │
  ▼
CDN/WAF + TLS
  │  arquivos estáticos do CRM em cache
  ▼
Load balancer / reverse proxy
  ├──────────────────► API CRM (réplicas stateless) ───► PgBouncer ───► PostgreSQL primário + pgvector
  │                         │                                  │
  │                         │                                  └── réplica de leitura (fase posterior)
  │                         ▼
  │                       Redis: cache, filas e rate limit
  │                         │
  │                         ▼
  │                 Workers de negócio (CPU/I/O)
  │                         │
  │                         ├── MinIO/S3: PDFs, anexos, exportações
  │                         └── fila de IA
  │                                │
  └────────────────────────────► Workers de IA dedicados ───► servidor(es) de modelo/embeddings
                                      │
                                      └── MLflow: métricas, versões e qualidade
```

Princípios:

1. **API não executa IA nem parsing pesado.** Ela valida, persiste o pedido e responde com `202 Accepted` + `job_id`.
2. **Lista e detalhe são contratos distintos.** A lista traz um resumo pequeno; o detalhe busca documentos, itens e sessões apenas ao abrir um edital.
3. **Workers de IA são uma piscina separada.** Uma fila lenta não consome processos que atendem login, CRM e downloads.
4. **Banco é a fonte de verdade; Redis é descartável.** Cache tem TTL, chave por tenant e invalidação ao alterar edital.
5. **Escala só é feita sobre componentes stateless.** API e workers escalam horizontalmente; PostgreSQL/MinIO recebem backup, monitoramento e plano de recuperação antes disso.

## Plano de execução priorizado

### Fase 0 — linha de base e observabilidade (1–2 dias)

- Instrumentar a API com OpenTelemetry e métricas Prometheus: latência p50/p95/p99 por rota, payload de resposta, tempo SQL, pool de conexões, erros e profundidade das filas.
- Criar um dashboard com: `GET /crm/query/notices`, taxa de requests, tempo de renderização no navegador, CPU/RAM da API, PostgreSQL, Redis e workers.
- Habilitar `pg_stat_statements` no PostgreSQL e coletar `EXPLAIN (ANALYZE, BUFFERS)` da consulta de editais com uma base representativa.
- Definir SLO inicial: lista de editais p95 menor que 800 ms no servidor e LCP menor que 2,5 s em conexão comum. Estabelecer também tempo de fila e tempo de processamento de IA por tipo de job.

**Critério de saída:** o time consegue apontar, em cada lentidão, quanto tempo está em navegador, proxy, API, banco, fila e modelo.

### Fase 1 — correção direta do CRM (2–5 dias)

1. Criar `GET /crm/notices` (ou evoluir a query compatível existente) com paginação por cursor, filtro e ordenação no servidor. Começar com 50 editais por página; a resposta inclui `items`, `next_cursor` e `total` opcional.
2. Criar um DTO de cartão/lista que retorne somente campos mostrados no pipeline, órgão/portal resumidos e agregados (`pending_documents_count`, `products_count`, próxima sessão). Não retornar `notice_products(*)` e documentos completos na lista.
3. Criar `GET /crm/notices/{id}` com os relacionamentos do detalhe e carregar abas sob demanda: documentos, itens, sessões, matches, histórico e resultados.
4. Substituir `joinedload` de várias coleções simultâneas por consultas específicas ou `selectinload` no detalhe. O join múltiplo de coleções pode explodir o número de linhas intermediárias.
5. Levar busca, filtros e ordenação para o banco. Manter no navegador apenas o estado da interface da página já carregada.
6. Usar React Query já presente no CRM para cache por página/detalhe, prefetch do edital ao passar o cursor e atualização otimista ao mover o card.
7. Virtualizar colunas/cartões do pipeline quando houver muitos itens visíveis e medir o bundle do CRM para lazy-load de telas pesadas.

Índices candidatos, a validar com `EXPLAIN` antes de migrar:

- `crm_notices (tenant_id, outcome, created_at DESC, id DESC)` para a lista padrão;
- `crm_notices (tenant_id, stage, auction_date, id)` para quadro e agenda;
- `crm_notice_documents (tenant_id, notice_id, status)` para os contadores de pendência;
- `crm_notice_sessions (tenant_id, notice_id, scheduled_at)` para próxima sessão;
- confirmar os índices em `notice_id` das tabelas filhas já existentes e acrescentar os compostos somente se o plano de execução os usar.

**Critério de saída:** abrir a lista não depende da quantidade total de itens e documentos da base; a resposta da primeira página permanece pequena e previsível.

### Fase 2 — cache, conexões e arquivos (3–5 dias)

- Cache Redis do resumo da lista por `tenant + filtros + cursor`, TTL de 30–120 segundos. Invalidar as chaves do tenant em criação, atualização, exclusão e mudança de etapa.
- Cachear contadores do dashboard e resultados de consultas caras; não cachear permissões sem incluir usuário/tenant na chave.
- Inserir PgBouncer entre API/workers e PostgreSQL, com pool dimensionado pelo máximo de conexões do banco, não pelo número de containers.
- Garantir que PDFs e anexos sejam entregues por URL pré-assinada do MinIO/S3; a API não deve transmitir o arquivo inteiro quando o navegador pode baixar diretamente do object storage.
- Configurar cache imutável para assets com hash do Vite (`Cache-Control: public, max-age=31536000, immutable`) e `no-cache` apenas para HTML de entrada. Hoje o CRM publicado é um bom candidato a cache mais agressivo de assets.

**Critério de saída:** p95 da lista permanece dentro do SLO sob carga moderada e downloads não saturam workers Uvicorn.

### Fase 3 — retomar IA sem piorar o CRM (1–2 semanas)

Reativar em etapas e sempre por job assíncrono:

1. **Embeddings e RAG:** primeiro, gerar embeddings no worker de IA e persistir no pgvector. Medir recall, custo e duração.
2. **Triagem/matching determinístico:** regras e busca vetorial geram score, evidências e recomendação inicial. Isto produz valor mesmo quando o LLM estiver indisponível.
3. **LLM como enriquecimento:** enviar apenas os casos ambíguos ou de maior valor para o modelo, com limite de concorrência, timeout, retry com backoff e resultado estruturado validado.
4. **Copiloto do edital:** chat RAG por edital com fontes/citações e isolamento por tenant, depois que os passos anteriores estiverem estáveis.

Separar as filas Dramatiq em pelo menos:

- `edital-processing`: OCR, extração e normalização;
- `matching-fast`: regras, vetores e agregações;
- `ai-inference`: LLM, concorrência baixa e timeout estrito;
- `exports`: XLSX/PDF/ZIP;
- `maintenance`: sincronizações PNCP e tarefas periódicas.

Cada job deve ser idempotente, gravar estado/progresso, ter `correlation_id`, limite de tentativas e uma fila de falhas para reprocessamento manual. A UI deve exibir status e último resultado salvo, jamais bloquear enquanto aguarda a IA.

Para modelo local, disponibilizar um host dedicado a Ollama/vLLM com GPU, separado dos nós de API e banco. Para provedor externo, usar uma camada `AI Gateway` interna que centralize chaves, rate limit, orçamento, fallback e auditoria. Em ambos os casos, iniciar com um worker de inferência por modelo/GPU e aumentar apenas após medir throughput e VRAM.

**Critério de saída:** ligar/desligar a IA não muda a latência da lista de editais; 95% dos jobs possuem estado final observável e reprocessável.

### Fase 4 — alta disponibilidade e load balancer (após as fases 1–3)

Implantar quando houver ao menos duas réplicas de API ou necessidade real de manutenção sem indisponibilidade:

- Um load balancer L7 gerenciado (ou Nginx/Traefik inicialmente) termina TLS, aplica rate limit e encaminha `/api` para ao menos duas réplicas de API stateless.
- Health checks devem usar endpoint `live` (processo vivo) e `ready` (PostgreSQL/Redis acessíveis), com remoção automática de réplicas não prontas.
- Cookies de autenticação devem manter `Secure`, `HttpOnly`, `SameSite=Lax`; não usar sessão presa a uma instância. JWT já favorece isso.
- Fazer rollout `rolling`/blue-green da API e do frontend; executar migrações como job único antes de aumentar as réplicas.
- Redis deve ter persistência e backup apropriado, mas não ser o único repositório de trabalho irrecuperável. PostgreSQL deve ter backup diário, PITR e teste periódico de restore. MinIO/S3 precisa de versionamento/replicação conforme criticidade.
- Só introduzir réplica de leitura do PostgreSQL após identificar relatórios/listagens que realmente competem com escrita. O detalhe transacional continua no primário para consistência.

**Critério de saída:** perda de uma réplica de API/worker não interrompe o CRM e a plataforma suporta deploy sem downtime percebido.

## Dimensionamento inicial sugerido

Para uma operação pequena/média, iniciar de forma simples e ajustável:

| Componente | Início recomendado | Regra de escala |
|---|---:|---|
| API FastAPI | 2 réplicas, 2–4 workers cada | aumentar quando CPU sustentada >70% ou p95 exceder SLO |
| Worker de negócio | 1–2 réplicas | aumentar por backlog e tempo de espera da fila |
| Worker de IA | 1 por GPU/modelo | limitar pela VRAM, tokens/s e tamanho de fila |
| PostgreSQL | 1 primário com backup/PITR | otimizar índice/consulta antes de aumentar máquina; réplica só para leitura pesada |
| Redis | 1 instância com persistência | HA quando se tornar ponto único crítico |
| MinIO/S3 | bucket privado + URLs assinadas | crescer por volume/IO; replicar por requisito de RPO/RTO |

Os números precisam ser recalibrados após a Fase 0; não é seguro fixá-los sem usuários simultâneos, volume de editais e tamanho médio dos anexos.

## Segurança e governança essenciais

- Tenant obrigatório em toda query, chave de cache, objeto do bucket e job.
- PDFs/anexos privados; URL pré-assinada curta e auditoria de download.
- Segredos em cofre/variáveis do orquestrador, nunca em imagem, repositório ou banco de dados do CRM.
- Logs estruturados sem conteúdo integral de edital, credenciais ou prompts sensíveis.
- Rate limit por usuário/tenant, limites de upload, antivírus/validação de tipo de arquivo e retenção definida para documentos.
- Avaliação de IA: conjunto de referência, métricas de qualidade, aprovação humana para recomendações críticas e trilha de evidências/citações.

## Decisões práticas para agora

1. **Não colocar load balancer como primeira entrega.** A prioridade técnica é a rota de lista paginada/resumida e o detalhe sob demanda.
2. **Não executar OCR, embeddings ou LLM na requisição HTTP.** Todos retornam `job_id`.
3. **Manter Postgres + pgvector inicialmente.** Não há evidência de que um banco vetorial separado seja necessário antes de medir escala e latência de busca.
4. **Manter o CRM e API no mesmo domínio atrás do proxy.** Reduz CORS, problemas de sessão e latência de conexão.
5. **Liberar IA por feature flag por tenant/tipo de job.** O compose de produção já prevê `AI_FEATURES_ENABLED`, `DATASHEET_EXTRACTOR_USE_LLM` e `CRM_MATCH_USE_LLM`; a reativação deve começar desligada e controlada.

## Riscos e como evitá-los

| Risco | Mitigação |
|---|---|
| Escalar API sem reduzir payload | executar Fase 1 antes de comprar mais infraestrutura |
| Um job de IA ocupa todos os workers | filas e réplicas exclusivas para IA |
| Explosão de conexões PostgreSQL | PgBouncer, limites por processo e observabilidade |
| Cache mostra estado antigo | TTL curto, chave por tenant e invalidação nas mutações |
| LLM produz conclusão sem evidência | RAG com fontes, schema de saída e revisão humana |
| Nova migration derruba o serviço | migration compatível/expand-contract, backup e rollout gradual |

## Ordem sugerida das próximas entregas

1. Medir e registrar a linha de base de `/crm/editais`.
2. Implementar endpoint/lista resumida paginada e alterar `Notices.tsx`.
3. Implementar detalhe e abas carregadas sob demanda.
4. Adicionar índices comprovados pelo plano de execução e cache Redis.
5. Separar workers e filas de IA, então reativar embeddings/matching com feature flag.
6. Implantar duas réplicas de API atrás de load balancer, PgBouncer, backup/PITR e alertas.

