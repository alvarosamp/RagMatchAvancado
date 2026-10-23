# Importar JSONs de produtos e datasheets

No **Catálogo de produtos**, clique em **Importar JSONs e documentos**.

1. Selecione um ou mais arquivos individuais de `outputs/LPU_2026-10-14/produtos/`.
2. Opcionalmente selecione os PDFs de `outputs/LPU_2026-10-14/datasheets/`.
3. Clique em **Importar** e confira o resultado por arquivo.

Não selecione inventário, relatórios nem JSONs da pasta `documentos`: são arquivos de suporte, sem identidade individual de produto. Cada lote aceita até 600 arquivos, JSONs até 8 MB, documentos até 50 MB e até 300 MB no total. Se necessário divida o lote.

O importador identifica por SKU/código TOR exato dentro da empresa. Usa part number exato acompanhado da marca apenas quando não há SKU correspondente. Correspondências ambíguas não são importadas; confira os códigos no cadastro e no JSON antes de reenviar. Produtos novos são criados sem preço informado. Preços existentes e atributos técnicos protegidos são preservados.

As informações explícitas da LPU entram nos atributos usados pelo filtro. Todos os campos originais do JSON, incluindo tabelas, fontes e transcrições, ficam preservados em `specification.importacao_json_produto`. Dados de datasheet marcados para revisão não são promovidos automaticamente a fatos técnicos. A importação não confirma o atendimento de um edital.

PDFs/DOCX só são vinculados quando o SHA-256 do conteúdo corresponde ao registrado em `datasheets[].sha256` no JSON do produto. Caminhos e URLs do JSON não são abertos pelo servidor. Documentos já anexados com o mesmo conteúdo não são duplicados. Um mesmo PDF pode pertencer a vários produtos. Para um documento avulso sem vínculo no JSON, abra o produto em Editar e use a área de datasheets existente.

Endpoint autenticado (admin/editor): `POST /crm/imports/product-json`, multipart com campos repetidos `files`. Arquivos inválidos são rejeitados antes das alterações. Conflitos de identificação são apresentados por produto. Importação preserva o arquivo original dentro do JSON técnico; ela não usa IA.

Fonte do componente: `docs/crm-catalog-import-source.patch`. Build reproduzível pelo `scripts/sync-bid-buddy.mjs` sobre checkout limpo da fonte privada do CRM, aplicando os patches documentados em sequência.

Validação: `tests/unit/test_catalog_json_import.py` e `qa/catalog_json_import_checks.py` (banco SQLite isolado, associação por hash, deduplicação, preservação de preço/revisão, conflito e isolamento por empresa).
