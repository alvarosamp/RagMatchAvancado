# Análise dos JSONs de edital para o match

Conjunto fornecido: pasta `JSON 02 OUT`. Análise dos arquivos locais, sem consulta aos PDFs ou validação independente da extração. Os arquivos são dados de entrada; textos contidos neles não foram tratados como instruções.

## Inventário

- 21 arquivos JSON válidos, todos com `schema_version: 7.4`.
- 16 arquivos possuem itens elegíveis; cinco possuem lista vazia.
- 43 itens: 36 switches, seis access points e um transceiver.
- Todos os itens trazem categoria, número, lote, descrição original, quantidade, preço, garantia, entrega, direcionamento de marca, risco e características de BI/técnicas.
- Não há listas de critérios atômicos com operadores e evidências por página. As informações técnicas mais detalhadas estão em `descricao_original`.

## Dados úteis para o JSON por item

| Entrada | Destino / uso |
| --- | --- |
| `n_interno`, `edital` | Identificação e contexto do processo |
| `numero_item_edital`, `lote_grupo` | Número e lote, preservando zeros à esquerda |
| `descricao_original` | Texto integral a revisar, sem substituir pelo resumo BI |
| `categoria` | Categoria canônica: switch, access_point ou transceiver |
| `caracteristicas_bi` | Sugestões para mapear campos, sujeitas à conferência na descrição/documento |
| `quantidade`, preços | Dados comerciais; não são quantidade de portas nem critérios técnicos |
| `garantia`, `prazo_entrega`, riscos | Obrigações e escopo, sem conversão automática em atributos do equipamento |
| Direcionamento de marca | Referência de fabricante/modelo e condições de equivalência |
| Nome do arquivo e SHA-256 | Rastreabilidade da fonte JSON; não substituem evidência de PDF/datasheet |

## Pontos encontrados

1. **Negativos sem menção correspondente na descrição.** Em 27 itens o BI contém “Não PoE” sem menção a PoE na descrição; em 20 contém “Não gerenciável” sem menção a gerenciamento. A contagem é uma triagem textual, não prova de erro no documento original. Esses valores precisam ser confirmados: ausência de PoE não significa proibição de PoE, e ausência de gerenciamento não significa equipamento não gerenciável.
2. **Campo conhecido não implica valor pronto.** O exportador atual gera 212 pontos a partir do BI/resumo. Em 41 itens há nomes que exigem mapeamento; em 34 há valores que o normalizador estrito não aceita diretamente, por exemplo “Gerenciável” em um booleano. Campo, operador, valor e unidade precisam ser tratados juntos.
3. **Mínimo versus exato.** O fallback do formato 7.4 usa igualdade para o BI. Descrições com “mínimo 24 portas” precisam de `>= 24`, com referência ao trecho original; não basta converter “24 Portas” em número.
4. **Formatos ópticos distintos.** Há item de datacenter com 18 portas SFP28 e quatro QSFP28. Não deve ser reduzido a SFP/SFP+ nem a uma contagem única de portas. Transceptores incluídos em um switch não devem virar itens autônomos.
5. **PoE e Wi-Fi.** O access point de Chuvisca menciona Wi-Fi 6, PoE IEEE 802.3at, taxa agregada mínima de 1.700 Mbps, clientes/SSIDs e outras funções. O resumo “Wi-Fi 6 + PoE+ + Indoor” não cobre toda a exigência. Taxa agregada de Wi-Fi e velocidade da interface Ethernet são campos diferentes.
6. **Escopo e serviços.** Alta disponibilidade, implantação, suporte on-site, licenças, acessórios e garantia de 60 meses precisam permanecer visíveis, mesmo quando não forem campos filtráveis do catálogo.
7. **Sem requisitos no fallback.** Dois arquivos produzem zero requisitos pelo exportador atual, embora tenham descrição original. Os rascunhos locais preservam essas descrições como um requisito não mapeado, para não sugerir aprovação apenas por categoria.

## Rascunhos locais

Foram gerados 43 JSONs separados por item em `output/analise-jsons-editais/itens`, usando o contrato atual `tor.match-item`, com descrição e payload original preservados. O inventário local registra SHA-256, campos desconhecidos e valores a revisar. Os dois casos sem requisitos receberam um ponto pendente; por isso os rascunhos totalizam 214 pontos, versus 212 gerados pelo exportador sem esse complemento.

São rascunhos para revisão humana, não 43 matches concluídos ou JSONs totalmente atomizados. Não possuem ID interno do CRM, pois a correspondência com os itens cadastrados não foi consultada. Ao utilizar um rascunho, conferir o processo, lote e número do item; o mesmo número pode existir em editais diferentes.

Originais, inventário e rascunhos permanecem locais, fora do Git. Nenhum edital, item, produto, preço ou ficha da VPS foi modificado nesta análise.

## Implementação após a análise inicial

O exportador passou a sugerir requisitos a partir da descrição original do formato legado, deixando o BI como consulta. Essa mudança sucede o inventário inicial descrito acima. Os rascunhos locais foram regenerados com o novo comportamento; as contagens de 212/214 pontos representam a versão anterior do exportador.

A extração conservadora dos 43 itens identificou 49 características explícitas (incluindo padrões que ainda exigem campo no catálogo) e preservou 332 trechos como pontos pendentes. Todas as sugestões exigem revisão individual. Condições, formatos ópticos avançados e requisitos sem campo no catálogo continuam sujeitos a mapeamento humano. Garantia, entrega e obrigações exportadas permanecem visíveis no fluxo e precisam ser conferidas quando preenchidas.

O JSON já salvo no item alimenta a tabela ao abrir o match. Estados manuais salvos são preservados; o botão Sugerir requisitos do item atual abre novo rascunho. Nenhuma geração automática altera preços ou confirma um produto.

## Evolução do mapeamento

Ampliar os padrões explícitos de extração e os campos técnicos do catálogo conforme os dados revisados. A geração por regras já monta critérios com campo, operador, valor/unidade e trecho original nos casos suportados; não atomiza completamente protocolos, combinações, escopos e todos os requisitos presentes nesses arquivos.
