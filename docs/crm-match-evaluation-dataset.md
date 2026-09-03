# Dataset de avaliação do matching a partir do CRM

## Objetivo

O CRM já registra a escolha humana do produto do catálogo vinculado a cada item do edital. Essa escolha é aproveitada como **rótulo de recuperação**: o produto confirmado deveria aparecer no ranking produzido pelo matcher.

O endpoint abaixo exporta um dataset versionado e calcula Recall@K, MRR e NDCG:

```http
GET /api/crm/matches/evaluation-dataset
```

Para gerar recomendacao de calibracao a partir do mesmo gold dataset:

```http
GET /api/crm/matches/calibration-report
```

Para mapear os itens anexados/vinculados manualmente e descobrir quais dados do CRM ja servem para novas IAs:

```http
GET /api/crm/matches/attached-products/ai-opportunities
```

Esse relatorio retorna:

- cobertura de campos tecnicos, comerciais e de labels;
- contagem por origem do vinculo (`manual_confirmed`, `match_confirmed`, `manual_kit`, sem origem);
- recomendacoes de uso para retrieval, decisao tecnica, kits, RAG com datasheet e modelos comerciais;
- fronteiras anti-vazamento para nao misturar preco/resultado com matching tecnico;
- amostra dos registros para auditoria.

Filtros disponíveis:

```text
notice_id=<uuid>
source=manual_confirmed|match_confirmed|manual_kit
include_unmarked=false
limit=500
```

Somente usuários `admin` ou `editor` podem exportar o dataset, e a consulta permanece isolada pelo tenant autenticado.

## Como os campos do CRM entram no dataset

### Entradas do matching técnico

- título do edital;
- descrição, código e categoria do item;
- características técnicas;
- garantia e prazo de entrega;
- marca/modelo direcionado e justificativa;
- campos estruturados de BI;
- payload original importado;
- categoria, marca, modelo, SKU/MPN, especificação, palavras-chave e equivalências do produto candidato.

### Rótulo humano

- produto do catálogo selecionado;
- origem da seleção (`manual_confirmed`, `match_confirmed`, `manual_kit` etc.);
- usuário/data da confirmação;
- observações da revisão.

`manual_confirmed` e `match_confirmed` são considerados prontos para avaliação de retrieval. `manual_kit` e vínculos sem origem continuam no export, mas exigem revisão antes de treinamento.

### Contexto comercial separado

Estes campos são úteis para Bid/No-Bid, preço e previsão de vitória, mas não entram nas features do matching técnico:

- quantidade e unidade;
- preço de referência e valor total;
- custo e preço mínimo/ofertado;
- item selecionado para disputa;
- resultado do edital;
- recomendação comercial atual.

A separação evita que informações registradas depois da decisão contaminem o benchmark técnico.

## Revisão humana da decisão

Depois de vincular um produto, a aba de match do CRM permite registrar:

- veredito `ATENDE`, `VERIFICAR` ou `NAO_ATENDE`;
- confiança da revisão;
- códigos de motivo, como `velocidade`, `temperatura` ou `dados_ausentes`;
- observação/evidência textual.

Com esses campos, o export passa a calcular matriz de confusão, precisão/recall/F1 por classe, macro-F1 e `false_accept_rate`. Registros antigos sem veredito continuam válidos para Recall@K, mas não entram nas métricas de decisão.

Sugestões marcadas como rejeitadas depois da confirmação de outro produto não são automaticamente negativos fortes: parte delas pode apenas ter perdido o ranking ou ser uma alternativa válida.

## Avaliação offline

Salve a resposta do endpoint em um arquivo JSON e rode:

```bash
PYTHONPATH=backend python mlops/scripts/evaluate_match_dataset.py dataset.json
```

Saída JSON para CI/MLflow:

```bash
PYTHONPATH=backend python mlops/scripts/evaluate_match_dataset.py dataset.json --json
```

Para simular pesos e thresholds offline:

```bash
PYTHONPATH=backend python mlops/scripts/evaluate_match_dataset.py dataset.json --calibration
PYTHONPATH=backend python mlops/scripts/evaluate_match_dataset.py dataset.json --calibration --json
```

Itens do mesmo edital possuem o mesmo `split_group`. Ao formar treino/teste, divida por esse campo para impedir que itens quase idênticos do mesmo edital apareçam dos dois lados.

## Recuperação híbrida e embeddings do catálogo

O matching do CRM agora persiste um embedding para cada produto do catálogo. A atualização é incremental: um hash SHA-256 representa apenas os campos pesquisáveis (nome, marca, modelo, MPN, SKU, categoria, especificação, descrição, palavras-chave, equivalências e notas). Preço ou margem não provocam reprocessamento.

Cada vetor registra provider, modelo, dimensão, hash da fonte e data de atualização. Ao executar o match:

1. somente produtos sem vetor, alterados ou produzidos por outra versão são recalculados;
2. o item do edital é vetorizado uma vez e reutilizado durante a execução;
3. todos os candidatos recebem score lexical e semântico antes do corte de top-K;
4. uma falha do provider mantém o ranking lexical, sem inventar score semântico;
5. o histórico do edital registra a versão e quantos vetores foram atualizados ou reutilizados.

Os vetores e metadados internos não são aceitos em gravações genéricas do CRM nem enviados para o frontend. A migração necessária é `20260831_01_catalog_embeddings.py` e depende de `20260830_01`.

Configuração padrão:

```text
OLLAMA_HOST=http://localhost:11434
OLLAMA_EMBED_MODEL=nomic-embed-text
ML_EMBED_DIMS=768
CRM_MATCH_EMBEDDING_WEIGHT=0.55
```

Trocar modelo ou dimensão invalida automaticamente os vetores persistidos. Alterar a dimensão exige também uma migração da coluna `vector`, pois o PostgreSQL fixa a dimensão no schema.

### Backfill operacional

Depois de aplicar a migration na VPS, consulte a cobertura:

```http
GET /api/crm/catalog/embeddings/status
```

Resposta esperada:

```json
{
  "total": 1200,
  "current": 1180,
  "stale": 20,
  "coverage": 0.9833,
  "reason_counts": {
    "missing_vector": 12,
    "source_changed": 8
  }
}
```

Para atualizar em lotes idempotentes:

```http
POST /api/crm/catalog/embeddings/backfill
Content-Type: application/json

{
  "active_only": true,
  "stale_only": true,
  "limit": 100
}
```

Repita a chamada enquanto `has_more=true`. O endpoint e admin-only porque consome provider de embeddings e grava vetores no catalogo.

### Calibracao recomendada na VPS

Fluxo sugerido:

1. rode `alembic upgrade head`;
2. rode o backfill ate `stale=0`;
3. rode matches em itens rotulados com `/api/crm/matches/ground-truth/run`;
4. consulte `/api/crm/matches/calibration-report`;
5. ajuste as variaveis recomendadas:

```text
CRM_MATCH_EMBEDDING_WEIGHT=<calibration.recommended.embedding_weight>
ML_THRESHOLD_ATENDE=<calibration.recommended.threshold_atende>
ML_THRESHOLD_VERIFICAR=<calibration.recommended.threshold_verificar>
```

O scorer do CRM usa `ML_THRESHOLD_ATENDE` e `ML_THRESHOLD_VERIFICAR` para classificar `strong`, `possible`, `weak` e `none`; portanto a calibracao passa a refletir o comportamento real do sistema.

## Itens anexados manualmente como combustivel de IA

Os itens anexados manualmente devem ser tratados como sinais humanos valiosos, mas com papeis diferentes:

- `manual_confirmed` e `match_confirmed`: pares positivos fortes para retrieval/ranking;
- `manual_kit`: sinal de composicao de kit ou multi-produto; exige tratamento separado antes de treino;
- item com `match_review_verdict`: label tecnico para calibrar decisao `ATENDE/VERIFICAR/NAO_ATENDE`;
- campos `raw_payload` e `bi_features`: bons para melhorar extracao e atributos estruturados;
- outcome, preco, margem, vencedor e decisao comercial: bons para IA comercial, mas proibidos como entrada do matching tecnico.

No banco local validado em 2026-08-31 havia 154 itens de CRM e 3 produtos de catalogo ativos, mas nenhum item ainda estava vinculado a um produto (`catalog_product_id` vazio). Tambem havia dados estruturados em alguns tenants: `raw_payload`/`bi_features` em 6 itens, caracteristicas tecnicas em 5 itens e preco de referencia em 56 itens. Na VPS com os dados reais, o endpoint `attached-products/ai-opportunities` deve ser o primeiro diagnostico antes de decidir qual modelo treinar.
