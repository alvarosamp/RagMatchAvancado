# Datasheets no CRM

## Decisoes de compatibilidade

- O arquivo do datasheet usa `document_files`, a biblioteca operacional ja existente. Isso preserva upload, download, controle de acesso e versionamento sem criar um segundo armazenamento.
- `document_files.catalog_product_id` identifica o item de catalogo dono do datasheet. Uma nova revisao e filha da primeira revisao e recebe um numero de versao crescente.
- `crm_notice_product_datasheets` registra a versao vigente incluida para cada `crm_notice_products`. A associacao nao copia o arquivo fisico: um unico datasheet pode compor a documentacao de varios editais.
- Ao selecionar um produto para um item, o CRM cria ou atualiza essa associacao com a revisao vigente. Ao enviar uma nova revisao, todas as associacoes daquele produto passam a apontar para ela, de forma transacional.
- O ZIP de um edital combina arquivos anexados diretamente e os datasheets incluidos por essas associacoes. Nomes duplicados recebem sufixo numerico dentro do arquivo ZIP.

## Operacao

No catalogo, envie o arquivo no campo **Arquivo do datasheet**. Nos produtos ja cadastrados, o upload gera uma nova versao; o historico permanece disponivel no dialogo do produto. Ao vincular ou adicionar um produto em um edital, o datasheet vigente aparece na documentacao e e considerado pelo botao **Baixar todos**.
