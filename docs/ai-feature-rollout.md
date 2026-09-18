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
