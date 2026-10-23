# Aceite local — inteligência comercial

Data: 09/10/2026. Escopo confirmado pelo usuário: concluir no Docker local.
Bling é integração futura; não foi homologado nem ativado.

## Entrega por fase

| Fase do plano | Entrega local | Limites de habilitação |
| --- | --- | --- |
| 1. Diagnóstico e contratos | Diagnóstico do banco conectado, semântica de preços, cobertura, origem e amostras | Os dados fictícios não representam a qualidade do banco de produção. |
| 2. Fundação e CRM | Ledger raw/core/mart, histórico de revisão, snapshots reconciliados, fila durável e RLS | Migration de produção exige homologação e backup próprios. |
| 3. Identidade | CNPJ/GTIN/MPN, blocking, aliases auditáveis e revisão humana de conflitos | Correspondências probabilísticas exigem revisão; similaridade não é equivalência técnica. |
| 4. Fontes | Contratos e extratores públicos, importação administrativa, adaptador Bling de leitura | Bling planejado e desabilitado por padrão. Fontes externas autenticadas não foram homologadas. |
| 5. Indicadores | Cobertura, Supplier 360, marcas solicitadas/ofertadas/vencedoras, evolução mensal, margens e benchmarks | KPIs de entrega dependem de recebimentos reais. Produto desconhecido e referência ausente permanecem explícitos. |
| 6. Matching e feedback | Regras estruturadas, restrições técnicas e decisões humanas com snapshots | Reranker avançado depende de ganho comprovado no benchmark e latência aceitável. |
| 7. Modelos | Prontidão, baseline comercial, challenger, avaliação temporal, drivers e previsões com faixa histórica | Demo sem labels/histórico suficiente não habilita probabilidade ou previsão fictícia. |
| 8. Operação | Docker, Prefect/dbt, observabilidade, gates de CI, controle de desativação, backup e restauração ensaiados | CI remoto e produção não foram executados; Metabase exige provisionamento próprio. |

## Dashboard interativo

A aba padrão **Dashboard interativo** usa os dados da empresa autenticada.
Inspirado na interação do [relatório enviado pelo usuário](https://unidas-pesados-relatorio.vercel.app/#cenarios), oferece:

- **Produtos × demanda:** ranking clicável, busca, fonte, fornecedor relacionado, medida, referências conhecidas e atendimento confirmado.
- **Fornecedores × produtos:** vínculos atuais do catálogo, custo, prazo cadastrado e navegação para demanda.
- **Simular cenários:** variação hipotética de demanda e meta de cobertura por valor, recalculadas imediatamente. É aritmética sobre referências observadas, sem previsão causal, receita garantida ou confirmação técnica automática.
- **Detalhamento:** registros da origem com identidade, data, quantidade e unidade; paginação mantém o recorte.
- **Apresentação:** tela cheia para mostrar a análise, mantendo autenticação e seleção. CSV reproduz busca e seleção do explorador, protege fórmulas e preserva valores ausentes.
- **Responsividade:** versão móvel com eixo compacto, tabelas com rolagem e alternativas em botões para selecionar produtos.

Fontes permanecem separadas para evitar somar processos que também estejam registrados no CRM. Quantidades são agregadas somente com unidade única conhecida. Catálogo e vínculos de fornecedor representam o estado cadastral atual; o período filtra os fatos de demanda. Produtos sem demanda e demanda sem produto identificado ficam visíveis.

## Evidências reproduzíveis

- 65 testes analíticos aprovados, incluindo 3 testes com migration e RLS reais em PostgreSQL 16 novo e descartável.
- 52 testes do matching técnico aprovados.
- 63 testes frontend aprovados, TypeScript global, lint dos componentes e build integrado aprovados.
- Docker integrado: login real das duas contas, cargas processadas pelo worker, relatórios, consulta operacional e CSV. Identidades dos produtos do explorador não se cruzam entre empresas.
- Edge headless: login, gráfico e seleção de produto, detalhamento, fornecedor, alteração de cenário, exportação, apresentação e visualização móvel.
- Backup consistente via `pg_export_snapshot` e `pg_dump`, restauração em banco novo, conferência por empresa de contagens/valores das tabelas analíticas, versão Alembic e FORCE RLS. O banco temporário de restauração foi removido; dumps e manifests ficaram em `analytics/.validation/backups/`.
- Ensaio com 5.000 fatos temporários: cinco execuções; mediana de 0,24 s e maior tempo de 0,27 s para consulta PostgreSQL, cálculo e serialização. A transação foi revertida. Não mede rede, renderização nem escala de produção.

Reproduzir com os comandos do runbook `docs/inteligencia-comercial-operacao.md`.
O navegador integrado não foi automatizado; os testes visuais usaram Playwright com Edge.

## Resultado operacional

O ambiente local permanece disponível em `http://127.0.0.1:3088/login`.
Contas fictícias: `demo1@example.com` e `demo2@example.com`, senha `DockerTeste@2026`.
Após entrar, abrir `/crm/inteligencia-comercial`.

Esta entrega conclui a implementação e homologação do escopo local. Não declara integração Bling completa, implantação de produção ou modelos validados sem dados reais.

## Complemento — nomes de fornecedores

Nomes de fornecedores agora têm exibição padronizada, aliases originais e identidade estável. Variações de caixa, acentos, espaços e pontuação são normalizadas; CNPJ completo igual consolida a empresa, enquanto CNPJs diferentes e nomes apenas semelhantes permanecem separados ou aguardam revisão. A confirmação humana remapeia também vínculos de produtos e desativa entidades substituídas sem apagar o histórico. Uma reimportação não recria o fornecedor substituído.

O administrador pode usar **Normalizar fornecedores existentes** em **Revisão e feedback**; a carga CRM também executa a normalização. Este complemento passou pelos 68 testes analíticos sem a fixture PostgreSQL descartável e 63 testes frontend. O Docker confirmou a operação nas duas contas e uma transação temporária com consolidação real em PostgreSQL, incluindo constraints compostas, deduplicação de vínculos, idempotência e rollback.

## Complemento — dashboard CRM, predição e relatório para fornecedor

O dashboard principal `/crm/` incorpora a visão analítica interna, exploração de produtos/fornecedores e atalhos para as abas **Predição** e **Apresentar ao fornecedor**. Os erros de consulta deixam de aparecer como indicadores zerados. A inteligência de atributos também oferece os atalhos. O valor ganho é identificado como adjudicado, sem descrevê-lo como faturamento recebido.

As previsões têm área dedicada para solicitação, acompanhamento da fila e consulta da última avaliação concluída. O gráfico separa fontes de demanda, moedas e unidades; a tabela informa requisitos, método, erro, faixa e mês estimado. A seleção de demanda/preço persiste durante recargas. As contas demo não têm histórico para habilitar previsões; as duas avaliações reais feitas pelo worker retornaram insuficiência corretamente.

O relatório para fornecedor aplica o recorte, seleciona produtos relacionados e exporta uma lista explícita de dados observados, sem custos internos, margens, feedback ou IDs. O cenário de negociação permanece hipotético. O HTML é autônomo, escapado e imprimível; o teste abriu o arquivo em Edge e gerou PDF. O CSV contém o recorte inteiro. Dados sem referência ou unidade comparável permanecem indisponíveis.

Validação deste complemento: **69 testes analíticos** (sem repetir a fixture PostgreSQL descartável), **71 testes frontend**, TypeScript, lint e build integrado. O navegador real confirmou cockpit, seleção de produtos, escolha do fornecedor, cenário de 50%, HTML com referências reconciliadas, PDF e avaliação dos dois modelos pelo worker. Um teste adicional em PostgreSQL com role restrita executou **oito bootstraps simultâneos**, criando apenas um checklist completo. A empresa temporária e seus checklists foram removidos; as contas demo foram preservadas.

Evidências locais ficam em `analytics/.validation/`: `crm-commercial-cockpit.png`, `supplier-demand-workspace.png`, `supplier-demand-presentation.html`, `supplier-demand-presentation.pdf`, `forecast-workspace.png` e `forecast-workspace-mobile.png`. São dados fictícios, sem homologação de integração Bling ou produção.

## Complemento — planejamento de compras e negociação

A versão `commercial-20261009-v2` adiciona planejamento com saldo físico e reservado documentados, solicitação de cotação, propostas de fornecedores vinculados, comparação do custo total e escolha com justificativa/histórico. O cálculo só usa unidade compatível e saldo de até sete dias; quantidade incompleta ou saldo ausente exigem revisão. Solicitações preservam a fotografia de demanda que as originou. Nenhuma seleção gera pedido ou reserva.

Validação: **85 testes analíticos**, incluindo PostgreSQL 16 com FORCE RLS e referências compostas, e **72 testes frontend**; TypeScript, lint e build aprovados. Docker executou API, frontend e worker v2 sem montagens do código. Login/cargas/relatórios/CSV das duas contas, cockpit, apresentação/cenário e processamento das duas avaliações de previsão passaram.

Edge confirmou demanda 10 UN, físico 3 UN, reservado 1 UN e 8 UN para avaliar; propostas 4050/4150 BRL; destaque da proposta com menor total e condições documentadas; seleção com justificativa persistente após recarga; exportação da solicitação HTML/PDF sem estoque, propostas concorrentes e histórico interno; isolamento por empresa. O teste também gerou capturas desktop e móvel.

A consolidação de fornecedores atualiza as cotações e conserva o nome capturado na evidência. Um saldo mais antigo não substitui uma conferência recente. Migração aplicada no Docker local: `20261009_02`. Evidências: `analytics/.validation/procurement-desktop.png`, `procurement-mobile.png`, `procurement-inquiry.html` e `procurement-inquiry.pdf`. Guia: [planejamento de compras e cotações](planejamento-compras-cotacoes.md).

O ensaio de backup desta versão restaurou um banco independente, conferiu contagens/valores, migration `20261009_02` e FORCE RLS, incluindo 2 solicitações e 4 propostas fictícias da empresa demo 1. A empresa demo 2 continuou isolada. Banco de restauração removido; dump/manifesto mantidos em `analytics/.validation/backups/market-local-0d80dc88f637.*`.

Publicação concluída no Docker Hub: `commercial-20261009-v2` para API, frontend, worker e MLflow compatível. Digests remotos conferidos. [Notas e hashes da release](releases/commercial-20261009-v2.md).

## Complemento — acompanhamento das negociações

88 testes analíticos, incluindo as agregações em PostgreSQL com conta restrita e RLS, e 74 testes frontend aprovados. Indicadores usam o histórico inteiro da empresa, com filtros próprios para solicitações; fornecedores usam a identidade normalizada. Validade segue o calendário de Brasília. Comparação mostra preço unitário/unidade, referência e data do registro.

A release v3 empacotada passou por login, cargas CRM, relatório, CSV e isolamento das duas empresas. Edge confirmou solicitações sem proposta, propostas com condições não informadas, filtro por fornecedor, busca literal, referência/preço unitário e capturas desktop/móvel. Fluxo de estoque/cotações, escolha persistente, exportação HTML/PDF, cockpit, cenário para fornecedor e avaliações de demanda/preço continuaram aprovados.

Evidências: `analytics/.validation/negotiations-desktop.png` e `negotiations-mobile.png`. Migração permanece `20261009_02`; não há mudança de formato das tabelas ou do backup.

Release `commercial-20261009-v3` publicada no Docker Hub, com digests dos quatro componentes conferidos; demo executando a versão final sem montagens do código. Layout desktop/móvel passou pelo teste de ausência de transbordamento horizontal. [Notas e hashes](releases/commercial-20261009-v3.md).

## Complemento — composição de custos e relatório interno

85 testes analíticos e 76 testes frontend aprovados, com casos de empates, valores exatos, propostas incompletas/vencidas e conteúdo escapado. Testes PostgreSQL descartáveis da v3 permanecem válidos para as consultas e schema, que não foram alterados neste incremento. TypeScript, lint e build aprovados.

A release v4 sem montagens passou em login, cargas, relatórios e isolamento das duas empresas. Edge confirmou 4000 + 40 + 10 = 4050 BRL, diferença 100 BRL entre propostas elegíveis, evidência/histórico e geração do relatório interno em HTML/PDF A4 paisagem. Fluxos anteriores de estoque, escolha persistente, solicitação compartilhável e acompanhamento mantiveram aprovação. Evidências em `analytics/.validation/negotiation-internal-report.{html,pdf,png}`.

Release `commercial-20261009-v4` publicada no Docker Hub, com os quatro digests remotos verificados e as imagens finais executadas no demo sem montagens. [Notas e hashes](releases/commercial-20261009-v4.md).
