# CRM Design System - Plano de Execucao do Redesign

## Objetivo

Este arquivo e o checklist operacional do redesign do CRM.

Ele deve ser usado para acompanhar a implementacao sem precisar reconstruir o contexto pelo historico da conversa ou reler todos os documentos do design system.

## Status atual

Branch do repositorio principal:

```text
codex/crm-design-system-layout
```

Ultimo commit conhecido no repositorio principal:

```text
b6cb883
```

Branch do CRM fonte:

```text
codex/crm-layout-redesign
```

Ultimo commit conhecido no CRM fonte:

```text
853d705
```

Ambiente de validacao:

```text
http://127.0.0.1:8080/crm/editais/notice-1?preview=1
```

Fluxo de implementacao:

```text
1. Alterar fonte em bid-buddy
2. Rodar npx tsc --noEmit em bid-buddy
3. Rodar npm run build:crm em frontend
4. Validar no preview /crm
5. Commitar bid-buddy
6. Commitar repositorio principal com o gitlink e build sincronizado
```

## Mudancas ja realizadas nesta conversa

### Funcionais do CRM

- [x] Padronizacao de datas nos cards de edital em formato `DD/MM/YYYY`.
- [x] Exibicao de `Sem data` quando o edital nao possui data cadastrada.
- [x] Data exibida tambem nas etapas a partir de julgamento, quando houver data cadastrada.
- [x] Cards de edital em etapas de julgamento em diante podem ser movimentados pelo pipeline.
- [x] Avanco de etapa dentro do edital funciona tambem para etapas de julgamento em diante.
- [x] Nomenclatura alinhada: o que aparecia como "processo" no card foi tratado como edital/oportunidade do funil.
- [x] Valor total de referencia por item adicionado no detalhe do edital.
- [x] Valor total de referencia do item calculado como valor de referencia unitario vezes quantidade, quando nao houver total explicito.
- [x] Valor total do item exposto na visualizacao dos itens.
- [x] Calendario ajustado para abrir edital em popup/modal ao clicar no edital.
- [x] Popup do calendario passou a ter opcao de abrir o edital em nova janela.
- [x] Fluxo de calendario preserva o contexto da data/lista lateral ao consultar um edital.

### Documentacao e direcao de produto

- [x] Analise da estrutura geral do CRM.
- [x] Identificacao de pontas soltas, incongruencias e informacoes faltantes.
- [x] Definicao do usuario principal: analista de editais de licitacao.
- [x] Definicao do objetivo operacional: funil de vendas para editais vindos do analisador.
- [x] Definicao das informacoes indispensaveis do card/detalhe: data do pregao, portal, municipio, resumo dos itens, orgao, alertas de risco, lista de itens, lote, preco dos itens, preco total e documentos pendentes.
- [x] Priorizacao definida como manual inicialmente, com possibilidade futura de ranking por estrelas.
- [x] Definicao de alertas fortes: data vencida, pregao nas proximas 24h, documento sem assinatura, analise tecnica atrasada, item sem produto vinculado, proposta nao cadastrada antes da disputa e tarefa com prazo expirando.
- [x] Definicao de tarefas e notificacoes como conceitos separados: tarefas atribuidas a pessoas e notificacoes geradas por tarefas ou eventos relevantes.
- [x] Decisao de manter modo claro e modo escuro.
- [x] Decisao visual registrada: modo claro precisa ter mais presenca; modo escuro precisa ser menos pesado.
- [x] Decisao de manter "Suspensos" como nomenclatura do setor.
- [x] Decisao de manter pipeline e calendario como duas visualizacoes dos mesmos dados.
- [x] Decisao de tratar ganhos e perdidos separados por abrirem caminho para modulo futuro de pos-venda/atas/pedidos/faturamento.
- [x] Criacao dos documentos de design system:
  - `01-estrategico-conceitual.md`
  - `02-tecnico-implementavel.md`
  - `03-guia-consolidado.md`
  - `04-manual-visual-layout.md`
  - `05-especificacao-implementacao-layout.md`
- [x] Revisao registrada: etapas atuais do pipeline devem ser preservadas; atividades intermediarias podem ser acoes, status, checklists, tarefas ou alertas.
- [x] Branch de trabalho separada criada para o redesign, evitando interferir diretamente na `main`.

### Redesign ja implementado

- [x] Aba Informacoes redesenhada como ficha operacional.
- [x] Edicao campo a campo por icone, sem modo geral de edicao.
- [x] Icones de edicao discretos, aparecendo por hover/foco.
- [x] Valor total do item mantido na parte inferior dos cards de item.
- [x] Acoes do edital reorganizadas no topo.
- [x] "Suspender edital" movido para o menu de tres pontos.
- [x] "Enviar para pos-disputa" movido para o menu de tres pontos.
- [x] "Abrir tabela de disputa" com icone relacionado a disputa.
- [x] Analise tecnica com icone de ferramenta.
- [x] Aba Itens reorganizada por lote.
- [x] Itens em disputa aparecem primeiro.
- [x] Itens retirados ficam em bloco recolhivel.
- [x] Lote totalmente retirado aparece como linha compacta.
- [x] Item retirado mostra contexto suficiente para reabertura.
- [x] Alerta para item em disputa sem produto vinculado.
- [x] Correcao de rotulo duplicado de lote.
- [x] Cards do pipeline reorganizados em blocos compactos.
- [x] Data do card do pipeline mantida em `DD/MM/YYYY` e com mais destaque visual.
- [x] Contexto do edital agrupado no card: portal, cidade, orgao, valor e documentacao.
- [x] Resumo de itens do card transformado em bloco compacto.
- [x] Alertas fortes separados das informacoes comuns.
- [x] Indicador discreto para pendencias anteriores no topo do card.
- [x] Icones e nomenclaturas do card alinhados com a pagina do edital: agendamento/data, documentacao, analise tecnica, orgao e numero do pregao/licitacao.
- [x] Pipeline ajustado para abrir edital em popup sem sair da tela.
- [x] Popup do pipeline inclui opcao de abrir edital em nova janela.
- [x] Popup do pipeline carrega a pagina do edital em modo embutido, sem menu lateral esquerdo.
- [x] Popup do calendario tambem carrega a pagina do edital em modo embutido, sem menu lateral esquerdo.
- [x] Modo embutido do edital remove o botao "Voltar para o pipeline" para evitar navegacao interna no popup.
- [x] Menu de acoes do card alinhado com a pagina do edital: abrir agendamento do edital, abrir tabela de disputa, avancar etapa, marcar documentacao analisada, marcar analise tecnica realizada, enviar para pos-disputa, suspender edital, descartar, reabrir e excluir edital.

## Pausado para revisao posterior

- [ ] Aba Documentacao como checklist + biblioteca.

Motivo:

- a primeira proposta visual nao ficou adequada;
- antes de redesenhar novamente, e necessario detalhar melhor as regras de negocio e o fluxo real de documentacao.

## Proximos passos

### 1. Calendario com popup de edital

Objetivo:

- manter a experiencia ja iniciada no calendario: clicar no edital deve abrir popup, nao exigir selecionar e depois abrir.

Implementar:

- clique direto no edital abre popup;
- botao de abrir em nova janela dentro do popup;
- lista lateral fica mais limpa;
- cards da lista mostram data e contexto.

Criterios de aceite:

- usuario nao perde a data selecionada;
- fluxo fica mais direto;
- calendario e pipeline usam comportamento parecido para abrir edital.

### 2. Revisao de temas claro e escuro

Objetivo:

- deixar o modo claro menos insosso e o modo escuro menos pesado.

Implementar:

- revisar tokens de fundo, card, borda, texto secundario e acento;
- manter contraste adequado;
- evitar paleta monotematica;
- preservar leitura durante uso prolongado.

Criterios de aceite:

- modo claro tem mais presenca visual;
- modo escuro tem camadas mais suaves;
- cores semanticas continuam reconheciveis;
- o CRM parece mais agradavel para uso diario.

### 3. Revisao visual geral

Objetivo:

- eliminar incongruencias deixadas pelas fases anteriores.

Verificar:

- tamanhos de fonte;
- espacamentos;
- radius;
- uso de cards;
- botoes com icones;
- tooltips;
- estados vazios;
- responsividade basica.

Criterios de aceite:

- telas principais parecem pertencer ao mesmo sistema;
- informacoes importantes continuam acessiveis;
- interface fica mais fluida e organizada.

## Regras para atualizar este arquivo

- Marcar um item como concluido somente depois de validar no preview.
- Registrar decisoes novas que alterem a direcao do redesign.
- Manter os proximos passos em ordem operacional.
- Nao transformar este arquivo em documento conceitual longo; ele deve continuar pratico.

## Referencias internas

- `docs/crm-design-system/01-estrategico-conceitual.md`
- `docs/crm-design-system/02-tecnico-implementavel.md`
- `docs/crm-design-system/03-guia-consolidado.md`
- `docs/crm-design-system/04-manual-visual-layout.md`
- `docs/crm-design-system/05-especificacao-implementacao-layout.md`
