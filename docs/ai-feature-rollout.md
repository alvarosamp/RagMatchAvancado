# Rollout seguro das capacidades de IA

## Objetivo

As capacidades de IA possuem dois niveis de controle:

1. `AI_FEATURES_ENABLED` e o disjuntor global do ambiente. Quando desligado,
   nenhuma operacao que depende de OCR/modelo, embeddings ou LLM e iniciada.
2. `tenants.ai_features` guarda overrides por empresa. A ausencia de uma chave
   herda o comportamento padrao, enquanto `false` bloqueia somente aquela
   capacidade para o tenant.

O matching do CRM e uma excecao intencional: `crm_matching` pode continuar
ativo com o disjuntor global desligado, mas opera apenas com o ranking
lexical/deterministico. `crm_embeddings` e `crm_llm_rerank` continuam
desligados. Assim uma indisponibilidade do provedor nao paralisa a operacao.

## Capacidades

| Chave | Operacao protegida | Depende do disjuntor global |
| --- | --- | --- |
| `document_processing` | upload, OCR e indexacao de edital | sim |
| `matching` | matching do pipeline legado | sim |
| `edital_chat` | chat RAG por edital | sim |
| `datasheet_extraction` | extracao e preview de datasheet | sim |
| `crm_matching` | ranking base do CRM | nao; possui fallback deterministico |
| `crm_embeddings` | busca semantica no catalogo CRM | sim |
| `crm_llm_rerank` | reranking de candidatos por LLM | sim |

## API administrativa

Somente um administrador do tenant autenticado pode consultar ou alterar as
flags. Nao e possivel editar outra empresa pelo payload.

```http
GET /auth/tenant/ai-features
```

Cada capacidade retorna `enabled`, `configured`, `source` e `reason`. Os
motivos possiveis sao `enabled`, `tenant_disabled` e `global_disabled`.

Exemplo de rollout inicial, mantendo somente o fallback do CRM:

```http
PATCH /auth/tenant/ai-features
Content-Type: application/json

{
  "document_processing": false,
  "matching": false,
  "edital_chat": false,
  "datasheet_extraction": false,
  "crm_matching": true,
  "crm_embeddings": false,
  "crm_llm_rerank": false
}
```

Enviar `null` remove um override e faz a capacidade voltar a herdar o padrao:

```json
{"crm_embeddings": null}
```

## Implantacao

1. Aplicar `alembic upgrade head` para criar `tenants.ai_features`.
2. Manter `AI_FEATURES_ENABLED=0` durante a verificacao da API e dos workers.
3. Configurar os overrides do tenant piloto.
4. Ativar `AI_FEATURES_ENABLED=1` e liberar embeddings/LLM separadamente.
5. Monitorar falhas, tempo e qualidade antes de ampliar para outros tenants.

Jobs de matching do CRM revalidam `crm_matching` no worker. Portanto, desligar
a flag depois do enfileiramento impede a execucao e deixa o job como `failed`,
com motivo operacional explicito.
