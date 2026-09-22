# Rollout seguro das capacidades de IA

## Objetivo

As capacidades de IA possuem dois niveis de controle:

1. `AI_FEATURES_ENABLED` e o disjuntor global do ambiente.
2. `tenants.ai_features` guarda overrides por empresa.

O matching do CRM e uma excecao intencional: `crm_matching` pode continuar
ativo com o disjuntor global desligado, mas opera apenas com ranking
lexical/deterministico. Embeddings e reranking continuam desligados.

## Capacidades

| Chave | Operacao protegida | Disjuntor global |
| --- | --- | --- |
| `document_processing` | upload, OCR e indexacao | sim |
| `matching` | matching do pipeline legado | sim |
| `edital_chat` | chat RAG por edital | sim |
| `datasheet_extraction` | extracao de datasheet | sim |
| `crm_matching` | ranking base do CRM | nao; fallback deterministico |
| `crm_manual_examples` | precedentes de vinculos manuais no matching CRM | nao; recuperacao deterministica |
| `crm_embeddings` | busca semantica no CRM | sim |
| `crm_llm_rerank` | reranking por LLM | sim |

## API administrativa

```http
GET /auth/tenant/ai-features
PATCH /auth/tenant/ai-features
```

Somente administradores do tenant autenticado podem alterar as flags. Enviar
`null` remove um override e restaura a heranca do ambiente.

## Implantacao

1. Aplicar `alembic upgrade head`.
2. Manter `AI_FEATURES_ENABLED=0` durante a verificacao.
3. Configurar o tenant piloto.
4. Ativar o disjuntor e liberar embeddings/LLM separadamente.
5. Monitorar falhas, duracao e qualidade antes de ampliar o rollout.

## Observabilidade dos jobs

Cada job persistido possui:

- `correlation_id` estavel durante enqueue, retry e recuperacao;
- `attempt_count` e `max_attempts` como campos consultaveis;
- `last_enqueued_at` para diferenciar espera normal de mensagem perdida;
- logs de claim e retry com a mesma correlacao.

`GET /jobs/{job_id}` devolve esses campos. `GET /jobs/summary` inclui
`retrying_count`, `exhausted_count`, `success_rate`,
`avg_duration_seconds` e `p95_duration_seconds`, alem da correlacao nos
jobs ativos e falhas recentes.

Jobs anteriores a migration recebem `correlation_id=id`, preservando a
rastreabilidade sem invalidar registros historicos.

### Retry manual

`POST /jobs/{job_id}/retry` permite que administradores e editores
reenfileirem um matching com falha. A operacao:

- preserva o mesmo `correlation_id`;
- mantem o contador historico de tentativas;
- concede exatamente uma nova tentativa quando o limite foi esgotado;
- registra quantidade e horario dos retries manuais no payload;
- rejeita jobs ativos, concluidos, cancelados e uploads sem arquivo persistido.

## Idempotencia e falhas estruturadas

Os endpoints de criacao de jobs aceitam o header `Idempotency-Key`:

- `POST /editais/upload`;
- `POST /editais/{edital_id}/match`;
- `POST /crm/notices/{notice_id}/matches/run-job`.

Repetir uma chamada com a mesma chave, tenant e tipo de job retorna o
`job_id` original e nao publica uma segunda mensagem. A restricao unica no
banco protege inclusive contra duas requisicoes concorrentes. Chaves podem ter
ate 128 caracteres.

Falhas agora possuem `failure_code` separado da mensagem humana:

- `timeout`;
- `dependency_unavailable`;
- `execution_error`;
- `feature_disabled`;
- `worker_interrupted`;
- `cancelled`.

## Painel operacional P1

A tela de Jobs tambem funciona como painel de incidentes da IA:

- identifica jobs com tentativas esgotadas (`dead_letter`);
- separa cancelamentos de falhas operacionais;
- agrega falhas das ultimas 24 horas por `failure_code`;
- classifica o estado da fila como `healthy`, `degraded` ou `critical`;
- gera alertas para jobs travados, tentativas esgotadas e dependencias indisponiveis;
- permite filtrar dead letters pela API com `GET /jobs/?dead_letter=true`;
- permite reprocessar jobs de matching e CRM diretamente pela interface.

Uploads esgotados continuam exigindo um novo envio do arquivo, evitando retry
com referencia temporaria indisponivel. Jobs cancelados nunca podem ser
reenfileirados.

## Quota mensal de jobs por empresa

O administrador configura `monthly_job_limit` em
`PATCH /auth/tenant/ai-job-quota`; `GET` no mesmo caminho informa uso,
restante e inicio do proximo periodo. `null` significa sem limite (padrao),
enquanto `0` bloqueia novos jobs. A tela de Configuracoes exibe e altera o
limite.

A quota conta novos jobs de upload/OCR, matching legado e matching CRM criados
no mes UTC, independentemente do resultado. Requisicoes com a mesma chave de
idempotencia reutilizam o job existente sem consumir outra vaga. A admissao e
serializada por tenant no PostgreSQL, evitando ultrapassar a quota em chamadas
concorrentes. Ao esgotar o limite, a API retorna HTTP 429. Retry do mesmo job
nao cria uma nova unidade e nao conta novamente.

Esta quota limita volume de processamento; nao e uma quota de tokens ou de
custo monetario.

## Telemetria de consumo dos provedores

A migration `20260921_02` cria `ai_usage_events`; `20260922_01` acrescenta
resultado e codigo de falha. Cada chamada **concluida**
de OpenAI ou Ollama dentro de um contexto de empresa grava provedor, modelo,
operacao, `correlation_id` de job quando disponivel, duracao e contagens de
tokens fornecidas pelo proprio provedor. Prompts, respostas e dados do cliente
nao sao persistidos nessa tabela. Se o provedor nao informar tokens, os campos
ficam nulos; nao ha estimativa artificial nem conversao automatica em dinheiro.

O contexto cobre jobs de upload/processamento, matching legado, matching CRM,
chat de edital, extracao de datasheet e matching CRM sincrono. A contagem de
embeddings Ollama depende de o retorno do provedor incluir contadores. Chamadas
fora desses fluxos nao sao incluidas no painel. A persistencia e best-effort
e usa sessao independente para que falhas de telemetria nao quebrem a inferencia
ou sejam revertidas por rollback do job.

Falhas de chamada ao provedor sao registradas separadamente com um codigo
generico (`timeout`, `dependency_unavailable`, `rate_limited` ou
`provider_error`). A excecao original continua sendo propagada, mas sua
mensagem nao e salva na telemetria. Falhas nao sao contabilizadas como tokens
consumidos, pois a resposta do provedor pode nao informar uso parcial.

`GET /ops/ai-usage` exige papel `admin`, filtra pelo tenant autenticado e
resume o mes UTC por provedor, modelo e operacao. A tela Configuracoes exibe
chamadas concluidas, falhas e totais reportados, destacando chamadas sem
contagem completa. A medicao ainda nao aplica limite de tokens ou custos.
