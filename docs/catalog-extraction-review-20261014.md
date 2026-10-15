# Revisão das extrações documentais no catálogo

A ficha técnica mantém a descrição em um bloco separado, na leitura e na edição. As extrações arquivadas agora são agrupadas por SHA do documento e pela página que contém o identificador. PDFs de até quatro páginas com o identificador são apresentados primeiro para conferência da variante; páginas gerais de guias permanecem recolhidas. Essa prioridade não aprova aplicabilidade.

Limites Min/Typ/Max são mostrados como mínimo, típico e máximo e adicionados ao rascunho sem converter campos ausentes em zero. Valores originais, condições, tabelas, página e SHA continuam preservados. Campos reconhecidos têm rótulos em português. Regras textuais explícitas estruturam DDM, conector, fibra, receptor e dissipação; alternativas ambíguas continuam como texto. Duplicatas iguais na mesma página são recolhidas na apresentação; o arquivo original continua integral.

“Adicionar à ficha” abre o editor com a proposta. A ação não altera o produto até salvar e não sobrescreve um atributo já existente. Documento anexado cujo nome é o SHA do arquivo é vinculado automaticamente; demais documentos podem ser selecionados no editor. A evidência começa sem revisão, com aplicabilidade pendente. Marcar como conferido exige um documento e uma página válidos, validados pelo servidor. Condições e extração original acompanham o atributo salvo. As regras funcionam sem IA.

No exemplo PRE-XFP-B23-40, há 34 propostas no PDF específico e 79 trechos distintos em outras páginas/famílias, após recolher duplicatas. A descrição do PDF diz SFP+ enquanto a LPU diz XFP; a divergência é exibida no grupo e no editor. Os valores não são aprovados automaticamente.

Validação: seis testes de agrupamento, limites, zeros, negativos, alternativas, conflitos e origem; um teste de componente cobrindo adoção e salvamento com fonte, limites e evidência não conferida; regressão das páginas e bibliotecas de inteligência; build em exportação limpa com todos os patches aplicados; conferência no Docker e navegador.
