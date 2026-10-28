# Auditoria: inteligência técnica para negociação com fornecedores

## Objetivo confirmado

Preparar uma reunião com um fabricante/fornecedor usando demanda observada nos
editais captados, modelos citados, requisitos técnicos recorrentes, desempenho
dos produtos da empresa e oportunidades de cobertura do portfólio.

Esta revisão inspecionou código local. Não consultou produção, o ERP autenticado
nem datasheets de fabricantes. Os testes anteriores de ingestão não certificam
a qualidade desse relatório comercial. A implementação atual é parcial para
este objetivo.

## Achados

### 1. Identificação ainda depende do catálogo conhecido

`bid-buddy/src/lib/product-intelligence.ts` cruza códigos exatos com modelo/MPN
do catálogo local. Distingue associações ambíguas e exclui um trecho explícito de
compatibilidade. Entretanto, a separação de marca/modelo não constitui um cadastro
mestre verificado de fabricantes. Um modelo citado que não está no catálogo pode
continuar sem identificação. Campos de marca/modelo explícitos e uma string
combinada de referência ainda são tratamentos diferentes.

**Critério de correção:** conservar menções separadas com papel, marca, modelo,
part number, variante/revisão, trecho original, fonte, método e revisão. Distinguir
referência, exclusividade declarada no texto, equipamento de compatibilidade,
produto ofertado e produto vencedor. A indicação do papel não substitui análise
do edital original.

### 2. A marca de demanda pode ficar subcontada

`backend/app/market_intelligence/crm_source.py` lê a marca de demanda de
`raw_payload.marca` ou `raw_payload.brand`. O contrato de entrada também transmite
referências em `direcionamento_marca.marca_modelo`. Uma referência existente nesse
campo pode aparecer na tela como texto, mas não alimentar o ranking analítico de
marca como uma menção estruturada.

**Critério de correção:** ranking de marca explicitamente citada com cobertura,
papel da menção e evidência. Associação de catálogo e compatibilidade devem ter
indicadores próprios, sem aumentar artificialmente a demanda de marca.

### 3. Modelo do catálogo não é levado explicitamente ao snapshot analítico

A reconciliação de produtos em `crm_source.py` envia nome, marca, MPN, SKU, GTIN,
categoria e especificação para a entidade canônica, mas não envia `product.model`
como atributo próprio. A identidade por marca+MPN existente é útil, porém não
substitui a distinção entre modelo comercial, SKU interno e part number.

**Critério de correção:** conservar campos separados, aliases revisados e vínculo
entre os identificadores do catálogo e do ERP. Variações de escrita da marca
precisam convergir sem fundir revisões/variantes técnicas diferentes.

### 4. “Meus produtos que mais saem” ainda precisa de uma definição de evento

O conector Bling usa `/pedidos/vendas`. O adaptador conserva a situação original,
mas registra as linhas como `outcome='ordered'`. Pedido, vitória em licitação,
faturamento e recebimento são eventos diferentes. O agregado `relationship_report`
atual forma `product_demand` a partir de fatos de demanda, não de fatos de venda.

**Critério de correção:** tabelas distintas por modelo para ofertado, ganho,
pedido e faturado; incluir devoluções/cancelamentos conforme o contrato real da
origem. Quantidade, valor e período precisam informar a base de cálculo.

### 5. O relatório externo atual não tem o detalhamento técnico necessário

`sharing.py:PUBLIC_FIELDS` expõe produto, marca, categoria, itens, quantidade,
unidade, valor e cobertura dessas medidas. Não inclui modelo/MPN separado,
requisitos, comparadores, evidências técnicas nem vendas próprias por estágio.
Os perfis novos do frontend cobrem campos selecionados, não a ficha técnica
completa. O extrator textual `domain.technical_attributes` também é limitado.

**Critério de correção:** dossiê por fornecedor com rankings separados e uma
matriz técnica verificável. Não considerar o link público atual um dossiê pronto.

## Contrato técnico necessário

Para cada requisito, preservar:

`categoria → atributo → operador → valor → unidade → obrigatório/opcional →
trecho original → documento/página → status de revisão`.

Para cada característica de produto, preservar:

`fabricante → modelo → MPN → variante/revisão → atributo → valor/unidade →
datasheet/versão/página → data de verificação`.

Exemplos de dimensões a modelar, sem preencher valores por inferência:

| Categoria | Dimensões técnicas |
|---|---|
| Switch | Portas por tipo/velocidade, uplinks e quantidade, padrões PoE, orçamento total e por porta, capacidade de comutação, encaminhamento, VLAN, funções/protocolos L3, empilhamento, fontes e redundância |
| Access point | Padrões Wi-Fi, bandas, fluxos por rádio, largura de canal, uplink Ethernet, alimentação, consumo, proteção ambiental, controlador/ecossistema e licenças |
| Módulo óptico | Formato, velocidade, padrão óptico, comprimento de onda, fibra, conector/polimento, alcance, DOM/DDM, temperatura, codificação e compatibilidade com equipamento/versão |
| DAC/AOC | Formato em cada ponta, velocidade, breakout/topologia, comprimento, ativo/passivo quando aplicável e compatibilidade |
| Patch cord | Meio, categoria/fibra, construção, conectores em cada ponta, polimento, comprimento, blindagem, condutor e polaridade quando aplicável |

Não converter “capacidade ≥ X” em igualdade, nem “uplink SFP+” em comprovação de
módulos fornecidos. Desconhecidos, conflitos e requisitos não comparáveis devem
permanecer visíveis. Recomendações de produto exigem documentação oficial e
comparação revisada; uma semelhança de perfil não comprova atendimento.

## Dossiê comercial de destino

1. **Demanda explícita por marca/modelo:** editais distintos, itens/cotas,
   quantidades, valor estimado observado, período, fonte e evidências.
2. **Demanda técnica sem marca:** combinações de requisitos e sua recorrência.
3. **Portfólio do fornecedor:** modelos documentados que podem cobrir cada
   perfil; atendimento confirmado, pendente ou não atendido por requisito.
4. **Desempenho próprio:** ofertado, ganho, pedido e faturado por SKU/modelo,
   conservando os denominadores e a origem de cada indicador.
5. **Pauta de negociação:** modelos com demanda e saída comprovadas, lacunas
   técnicas, volumes por período, necessidade de disponibilidade e preço-alvo.

O universo é “editais captados/importados”, com cobertura das fontes e data da
última carga. Não representa automaticamente o mercado nacional. Valor estimado
de edital não é venda nem receita comprovada. Referência de marca não é compra
efetiva dessa marca; homologação/ganho também não é faturamento.

## Sequência recomendada

Primeiro fechar identidade e papéis de marca/modelo, com uma amostra revisada.
Depois consolidar demanda técnica por categoria e rastrear as vendas próprias
ao mesmo cadastro mestre. Só então montar o dossiê externo. O primeiro aceite
deve demonstrar que um módulo compatível com um switch de outra marca não gera
demanda falsa de switches e que uma oferta não vira uma venda no ranking.
