# Match manual por item (prévia local)

O processo principal fica na aba Match de cada edital do CRM. Na aba Itens, Exportar JSON aparece ao lado de Detalhes, por item. A exportação geral do edital continua disponível.

1. Entre em Match no edital: os itens aparecem em uma tabela com descrição, quantidade, situação e ações.
2. Abra Match no item. O JSON do próprio item é carregado automaticamente, retomando requisitos e filtros salvos quando houver.
3. Para atualizar o rascunho a partir do item, use Carregar JSON atual do item, sem baixar arquivo. Importar arquivo ou colar texto fica em Usar outro JSON. A importação preserva o JSON original e só modifica o item ao salvar.
4. Escolha a categoria. Mapeie cada ponto para uma característica, condição e valor, marcando quais pontos usar para filtrar.
5. Compare os produtos restantes na tabela: produto/modelo, SKU, situação e uma coluna para cada característica usada nos filtros. Escolha um produto e confira a matriz completa. Todos os requisitos continuam valendo, mesmo quando desmarcados como filtro.
6. Salve requisitos/filtros ou um candidato para revisão. A confirmação depende do resultado ATENDE, revisão da descrição e evidências vinculadas ao produto.

Não há chamada de IA, embeddings, job de match ou MLflow no novo processo. A API calcula os filtros de forma síncrona pelo motor de regras. Resultados antigos ficam em uma seção de consulta, sem disparar novo processamento.

## Dados incompletos

Contagens explícitas como `24x10/100/1000M RJ45 + 4x100M/1000M/10G SFP+`, camada e gerenciamento na descrição da LPU podem auxiliar a pré-seleção. Essas informações são temporárias, têm origem comercial e não alteram as fichas ou ganham evidência documental. Ausência de informação continua pendente. O contador de dados pendentes permanece visível; a lista pode ser exibida pelo usuário.

Categoria, filtros, requisitos mapeados, JSON original, usuário e data são salvos em `raw_payload._manual_match`, com registro no histórico. A API mantém os campos anteriores do JSON e não altera quantidades, preços negociados ou mínimos. Um candidato pendente fica como sugestão; não é vinculado como confirmação comercial. Alterações concorrentes do item ou da ficha causam 409, exigindo atualizar a comparação.

O fluxo não garante extrair todos os pontos de uma descrição: sem requisitos estruturados, o usuário monta a tabela manualmente. Protocolos e condições não mapeados continuam pendentes. Escolher um filtro não elimina um requisito. A confirmação verifica documento, produto, empresa, versão e hash no servidor.

## Normalização dos nomes

Campos e categorias usam aliases explícitos para variações de acentos, espaços e escrita, como `Portas RJ-45`, `Quantidade de portas RJ45` e `RJ-45 ports`. Um alias cadastrado para dois campos diferentes gera erro de configuração; não há substituição silenciosa nem aproximação por similaridade.

SFP, SFP+, SFP28, QSFP+, PoE, PoE+ e PoE++ mantêm significados distintos. Nomes de produto, modelo e SKU não passam pela normalização dos campos. Valores textuais preservam pontuação e versões, por exemplo `L2+` e `L2`, ou modelos com sufixos diferentes. O JSON original permanece guardado.

Os cartões usam as mesmas chaves canônicas da comparação. Quando duas fontes informam valores diferentes para a mesma característica, a comparação fica pendente; o cartão aponta para a matriz, sem escolher um valor arbitrariamente. Campo desconhecido exige mapeamento e categoria desconhecida não aprova um produto.

## Desenvolvimento e artefatos

Código backend: app/services/manual_match.py e app/routers/manual_match.py. Não há nova migration para este fluxo; a configuração usa o JSON existente do item. Regras 1.3.1 incluem camada, características de Wi-Fi e aliases explícitos com validação de ambiguidade.

O CRM privado foi compilado da revisão 463f56b, em uma cópia isolada, preservando o checkout original. As mudanças reproduzíveis estão em docs/crm-manual-match-source.patch. O script scripts/sync-bid-buddy.mjs aplica os patches de sessão e match antes do build e atualiza os hashes dos artefatos. Os bundles publicados no frontend têm nomes novos para evitar reutilização dos módulos antigos em cache.

```bash
node scripts/sync-bid-buddy.mjs --source-path=output/technical-preview/crm-session-source
docker build -f preview/Dockerfile -t ragmatch-technical-preview-api:local .
docker build -t ragmatch-technical-preview-frontend:local frontend
docker compose -f preview/compose.yaml up -d --wait
```

## Demonstração

Use o edital **EXEMPLO-MATCH-MANUAL** no Docker local. Seus três produtos e o PDF são explicitamente simulados. A LPU original e os editais reais da VPS não são modificados por essa demonstração.

Para recriar o exemplo:

```bash
python3 preview/manual_match_demo.py
```

## Validação

16 testes HTTP: qa/test_manual_match.py (JSON por item, filtragem progressiva, falta de evidência, requisitos desmarcados, preservação de preços, fonte divergente, JSON inválido, isolamento, permissão e confirmação documentada).

38 testes específicos de normalização, 16 de match manual, 62 de autenticação/sessão e 88 de regressão do motor, adaptador V8, exportação e extração passaram no Docker local (204 no total). No navegador real, a validação anterior do fluxo cobriu exportação e importação do mesmo arquivo, filtros ponto a ponto, confirmação do exemplo e persistência.

A prévia local usa http://localhost:13089. Esta mudança ainda não foi publicada na VPS.
