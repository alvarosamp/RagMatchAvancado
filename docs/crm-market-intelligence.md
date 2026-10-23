# Inteligência de mercado do CRM

O painel `/crm/inteligencia-mercado` usa os itens dos editais cadastrados, exceto os descartados (`not_pursued`). O intervalo de datas se refere ao cadastro do edital, não à disputa. Todos os indicadores, rankings e exportações usam o mesmo recorte de categoria, UF, busca e alertas.

## Categorias e atributos

Cabos DAC, ópticos e AOC são famílias separadas dos módulos ópticos. Categorias específicas existentes são respeitadas; descrições de itens sem categoria ou com categoria genérica permitem identificar cabos. A normalização de importações legadas reconhece aliases de cabos e preserva objetos e listas de atributos. O contrato V8 e seus dados originais permanecem preservados.

Marca, modelo e características são lidos de `raw_payload`, `bi_features`, campos legados de BI e rótulos explícitos da descrição. Portas podem ser extraídas de uma descrição de switch que declare a quantidade. Marcas vencedoras e produtos sugeridos pelo catálogo não entram na demanda solicitada. Referências históricas com marca/modelo juntos têm um recorte próprio: não são separadas por suposição.

Para novos campos conhecidos, estenda `DIMENSIONS` em `bid-buddy/src/lib/market-intelligence.ts` com um rótulo e aliases. Outros atributos presentes em `bi_features` aparecem automaticamente no seletor, com o caminho completo para evitar colisões entre blocos. Não é necessária uma coluna nova no banco para cada característica.

Exemplo de item importado:

```json
{
  "categoria": "Cabo DAC",
  "marca": "ACME",
  "modelo": "DAC-10G-3M",
  "quantidade": "20",
  "caracteristicas_bi": {
    "cabo_dac": {
      "velocidade_gbps": 10,
      "comprimento_m": 3,
      "conectores": ["SFP+", "SFP+"],
      "compatibilidade": "Plataforma declarada no edital"
    }
  }
}
```

## Rankings e relatórios

É possível ordenar por quantidade, linhas de itens, editais distintos ou valor estimado. Um edital conta uma vez por grupo. Quantidade ausente vale zero e não vira uma unidade artificial. Modelos são agrupados por marca e modelo. A participação usa a métrica selecionada e inclui itens sem o atributo no denominador; em editais, participações podem se sobrepor porque um edital pode solicitar várias marcas.

O painel mostra a cobertura de cada atributo e os líderes do recorte. O CSV exporta o ranking completo selecionado. `Relatório / PDF` abre a impressão do navegador para salvar o relatório com resumo, filtros e tabela em PDF. A impressão oculta navegação e controles e repete o cabeçalho da tabela.

Itens antigos sem marca ou modelo separado continuam sem essa informação. Para preencher esses campos, enriquecer ou reimportar o JSON com atributos documentados; esta mudança não inventa dados nem executa reanálise automática dos arquivos originais.
