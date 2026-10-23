# Match técnico por atributos

O motor em `backend/app/services/technical_matching` compara JSONs sem LLM,
embeddings, RAG ou acesso à rede. Ele complementa o matching atual: o CRM usa
esse caminho quando encontra uma chave `requisitos` em `raw_payload` ou em um
objeto JSON salvo no campo textual `technical_characteristics` do item.
Itens sem esse contrato continuam no fluxo existente.

O catálogo de switches em `data/Produtos/all_devices.json` já contém atributos,
mas parte dos valores ainda exige conversão: por exemplo, `"24x 1G"` reúne
quantidade e velocidade. O catálogo técnico `Product.data` e o catálogo do CRM
`CrmCatalogProduct.specification` são modelos distintos; este trabalho não migra
ou importa automaticamente os dados de um para o outro.

## Contrato

Item do edital, em `raw_payload` ou como JSON em `technical_characteristics`:

```json
{
  "categoria": "switch",
  "requisitos": {
    "portas_rj45": {"operador": ">=", "valor": 24, "obrigatorio": true},
    "poe_budget_w": {"operador": ">=", "valor": 370, "obrigatorio": true},
    "portas_sfp_plus": {"operador": ">=", "valor": 4, "obrigatorio": true}
  }
}
```

Produto do CRM: salvar este JSON como texto no campo `specification` existente:

```json
{
  "categoria": "switch",
  "atributos": {
    "portas_rj45": 24,
    "poe_budget_w": {
      "valor": 410,
      "unidade": "W",
      "evidencia": {"documento": "datasheet-v2.pdf", "pagina": 3}
    },
    "portas_sfp_plus": 4
  }
}
```

Também é aceito um objeto plano de atributos em `specification`. A categoria
vem do JSON ou do campo `category` do CRM. Um catálogo com especificação apenas
em texto recebe `VERIFICAR` para os requisitos estruturados; o motor não presume
que o texto comprove os atributos. A lista de requisitos deve representar todas
as exigências que se deseja avaliar: o resultado não valida cláusulas omitidas.

Uso independente, com `backend` no caminho de importação:

```python
from app.services.technical_matching import compare_item_product

resultado = compare_item_product(item_json, produto_json)
```

## Decisões e score

- `ATENDE`: obrigatórios comprovados e nenhuma comparação pendente.
- `NAO_ATENDE`: pelo menos uma falha obrigatória demonstrada, inclusive categoria
  incompatível. Uma média alta não altera essa decisão.
- `VERIFICAR`: atributos ausentes, valores ambíguos, aliases conflitantes,
  unidades incompatíveis ou regras inválidas. Falhas obrigatórias demonstradas
  têm precedência sobre pendências.

`obrigatorio` assume `true`; `peso` assume `1` e deve ser positivo e finito.
Operadores numéricos: `==`, `>=`, `<=`, `>` e `<`. Booleanos e textos aceitam
`==`. Textos preservam pontuação técnica, com comparação sem diferença de caixa
e com espaços normalizados; não há inferência de equivalências semânticas.
Uma falha opcional reduz o score sem reprovar. Uma pendência opcional ainda exige
verificação.

`score` é a soma dos pesos atendidos dividida pelos pesos de todos os requisitos.
`compatibilidade_conhecida` considera apenas os requisitos verificáveis, e vale
`null` se nenhum foi verificado. `cobertura` indica a fração ponderada verificada.
Todos são frações de 0 a 1. A categoria é uma trava separada, com peso zero.

O resultado inclui `detalhes` com valores originais e normalizados, unidade,
operador, obrigatoriedade, peso, motivo e fontes, além de `falhas_obrigatorias` e
`pendencias`. Metadados de evidência nos valores permanecem nas fontes.

No CRM, a justificativa e as listas existentes `matched_features` e `conflicts`
persistem a explicação por atributo; pendências aparecem também em `conflicts`.
O método é identificado por `source_method = deterministic_json`. Não há nova
coluna ou alteração de contrato do frontend. O resultado estruturado completo é
retornado pela função Python; não foi criado um endpoint específico para ele.

Para o resumo atual do CRM, o `overall_score` de um reprovado é zero e o de um
pendente é limitado abaixo do limiar de match forte. A fração técnica original
continua na justificativa. Todos os candidatos são comparados antes do corte de
pré-seleção. Candidatos sem dados e reprovados podem aparecer com score zero para
expor o motivo. O motor gera sugestões para revisão humana. Validações humanas
existentes são preservadas; o reaproveitamento por descrição não substitui uma
nova comparação de requisitos estruturados.

## Normalização e adoção

`rules.json` define aliases, tipos e unidades canônicas. Inclui portas RJ45,
PoE, SFP, SFP+, velocidade de uplink, comutação, gerenciamento, alcance e conector.
SFP e SFP+ são atributos distintos; `Uplinks` não é um alias de SFP+.
Conversões disponíveis: W/kW, Mbps/Gbps/Tbps e m/km. Números sem unidade usam a
unidade canônica do atributo; uma unidade pode ser informada na regra ou em
`{"valor": ..., "unidade": ...}`. Atributos personalizados podem ser comparados
com tipos inferidos do valor exigido; cadastre aliases e unidades para evitar
ambiguidades.

Valores como `"24x 1G"`, faixas e descrições compostas produzem `VERIFICAR`.
Separe-os em atributos comprovados durante a preparação do catálogo, mantendo
documento, página e versão como evidência. Não transforme ausência de informação
em `false` ou `0`.

Antes de ampliar a adoção, execute os dois métodos sobre os mesmos pares já
revisados no dataset do CRM. Compare falsos positivos, falsos negativos,
pendências, cobertura, tempo e custo. Este trabalho inclui testes sintéticos;
não realiza homologação por especialistas nem medição com um dataset real.

```powershell
.venv/Scripts/python.exe -m pytest tests/unit/test_technical_matching.py tests/unit/test_crm_match_scoring.py tests/unit/test_match_engine_scoring.py -q
```
