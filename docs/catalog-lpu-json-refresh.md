# Atualização automática do JSON técnico do catálogo

A importação existente em `POST /api/crm/imports/lpu` agora gera ou atualiza o JSON
em `CrmCatalogProduct.specification` na mesma transação dos dados comerciais.
Não é necessário executar o coletor de arquivos para atualizar o catálogo.

O JSON usa `atributos`, `sku` e `categoria`, compatíveis com a comparação técnica.
`dados_lpu` preserva a descrição original, os campos da linha, a aba, a linha,
o link da LPU e a versão da importação. Os atributos explícitos reconhecidos por
regras ficam marcados como `informado_na_lpu`, sem evidência de datasheet.
Os demais dados continuam disponíveis nos campos originais para revisão manual.

Na reimportação, atributos gerados pela LPU são recalculados. Valores que deixaram
de estar presentes são removidos, em vez de permanecer como características antigas.
Atributos manuais ou de datasheets, incluindo seus aliases, revisão e evidências,
são preservados. Divergências podem ser consultadas em
`dados_lpu.atributos_extraidos`. Ausência de PoE ou gerenciamento não gera `false`.

O comportamento vale para os produtos aceitos pelo importador existente, com seus
filtros de disponibilidade e tratamento de duplicatas. Produtos ausentes agora seguem o fluxo de revisão e preservação descrito em
`crm-lpu-validity.md`, sem exclusão automática. A resposta inclui `technical_jsons_refreshed`, a
quantidade de operações de criação/atualização, incluindo linhas duplicadas.

Os JSONs avulsos em `outputs/LPU_2026-10-14` continuam sendo uma entrega de arquivos
da coleta anterior; não são sincronizados com a aplicação nem com o HD externo.
A sincronização automática implementada ocorre no JSON persistido de cada produto
do catálogo. A mudança precisa ser publicada no ambiente que recebe a LPU.
