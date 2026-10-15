# Plano de implementação — inteligência de mercado do RagMatch

Data: 09/10/2026. Base: `C:\Users\vish8\Downloads\deep-research-report.md` e inspeção do código desta cópia do projeto.

Situação atual: implementação e homologação do escopo **Docker local**, escolhido pelo usuário, registradas em [Aceite local](inteligencia-comercial-aceite-local.md). Bling permanece integração futura, conforme esclarecimento do usuário. As seções abaixo conservam o planejamento inicial e seus critérios; não significam homologação de produção ou disponibilidade de dados reais para ML.

Este documento apresenta o plano solicitado antes da implementação. As recomendações do relatório foram adaptadas ao código existente. Os números exemplificativos, trechos de SQL e datas do relatório não são dados medidos nem requisitos literais. Nenhuma alteração funcional, migration ou consulta à VPS foi executada nesta etapa.

## 1. Objetivo e ordem de entrega

Conectar demanda de licitações, catálogo, marcas, fornecedores, preços e resultados para apoiar compras e decisões comerciais no CRM. A implementação terá entregas verificáveis, nesta ordem:

1. Diagnóstico e contratos de dados.
2. Fundação analítica, histórico e carga interna do CRM.
3. Identidade de fornecedores, marcas e produtos, com revisão humana.
4. Ingestão incremental de Bling e PNCP; enriquecimento cadastral e índices.
5. Indicadores e painéis comerciais no CRM.
6. Melhoria do matching técnico e captura de feedback.
7. Modelos comerciais e previsões, conforme disponibilidade de dados.
8. Operação, monitoramento e homologação para produção.

O primeiro marco utilizável reúne diagnóstico, dados internos, qualidade, cobertura do catálogo e comparação dos preços registrados no CRM. A entrega completa acrescenta Supplier 360, marcas, mercado externo, integrações e modelos validados.

## 2. O que já existe e o que falta

| Componente | Evidência local | Consequência para implementação |
| --- | --- | --- |
| CRM operacional | `backend/app/crm/models.py` | Reutilizar catálogo, editais, itens, candidatos, revisões e resultados. |
| Catálogo | `CrmCatalogProduct` | Já tem marca, modelo, MPN, SKU, custo, fornecedor textual e embeddings. Acrescentar identidade de origem, GTIN e relações estruturadas. |
| Dados comerciais dos itens | `CrmNoticeProduct` | Já tem quantidade, unidade, custo, oferta, mínimo e referência unitária/total. Validar semântica antes de transformar. |
| Resultados por item | `CrmNoticeItemResult` | Já tem preço/quantidade vencedora e marca/modelo vencedor. Falta identidade canônica do concorrente. |
| Matching e avaliação | `backend/app/routers/crm.py`, `backend/app/services/match_eval_dataset.py` | Reaproveitar avaliações, labels humanos e calibragem. |
| Painel de demanda | `bid-buddy/src/pages/MarketIntelligence.tsx`, `bid-buddy/src/lib/market-intelligence.ts` | Evoluir a tela existente; os cálculos atuais ocorrem no navegador. |
| Transporte do CRM | `bid-buddy/src/integrations/supabase/client.ts` | O nome do cliente é Supabase, mas existe adaptação para a API do projeto. Usar o transporte autenticado existente. |
| Analytics atual | `backend/app/routers/analytics.py` | Mede sobretudo matching técnico; criar serviços e contratos específicos para métricas comerciais. |
| Bling | `backend/app/integrations/bling/` | OAuth e credenciais cifradas por tenant já existem. O cliente inspecionado está voltado a vendas/notas; faltam extratores analíticos. |
| PNCP | `backend/app/services/pncp_client.py`, `backend/app/routers/pncp.py` | Reutilizar cliente/radar; ampliar para atualizações, resultados por item e contratos. |
| Ingestão de licitações | `Tender`, `TenderSyncCheckpoint`, `backend/app/integrations/tenders/` | Reaproveitar abstrações e checkpoints quando compatíveis com as fontes analíticas. |
| Jobs | `backend/app/jobs/`, Docker Compose | Dramatiq/Redis e workers já existem. Separar trabalho analítico dos workers de OCR e IA. |
| MLOps | `backend/app/mlops/`, `mlops/scripts/` | Há tracking, avaliação, drift e promoção. Verificar versões e isolamento antes de ampliar. |
| Isolamento | `backend/app/db/session.py`, migrations RLS | Estender o contexto `app.current_tenant_id` às novas tabelas, jobs e consultas. |
| Transformações | Prefect comentado em `backend/requirements.txt`; nenhum projeto dbt encontrado na inspeção | Instalar e configurar em ambiente próprio do worker de dados, com versões testadas. |

Há alterações anteriores em `docker-compose.prod.yaml` e, dentro de `bid-buddy`, em `src/index.css` e `src/pages/MarketIntelligence.tsx`. Existem também alterações em dependências do frontend. A execução deve preservar esse trabalho e manter separados os arquivos desta iniciativa.

## 3. Decisões de arquitetura

- PostgreSQL e pgvector permanecem a base inicial. Os schemas `raw`, `staging`, `core` e `mart` organizam os dados analíticos.
- FastAPI serve indicadores e recomendações ao CRM. Agregações e exportações grandes passam a ser executadas no servidor, com filtros, paginação e limites.
- Um `worker-data` executa extração, transformação e atualização de indicadores. Prefect coordena flows; dbt transforma os dados. Não haverá duas rotinas independentes agendando a mesma carga.
- Alembic governa schemas, controle operacional, identidade editável e políticas de segurança. dbt governa modelos analíticos derivados. Cada relação tem um único responsável por sua definição.
- O CRM continua sendo a interface principal. Metabase será uma entrega complementar para exploração dos marts, com acesso somente de leitura e isolamento explícito por tenant.
- MLflow e Evidently serão reaproveitados após validar compatibilidade das versões instaladas. Bibliotecas analíticas ficam separadas das dependências necessárias ao atendimento HTTP.
- Cada fato preserva fonte, identidade externa, momento do evento e momento da ingestão. Identidade canônica nunca elimina o dado original.

As tabelas materializadas e agregações também precisam de proteção própria. Não se deve presumir que uma materialized view herda a proteção RLS das tabelas de origem. O desenho inicial prefere marts em tabelas com RLS; views e eventuais materialized views só serão expostas após teste explícito do isolamento.

## 4. Fase 1 — diagnóstico e contratos

### Trabalho

1. Inventariar tabelas, migrations, enums, campos e integrações efetivamente usados pelo CRM.
2. Criar diagnóstico por tenant: quantidade de registros, período histórico, duplicidades, preenchimento e disponibilidade de labels.
3. Reutilizar os endpoints existentes:
   - `/api/crm/matches/attached-products/ai-opportunities`;
   - `/api/crm/matches/evaluation-dataset`;
   - `/api/crm/catalog/embeddings/status`;
   - `/api/crm/matches/calibration-report`.
4. Mapear SKU, MPN, marca, GTIN, fornecedor, CNPJ, categorias, unidades e todas as modalidades de preço.
5. Verificar se `winning_price` e `unit_price` representam preço unitário nos fluxos de gravação; identificar casos legados ambíguos.
6. Documentar denominadores de participação, vitória, cobertura e margens; distinguir resultado por edital de resultado por item.
7. Definir contratos de API, política de datas e fixtures representativas para implementação.

### Entrega e aceite

Relatório de qualidade e prontidão, dicionário de dados e mapa origem→destino. Os números devem vir de medições do ambiente consultado. O banco local não representa automaticamente a VPS. Nenhum percentual do relatório será usado como resultado real.

## 5. Fase 2 — fundação analítica e carga do CRM

### Trabalho

1. Criar migrations aditivas para schemas, execuções de carga, checkpoints, registros raw, identidade e auditoria.
2. Registrar `tenant_id`, `source_system`, `source_entity`, `source_id`, `source_updated_at`, `ingested_at`, `batch_id`, hash e payload original.
3. Persistir revisões raw sem duplicar a mesma versão em reexecuções. Capturar correções, exclusões e desativações com semântica explícita.
4. Criar extrator interno do CRM e staging tipado. Para tabelas sem `updated_at`, usar hashes/snapshots ou eventos, sem fingir que `created_at` captura edições.
5. Criar os primeiros modelos canônicos: produto, categoria, marca, item de oportunidade, candidatos de matching, ofertas, resultados e observações de preço.
6. Usar valores monetários decimais nos novos fatos, com escala e arredondamento documentados; manter compatibilidade com os campos operacionais existentes.
7. Normalizar unidades e embalagens somente quando a conversão for conhecida. Valores incompatíveis ficam fora dos benchmarks, com motivo visível.
8. Implementar limites de carga, execução por tenant, bloqueio de concorrência e checkpoints transacionais. Avançar o checkpoint somente depois de persistir a etapa correspondente.
9. Configurar dbt com chave composta por tenant/origem/identidade e testes reais de unicidade. Usar sobreposição de janela para alterações tardias, sem depender apenas de `timestamp > max(timestamp)`.

### Entrega e aceite

Carga interna executável e reprocessável; repetir uma execução mantém os mesmos fatos atuais e totais, uma alteração produz histórico e atualiza os agregados, e uma falha permite retomada sem perda. Isolamento validado com dois tenants em PostgreSQL real.

## 6. Fase 3 — entidades e revisão humana

### Trabalho

1. Criar fornecedor canônico, aliases de marca, produto canônico e vínculo produto–fornecedor com custo, prazo e origem.
2. Acrescentar GTIN e identificação de concorrentes onde necessário, preservando campos legados e compatibilidade da importação.
3. Normalizar CNPJ numérico e alfanumérico, preservar zeros iniciais e validar dígitos verificadores. Não remover letras de identificadores empresariais.
4. Resolver fornecedores por CNPJ completo e identidade da fonte. Usar raiz somente como atributo de grupo empresarial, sem fundir filiais automaticamente.
5. Resolver produtos por GTIN validado, marca+MPN e SKU restrito à mesma fonte/tenant. Exigir contexto e compatibilidade para identidades ambíguas.
6. Registrar método, evidências, confiança, versão, usuário e data de cada resolução.
7. Criar fila de casos conflitantes com confirmação/rejeição e histórico das correções.
8. Reutilizar embeddings para sugerir pares após blocking; sugestões probabilísticas passam por limiares medidos e revisão quando necessário.

### Entrega e aceite

Casos com identificadores contraditórios não são unidos. Aliases são versionados, as correções são auditáveis e não cruzam tenants. A precisão de resoluções automáticas é medida em conjunto revisado antes de ativar esse comportamento.

## 7. Fase 4 — fontes externas e integrações

### Bling

- Ampliar o cliente existente para produtos, contatos/fornecedores, vínculos produto–fornecedor, compras, vendas, propostas e estoque conforme os escopos disponíveis.
- Implementar paginação, limites por conta, retries com backoff e persistência incremental. Renovação de tokens continua no servidor.
- Integrar webhooks disponíveis e reconciliação periódica. Recebimento é idempotente, autentica a origem e trata eventos duplicados e fora de ordem.
- Separar compra de fornecedor de entrega da empresa ao órgão: fulfillment do CRM não comprova OTIF do fornecedor.

### PNCP

- Capturar contratações por publicação e atualização; obter itens, resultados e contratos pelos recursos apropriados.
- Preservar identificadores completos, fornecedor vencedor, quantidades, valores, status e retificações.
- Não transformar valor total de contrato em preço unitário sem item e quantidade confiáveis.
- Separar universo observado de mercado total. Diferenciar previsão de compra, contratação, adjudicação e execução contratual.
- Usar status válidos para benchmarks e excluir resultados cancelados sem perder seu histórico.

### Cadastro e índices

- Enriquecer fornecedores/concorrentes com dados oficiais de CNPJ, com versão e data de referência.
- Integrar séries oficiais do IBGE e configurar o índice adequado ao domínio; preservar preços nominais e calcular preços reais com mês-base explícito.
- Manter carga cadastral limitada ao conjunto relevante ou a uma base consultável preparada, evitando baixar todo o cadastro nacional no atendimento da API.

### Entrega e aceite

Conectores testados com payloads oficiais representativos, cenários de paginação, 401, 429, falha parcial, alteração e cancelamento. Com credenciais disponíveis, realizar piloto controlado por tenant e comparar contagens/valores com a origem.

## 8. Fase 5 — indicadores e painéis

Criar rotas autenticadas de inteligência de mercado, com filtros comuns de período, categoria, UF, marca, fornecedor e fonte. Tela, ranking e exportação precisam usar o mesmo recorte. Preservar a semântica atual de data de cadastro; filtros por publicação/disputa serão opções identificadas.

| Painel | Indicadores e comportamento |
| --- | --- |
| Visão executiva | Demanda observada, pipeline, propostas, resultados, valor ganho, margem estimada e lacunas; detalhamento até os itens que compõem o número. |
| Qualidade e prontidão | Atualização por fonte, preenchimento, duplicidades, vínculos, unidade, preços, embeddings e labels; sinalização de dados insuficientes. |
| Assortment Gap | Cobertura por itens e por valor, oportunidades sem produto adequado e motivos de lacuna; separar não analisado, pendente de revisão e falha técnica confirmada. |
| Pricing | Custo/referência, oferta/referência, vencedor/referência, margem bruta estimada e distribuição de comparáveis; unidade, moeda, período e tamanho da amostra visíveis. |
| Brand Health | Marca solicitada, considerada pelo matching, ofertada e vencedora em métricas distintas; participação, cobertura e tendência em janelas comparáveis. |
| Supplier 360 | Produtos/categorias, gasto, preços, prazo P50/P90, fill rate, OTIF e resultados comerciais quando houver registros elegíveis; componentes visíveis. |
| Mercado PNCP | Volume observado, órgãos, regiões, vencedores, concentração e preços; vínculo com cobertura do catálogo quando houver identidade confiável. |

Regras transversais:

- Dado ausente não vira zero artificial, preço gratuito, perda ou falha de atendimento.
- Produto apenas vinculado ao item não prova atendimento técnico. A classificação usa revisão/veredito com origem conhecida.
- Itens sem avaliação permanecem em uma classe separada; lacunas confirmadas e lacunas possíveis não são somadas silenciosamente.
- Taxa de vitória usa resultados elegíveis e mostra o denominador; pendentes e cancelados recebem tratamento explícito.
- Margem bruta estimada não é lucro líquido. Frete, impostos e demais componentes entram somente se conhecidos.
- Benchmark exige equivalência técnica e comercial suficiente, além de categoria. Uma categoria ampla não torna produtos comparáveis.
- Dados do catálogo sugerido e marcas vencedoras não preenchem automaticamente marca demandada.
- Telas exibem estados vazio/insuficiente, horário de atualização e proveniência dos números.

### Entrega e aceite

Evolução da rota `/crm/inteligencia-mercado`, com páginas ou abas para os domínios. Totais conferidos em exemplos calculados manualmente e por consultas independentes; exportações iguais ao recorte exibido; paginação, acessibilidade e tempo de resposta medidos. Integração do build pelo fluxo já existente do Bid Buddy.

Metabase será conectado somente a dados analíticos autorizados. Para a versão escolhida, testar isolamento por roles, conexões ou espaços separados; não disponibilizar um dashboard multiempresa confiando apenas em filtro editável.

## 9. Fase 6 — matching técnico e feedback

1. Ampliar extração de atributos, números e unidades, mantendo evidências e as categorias específicas atuais.
2. Reaproveitar embeddings incrementais e recuperação híbrida; aplicar restrições técnicas explícitas antes da recomendação final.
3. Consolidar motivos de confirmação, rejeição e revisão. Estender feedback estruturado para fornecedor, oferta, decisão comercial e resultado.
4. Medir Recall@K, MRR, NDCG, macro-F1 e falsos aceites com os dados revisados.
5. Preservar split por edital e manter custo, oferta e resultado fora do matcher técnico.
6. Introduzir reranker/cross-encoder somente se o benchmark demonstrar ganho dentro do orçamento de latência.

### Entrega e aceite

Comparação reproduzível com o matcher atual; restrições técnicas não são anuladas por similaridade de texto; nenhum modelo novo é promovido apenas por melhorar a média enquanto aumenta falsos aceites.

## 10. Fase 7 — ML comercial e previsão

1. Construir features com data de disponibilidade e versões de dataset/schema.
2. Implementar verificação de prontidão: volume de labels, diversidade, classes, histórico temporal, sazonalidade e qualidade. Definir exigências por caso de uso a partir do diagnóstico.
3. Criar baselines explicáveis para bid/no-bid, probabilidade de vitória e risco de atraso. Comparar XGBoost quando houver base suficiente.
4. Usar validação temporal e por edital. Preço vencedor e resultado futuro não entram nas features de decisão.
5. Avaliar calibração, PR-AUC, Brier/log loss e utilidade comercial. Mostrar evidências e motivo da recomendação ao usuário.
6. Para demanda e preços, comparar previsão simples, mediana móvel e modelos sazonais quando o histórico permitir; medir erro e intervalos.
7. Criar segmentação e redundância do catálogo e alertas de preço com avaliação humana.
8. Registrar modelos no MLflow e testar recomendações em modo observação antes de habilitá-las no CRM.

### Entrega e aceite

Pipeline de treino e avaliação reproduzível, relatório de prontidão e comparação com baseline. Se os dados forem insuficientes, entregar coleta de feedback e regras identificadas como regras; a interface informa indisponibilidade de probabilidade/modelo. Não apresentar valores inventados como previsão treinada.

## 11. Fase 8 — operação e homologação

- Consolidar `worker-data`, Prefect, dbt e eventual Metabase em configuração Docker separada por perfil/serviço, com versões fixadas e recursos limitados.
- Medir duração de cargas, atraso por fonte, erros, conflitos, qualidade e desempenho de API; criar alertas acionáveis.
- Separar histórico de monitoramento por tenant. Verificar os arquivos locais usados pelo monitor de drift antes de ampliar seu uso.
- Validar compatibilidade de Evidently/MLflow e modernizar APIs de promoção conforme a versão selecionada.
- Usar degradação de desempenho e labels como evidência para retreino; drift isolado não dispara promoção automática.
- Implementar gates de qualidade, regressão, segurança e modelo no CI; registrar SHA, versão de dados, features e modelo.
- Documentar instalação, reprocessamento, exclusões, backups, recuperação e rollback. Desativar a funcionalidade por configuração é a primeira opção de rollback; preservar o histórico coletado.
- Preparar artefatos e roteiro de homologação antes de aplicar migrations e ativar integrações no ambiente de produção.

### Entrega e aceite

Fluxo ponta a ponta em ambiente de homologação, falha e retomada demonstradas, teste de dois tenants e carga representativa. Migrations validadas a partir da versão real do banco. APIs antigas, matching e CRM permanecem funcionais.

## 12. Organização da implementação

Locais propostos para código novo:

| Área | Local |
| --- | --- |
| Contratos e semântica | `docs/data-contracts/` |
| Serviços de diagnóstico, identidade e indicadores | `backend/app/market_intelligence/` |
| Rotas comerciais | `backend/app/routers/market_intelligence.py` |
| Migrations | `backend/alembic/versions/` |
| Flows e extratores | `analytics/flows/`, com reaproveitamento dos clientes existentes |
| Projeto dbt | `analytics/dbt/` |
| Dependências do worker | `analytics/requirements.txt` e imagem própria |
| Treino e avaliação | `mlops/`, reaproveitando scripts existentes |
| Telas e transporte | `bid-buddy/src/pages/`, `bid-buddy/src/lib/` |
| Verificações reais de banco | `tests/integration/` |
| Runbooks | `docs/market-intelligence/` |

A implementação será dividida em mudanças pequenas: diagnóstico; schemas/carga CRM; identidade; Bling; PNCP; marts/APIs; telas; matching; modelos; operação. Cada mudança inclui validação proporcional ao comportamento introduzido.

## 13. Estratégia de validação

1. Testes unitários de contratos, normalização, identificadores, classificação de cobertura, cálculo de métricas e comparabilidade de preços.
2. Testes em PostgreSQL com migrations e RLS reais: duas empresas, mesma identidade externa, jobs e consultas sob contexto correto, correções e retomadas.
3. dbt: unicidade, campos obrigatórios, relacionamentos, valores aceitos, reconciliação e atualização por fonte.
4. Conectores: fixtures de payloads públicos, limites, paginação, tokens, duplicidades, retificações e cancelamentos; testes live somente com configuração disponível.
5. Frontend: filtros, denominadores, detalhes, estados de erro/ausência, revisão humana e exportações; testes e build do Bid Buddy e do frontend integrado.
6. Modelos: comparação com baseline, separação temporal/por edital, controle de vazamento e decisão de promoção documentada.

O `tests/conftest.py` atual substitui SQLAlchemy e outras dependências por mocks. Portanto, passar nos testes unitários existentes não comprova migrations, RLS, SQL analítico ou funcionamento dos modelos. A suíte de integração terá configuração que carregue dependências reais.

## 14. Dependências e sequência prática

| Dependência | Trabalho que ela libera |
| --- | --- |
| Diagnóstico do banco e do período histórico | Definição dos backfills e prontidão de modelos. |
| Conexão Bling por tenant e escopos necessários | Piloto de compras, fornecedores, vendas e estoque. |
| Histórico de compra com datas e quantidades | OTIF, fill rate e lead time de fornecedor. |
| Resultados por item e identidade do vencedor | Win rate, Brand Award Share e concorrentes. |
| Equivalência de produto/unidade | Benchmark confiável de preço. |
| Labels humanos e período suficiente | Ranking supervisionado, probabilidades e forecasts. |
| Ambiente de homologação com PostgreSQL | Aceite de migrations, isolamento e desempenho. |

Essas dependências não impedem criar código, fixtures, diagnóstico e interfaces. Impedem declarar validada uma integração live ou treinar/promover um modelo sem evidência.

A ordem de execução prioriza o primeiro marco interno antes de fontes externas e ML. Os prazos do relatório são uma estimativa de programa com equipe; não são promessa de calendário para esta execução. O cronograma será refinado após a Fase 1, com marcos de entrega e dependências medidos.

## 15. Ajustes técnicos ao relatório e referências oficiais

1. **CNPJ alfanumérico:** aceitar o formato já implantado em 2026. O cliente PNCP atual usa expressão regular de 14 dígitos e remove caracteres não numéricos no filtro; ambos entram na revisão. [Receita Federal](https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/acoes-e-programas/programas-e-atividades/cnpj-alfanumerico).
2. **Bling:** respeitar limites por conta, intervalos de consulta e processamento de webhooks. A configuração de produção será baseada na documentação vigente. [Limites](https://developer.bling.com.br/limites) e [webhooks](https://developer.bling.com.br/webhooks).
3. **PNCP:** consultar publicações e atualizações e distinguir resultados/contratos. [API de consultas](https://pncp.gov.br/api/consulta/swagger-ui/index.html) e [manual de integração](https://pncp.gov.br/manual/pt-br/latest/singlehtml/).
4. **dbt:** chave incremental não substitui teste de unicidade nem resolve sozinha mudanças tardias/exclusões. [Modelos incrementais](https://docs.getdbt.com/docs/build/incremental-models).

## 16. Critério de conclusão da iniciativa

A implementação completa será considerada entregue quando os dados internos e as fontes externas configuradas alimentarem entidades e fatos auditáveis; os painéis tiverem métricas reconciliadas e isolamento comprovado; os ciclos de revisão humana estiverem operacionais; e os pipelines de matching/modelos, monitoramento e homologação tiverem validação reproduzível.

Quando um modelo ou indicador depender de dados ainda inexistentes, a entrega deve conter diagnóstico, coleta e estado explícito de insuficiência. Isso não equivale a declarar o modelo validado. O acompanhamento registrará separadamente código entregue, integração homologada e modelo habilitado.

## 17. Avanço validado em 09/10/2026

As fases 7 e 8 receberam novas entregas: comparação das previsões com mediana móvel de três meses, faixa histórica calibrada antes dos seis meses de comparação, versão do conjunto observado e apresentação dos resultados no painel. Séries de demanda permanecem separadas por fonte; preços exigem produto, unidade, moeda e UF comparáveis. São necessários 24 meses consecutivos para previsão e pelo menos 12 meses anteriores ao período de comparação para a faixa. A cobertura nominal não constitui garantia de cobertura futura.

O monitoramento agora mede, por empresa e fonte, contagens e taxa de falha, duração P50/P95, espera na fila, idade da última carga e alertas de atraso ou falha. A fila considera também pendências antigas. As métricas ficam disponíveis em `/crm/market-intelligence/operations`, no snapshot de qualidade e na aba **Cargas e modelos**.

A homologação local usou o Docker isolado, as duas contas fictícias, o proxy do portal e PostgreSQL com conta restrita. Login, cargas CRM, consulta operacional, jobs de qualidade/previsão e tela em Edge headless foram aprovados. O demo informa corretamente histórico insuficiente; não foi inserido histórico artificial para habilitar previsão. A homologação das fontes externas autenticadas e a habilitação de modelos com dados reais continuam dependentes das conexões e do histórico descritos na seção 14.

## 18. Ampliação do dashboard CRM e apresentação comercial

Plano executado: (1) incorporar demanda e cobertura ao dashboard principal do CRM, (2) disponibilizar predição em uma área dedicada, (3) preparar relatórios de demanda por fornecedor para negociação, (4) validar filtros, exportações, concorrência e processamento no Docker local.

O dashboard principal agora apresenta os indicadores analíticos internos e permite abrir o explorador sem sair da página. Há atalhos para predição e apresentação ao fornecedor, também acessíveis pela seção de inteligência. Erros operacionais e analíticos são visíveis, com nova tentativa; valor adjudicado deixou de ser descrito como faturamento.

A aba **Predição** permite avaliar demanda ou preço, visualizar estimativas por grupos comparáveis, conferir erro, mês previsto, faixa e requisitos de histórico e exportar a avaliação. Fonte, moeda e unidade permanecem separadas no gráfico. A seleção do modelo persiste durante recargas. Solicitações pendentes e falhas são exibidas separadamente da última avaliação concluída.

A aba **Apresentar ao fornecedor** aplica o recorte comercial, a origem, o fornecedor e a busca. Mostra apenas demanda observada de produtos vinculados ao fornecedor escolhido. Exporta CSV e apresentação HTML imprimível em PDF, com referências, amostras, período e cenário hipotético. A lista explícita de campos exclui custos internos, margens, feedback e IDs. O relatório não transforma referências ou cenários em compromissos de compra ou previsões estatísticas.

## 19. Acompanhamento das negociações

Incremento posterior ao planejamento de compras: indicadores de solicitações sem resposta e com escolha, propostas vencidas ou vencendo em até sete dias e condições comerciais não informadas. Agregações abrangem a empresa inteira, independentemente da página e dos filtros de demanda. Cada fornecedor usa a identidade normalizada; o resumo conta propostas e solicitações respondidas, sem inferir compras ou desempenho de entrega.

Os indicadores filtram a lista de solicitações; estado, fornecedor com proposta e busca por produto/referência têm filtros próprios. Preço unitário, unidade, referência e data da proposta aparecem na comparação. O calendário de validade usa Brasília, e versões/pendências sobrepostas são identificadas na interface.


## 20. Composição de propostas e relatório interno

Incremento sobre o acompanhamento: separar produtos, frete e impostos adicionais, calcular diferenças somente entre propostas elegíveis da mesma solicitação e gerar relatório interno com evidências/histórico. Decimais preservam a comparação; ausência de condição não vira zero. Diferenças não são declaradas como economia realizada. Exportação interna fica explicitamente separada da solicitação para fornecedor.
