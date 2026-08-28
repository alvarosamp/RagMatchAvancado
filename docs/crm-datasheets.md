# Datasheets no CRM

## Decisoes de compatibilidade

- O arquivo do datasheet usa `crm_catalog_product_datasheets`, armazenamento privado do catálogo. Ele não aparece nem pode ser escolhido no repositório operacional de documentos.
- Cada produto mantém versões de PDF ou DOCX em diretório próprio; a revisão mais recente é a vigente.
- `crm_notice_product_datasheets` registra a versão vigente incluída para cada `crm_notice_products`. A associação não copia o arquivo físico: um único datasheet pode compor a documentação de vários editais.
- Ao selecionar um produto para um item, o CRM cria ou atualiza essa associacao com a revisao vigente. Ao enviar uma nova revisao, todas as associacoes daquele produto passam a apontar para ela, de forma transacional.
- O ZIP de um edital combina arquivos anexados diretamente e os datasheets incluidos por essas associacoes. Nomes duplicados recebem sufixo numerico dentro do arquivo ZIP.

## Operacao

No catalogo, envie o arquivo PDF ou DOCX no campo **Arquivo do datasheet**. Nos produtos já cadastrados, o upload gera uma nova versão; o histórico permanece no próprio diálogo do produto. Ao vincular ou adicionar um produto em um edital, o datasheet vigente aparece automaticamente na documentação e é considerado pelo botão **Baixar todos**. Sem datasheet, o produto continua sendo vinculado normalmente.
