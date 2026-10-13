# Comparação V8 no CRM

Motor determinístico reaproveitado da branch conlicitacao, adaptador V8/tor.match-item, ficha documental revisada e matriz persistida. A aba Match do CRM agora apresenta a matriz, filtros por item, reavaliação e histórico. A página `/crm/comparacao-tecnica` no frontend principal continua disponível como ferramenta auxiliar.

## Operação

Aplicar a migração `20261012_01` antes de iniciar o backend atualizado. Compilar o frontend principal. A página usa a sessão autenticada existente e exige perfil editor/admin para alterações.

1. Anexar datasheet ao produto pela rota existente de catálogo.
2. Salvar ficha em `PUT /api/crm/catalog-products/{id}/technical-sheet`.
3. Executar `POST /api/crm/notices/{id}/matches/run` com `{"mode":"rules"}` ou a rota `run-job` com o mesmo modo.
4. Consultar matriz em `GET /api/crm/notices/{id}/matches`.
5. Confirmar apenas candidatos ATENDE. Para reavaliar explicitamente uma seleção, usar `POST /api/crm/matches/{id}/reevaluate`: a seleção humana é preservada e a matriz anterior fica no histórico.

Ficha demonstrativa (substituir o ID pelo datasheet privado realmente anexado):

```json
{
  "categoria": "switch",
  "revisao": "A",
  "variante": "24P",
  "atributos": {
    "portas_rj45": {
      "valor": 24,
      "evidencias": [{"documento_id": "ID-DO-DATASHEET", "pagina": 2, "revisado": true}]
    },
    "poe_budget_w": {
      "valor": 410,
      "unidade": "W",
      "evidencias": [{"documento_id": "ID-DO-DATASHEET", "pagina": 3, "revisado": true}]
    }
  }
}
```

O servidor calcula hash do arquivo, identifica sua versão e registra o revisor. A revisão é uma declaração humana; o motor não verifica automaticamente o conteúdo da página. Valores cadastrados via specification continuam aceitos no contrato nativo anterior; V8/export exige evidência documental. Falha numérica comprovada veta o produto mesmo com ausência de evidência; um valor favorável sem evidência fica pendente.

Critérios duplicados preservam ID e limites. Operadores cobre_faixa/range_covers, contem_todos/contains_all, contem_algum/contains_any e em/in avaliam faixas e conjuntos. Grupos explícitos E/OU combinam decisões em três estados. Condições em objetos, como {"tipo_fibra":"OM3"}, selecionam valores com o mesmo escopo na ficha; uma lista variantes permite valores diferentes por condição. Condições em texto e alternativas sem semântica explícita permanecem VERIFICAR. Temperatura usa C e comprimentos de onda Tx/Rx usam nm. Contagens fracionárias ou negativas são inválidas. Documento e versão das regras entram nos hashes da avaliação. Categorias são comparadas por item, inclusive em editais mistos.

## Operação no CRM

No catálogo, editar um produto salvo abre a ficha técnica documentada. Selecione PDF, use “Sugerir atributos do PDF”, confira os valores e páginas e marque a revisão. A extração sem IA procura rótulos explícitos de portas, PoE e capacidade; valores divergentes são indicados como conflitos. PDFs escaneados ou sem esses rótulos precisam de preenchimento manual. As sugestões não são salvas automaticamente nem recebem revisão automática.

Na aba Match do edital, executar por item ou para todo o edital. Os filtros exibem contadores recalculados por categoria do item. “Comparar este item” usa os filtros selecionados antes de avaliar e escolher candidatos. A comparação considera todos os candidatos selecionados antes de gravar as melhores dez sugestões; os contadores representam o catálogo, enquanto a lista contém as sugestões persistidas. A central Match executa lotes no modo rules usando a fila existente. Itens sem critérios estruturados retornam pendência e não acionam IA.

Mudanças nos requisitos, na ficha ou na versão das regras produzem technical_stale na leitura da avaliação. Confirmação desatualizada é bloqueada até reavaliação explícita. A matriz anterior permanece no histórico, disponível pelo botão na aba Match e por GET /api/crm/matches/{id}/technical-history. A seleção humana continua preservada.

## Código fonte e reprodução

O fonte do CRM foi recuperado em bid-buddy no commit 82384b47d245c557f78fa2686bb9c493641e9867, o mesmo usado pelos bundles originais. As alterações locais estão no submódulo e também em docs/crm-technical-match-source.patch. A .gitmodules foi recuperada para permitir inicialização em outro checkout.

Para reproduzir as alterações em um submódulo limpo nesse commit:

```sh
git -C bid-buddy apply ../docs/crm-technical-match-source.patch
npm ci --prefix bid-buddy
node scripts/sync-bid-buddy.mjs
npm ci --prefix frontend
npm run build --prefix frontend
```

O patch é necessário enquanto as alterações do submódulo não forem commitadas e publicadas no seu repositório. Não aplicar sobre o fonte local já alterado. Os bundles atualizados ficam em frontend/public/crm.

## Validação e limites

Testes selecionados do motor, V8, API isolada, ranking e export passaram; testes de componentes da aba Match passaram; builds de produção do CRM e frontend principal passaram. Os testes HTTP usam os corpos reais das rotas com dependências isoladas; não validam JWT real, PostgreSQL, Redis ou a VPS. A checagem TypeScript completa encontrou erros preexistentes em outras telas e utilitários; a build e os testes dos novos componentes passaram.

A extração automática é conservadora e exige revisão humana. Condições em texto livre não são interpretadas. Busca semântica e precedentes permanecem no caminho híbrido existente; a expansão da recuperação não foi implementada nesta etapa. A política documental é exigida para V8/export; o contrato nativo anterior mantém sua compatibilidade.

## Publicação da branch

A branch do repositório principal inclui os bundles e o patch integral do fonte do CRM. O gitlink permanece no commit público 82384b47d245c557f78fa2686bb9c493641e9867; aplicar o patch reproduz o fonte atualizado a partir dessa base. O fonte atualizado foi commitado localmente no submódulo, mas seu push ao repositório de terceiro foi rejeitado pela revisão automática por ausência de autorização confirmada para esse destino.
