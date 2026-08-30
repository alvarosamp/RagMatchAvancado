# Dataset de avaliação do matching a partir do CRM

## Objetivo

O CRM já registra a escolha humana do produto do catálogo vinculado a cada item do edital. Essa escolha é aproveitada como **rótulo de recuperação**: o produto confirmado deveria aparecer no ranking produzido pelo matcher.

O endpoint abaixo exporta um dataset versionado e calcula Recall@K, MRR e NDCG:

```http
GET /api/crm/matches/evaluation-dataset
```

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

Itens do mesmo edital possuem o mesmo `split_group`. Ao formar treino/teste, divida por esse campo para impedir que itens quase idênticos do mesmo edital apareçam dos dois lados.
