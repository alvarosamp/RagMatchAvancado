# Comparação técnica lado a lado

O match manual apresenta cinco colunas: tipo, descrição do ponto, valor exigido no edital, valor do produto do catálogo e atendimento. O seletor acima da tabela escolhe o produto real a comparar; as opções na quarta coluna continuam filtrando progressivamente o catálogo e redefinem a seleção ao mudar. A descrição completa permanece separada.

O resultado usa a comparação determinística retornada pela API. Falhas aparecem como “Não atende”, atendimento comprovado como “Atende”, e dados ou evidências ausentes como “Conferir”, com o motivo. Uma escolha de filtro não se torna aprovação técnica. Selecionar um produto permanece um rascunho até salvar.

Validação: oito testes do match e da revisão documental passaram, incluindo a distinção entre filtro, dado cadastrado e evidência pendente. O patch foi conferido contra a base de origem, o CRM foi compilado e o fluxo foi verificado no navegador e Docker local.
