# Inteligência comercial: implementação e operação

O plano original está em `plano-implementacao-inteligencia-mercado.md`. Esta entrega acrescenta a camada analítica, conectores, API, painel e rotinas de avaliação. A ativação no banco e a homologação das contas externas são etapas de ambiente: não foram executadas na produção nesta sessão.

## Componentes entregues

| Área | Implementação |
|---|---|
| Diagnóstico | API `/api/crm/market-intelligence/diagnostic`, preenchimento e extensão temporal do CRM conectado |
| Warehouse | Migration `20261009_01`, schemas raw/staging/core/mart, fatos tipados, proveniência e revisões monotônicas de payload |
| Reconciliação | Snapshot transacional do CRM; dimensões, compras, vendas, propostas e estoque Bling; publicações, atualizações e resultados PNCP; séries IBGE; importação normalizada CNPJ/manual |
| Identidade | CNPJ numérico/alfanumérico com dígitos verificadores; GTIN validado; marca+MPN; vínculo de origem; nomes similares passam por revisão; alias versionado |
| Comercial | Cobertura e lacunas, Supplier 360, marcas por origem, ofertas/margem bruta, preços comparáveis, resultados observados PNCP e qualidade |
| Preços reais | Deflação opcional por série de nível explicitamente selecionada, mês-base e mês do evento; taxas percentuais não são tratadas como índices |
| Modelos | Logística comercial e challenger XGBoost, baselines técnicos/identidade revisados, forecast sazonal/naive, clusters exploratórios e anomalias IQR |
| MLOps | Versões de features/dataset, métricas e gates de prontidão/performance, MLflow opcional, snapshots de qualidade e drift KS/Evidently |
| Orquestração | Fila persistida por tenant, worker dedicado, Prefect para agendamento, dbt em ambiente separado, checkpoints após commit e recuperação de jobs interrompidos |
| Interface | Rota `/inteligencia-comercial`, filtros aplicados, tabelas paginadas, CSV, revisão de identidade, alias, feedback, cargas e prontidão |
| Segurança | Predicados explícitos de tenant, FORCE RLS, RBAC, webhook HMAC, CSV sem fórmulas executáveis, BI com views fixas por empresa |

## Instalação

1. Fazer backup e executar o pipeline de migrações existente com a conta administrativa: `alembic upgrade head`, a partir de `backend` com o runtime de migração. A versão nova depende de `20260926_01`. O `create_all` de desenvolvimento não cria o warehouse.
2. Executar o provisionamento existente `backend/scripts/provision_app_role.py` após a migração. Ele agora concede acesso aos schemas analíticos existentes, inclusive no primeiro provisionamento. A API e o worker usam contas sem SUPERUSER/BYPASSRLS. O worker precisa ler o CRM, processar o ledger e renovar credenciais Bling. Usar segredos específicos por ambiente.
3. Definir `MARKET_DATABASE_URL` e `MARKET_TENANT_IDS` com IDs autorizados. Preservar a chave Fernet já usada pela integração Bling. O exemplo `analytics/.env.example` contém nomes de configuração, sem credenciais reais.
4. Construir e iniciar o overlay: `docker compose -f docker-compose.prod.yaml -f docker-compose.analytics.yaml -f docker-compose.analytics.prod.yaml build worker-data`; depois `up -d worker-data`. Respeitar as variáveis obrigatórias e dependências da composição base. O serviço executa com usuário 10001, filesystem somente leitura e diretório temporário para logs.
5. Solicitar a primeira carga CRM no painel, em **Cargas e modelos**, com usuário administrador. A solicitação retorna HTTP 202 e fica na fila; acompanhar o resultado da execução. Reexecutar uma carga atualiza fatos em vez de duplicá-los.
6. Para agendamento, ativar o profile `analytics-schedule`. O padrão atualiza CRM; outras fontes só entram quando `MARKET_SCHEDULE_SOURCES` as incluir. `quality` persiste alertas e snapshots. Usar intervalos compatíveis com tamanho/limites das fontes.

## dbt e Metabase

O Dockerfile instala dbt em `/opt/dbt`, separado das dependências de modelos, para permitir evolução independente das dependências transitivas. `MARKET_DBT_BIN` aponta para seu executável. Em instalação local, usar dois ambientes virtuais com `analytics/requirements.txt` e `analytics/requirements-dbt.txt`. A resolução das duas listas foi conferida com `pip --dry-run`, sem alterar o ambiente existente da aplicação.

A conta `MARKET_DB_USER` precisa de USAGE/CREATE nos schemas staging/core/mart, SELECT nos dados de raw/core e propriedade das relações criadas pelo dbt. Ela não deve ser proprietária do ledger nem ignorar RLS. O runtime HTTP não precisa de CREATE. Provisionar a conta de transformação como administrador e passar a senha por secret store. Exemplo de concessões para uma conta já criada:

```sql
ALTER ROLE market_transform NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
GRANT USAGE ON SCHEMA raw TO market_transform;
GRANT SELECT ON ALL TABLES IN SCHEMA raw, core TO market_transform;
GRANT USAGE, CREATE ON SCHEMA staging, core, mart TO market_transform;
```

Configurar `MARKET_DB_*`, testar `dbt build` e só então definir `MARKET_DBT_ENABLED=true`. Cargas concluídas enfileiram uma transformação independente. O worker serializa DDL dbt entre tenants. Os marts substituem a fatia completa da empresa, corrigindo exclusões e mudanças tardias; `full_refresh` está desabilitado para impedir remoção das outras fatias. Views staging/core usam `security_invoker` e o contexto transacional; todas as tabelas de mart criadas pelo dbt recebem FORCE RLS.

Para BI, gerar SQL revisável com `python -m analytics.provision_bi --tenant 1`. Executá-lo uma vez como administrador, definir a senha da nova conta em secret store e conectar Metabase com `market_bi_1`, expondo apenas `bi_tenant_1`. As views têm filtro fixo de empresa e security barrier; a conta leitora não recebe acesso às tabelas base. Não usar a conta da API, de transformação ou administrativa na conexão de BI. O profile `analytics-bi` disponibiliza Metabase em loopback na porta 3030; sua base de configuração é separada. Os componentes analíticos complementares podem ser consultados através das views de fatos sem depender de dashboards proprietários do Metabase.

## Fontes e reprocessamentos

Bling permanece uma ideia de integração futura no escopo atual. O adaptador de leitura e os testes de contrato são preparação técnica. A interface identifica a fonte como planejada e bloqueia novas cargas; fila e webhook também recusam processamento enquanto `MARKET_BLING_ANALYTICS_ENABLED=false` (padrão). Habilitar somente depois de configurar a conta e realizar a homologação descrita abaixo.

- **CRM:** carga completa reconciliada em uma transação. Remoções desativam fatos/relações; versões brutas ficam preservadas. Feedback posterior é reaplicado. Zero padrão de custo não é convertido em custo conhecido.
- **Bling:** paginação com limite explícito, leitura detalhada, limitação de taxa, retry em 429/5xx, janelas de pedidos de até 365 dias e reconciliação de linhas retiradas de pedidos. A chave da integração é a mesma usada pelo CRM. Estoque é uma observação datada. A disponibilidade dos recursos e campos precisa ser homologada com a conta real.
- **Webhooks:** configurar `MARKET_BLING_COMPANY_MAP` na API e registrar `/api/crm/market-intelligence/webhooks/bling/{tenant_id}` no Bling. Assinatura `X-Bling-Signature-256` sobre os bytes recebidos e companyId precisam conferir. Eventos duplicados são reconhecidos; a reconciliação consulta a origem para evitar sobrescrita por eventos fora de ordem.
- **PNCP:** modalidade 6 por padrão; outras modalidades devem ser especificadas no pedido. O watermark tem sobreposição de sete dias para atualizações tardias. Publicações e contratos ficam como evidência; apenas itens/resultados alimentam medidas de preços. Resultados cancelados ficam inativos. Cobertura é do universo consultado, sem assumir mercado total.
- **IBGE:** configurar tabela/variável de série adequada. `MARKET_DEFLATOR_SERIES=1737:2266` é uma seleção operacional possível, condicionada à adequação econômica da categoria e metadados da origem. A API exige unidade de índice de nível; mês ausente permanece desconhecido. Configurar `MARKET_DEFLATOR_BASE_MONTH=AAAAMM` para fixar o mês-base, ou usar o último mês observado.
- **CNPJ/manual:** POST `/records`, exclusivo de administrador, com até 1000 registros por lote. Carregar dimensões antes de relações/fatos. O enriquecimento CNPJ usa arquivos normalizados fornecidos pelo operador; não baixa automaticamente o dump nacional.

Backfill pode informar `date_from`/`date_to` por execução. O limite é dez anos por pedido e os conectores dividem janelas quando necessário. Backfill histórico não avança o watermark corrente. Falha reverte o snapshot inteiro e grava status de erro sanitizado. Para repetir, solicitar nova carga; a fila deduplica solicitações pendentes da mesma fonte. Um job interrompido pode ser recuperado após quatro horas, respeitando locks de transações ainda vivas.

## Semântica e modelos

Fornecedores usam nome de exibição estável em caixa alta e aliases com a grafia original. Caixa, acentos, espaços e pontuação são normalizados para comparação; `&` equivale a `e`. CNPJ completo prevalece sobre nomes, sem fundir filiais por raiz. Nomes com sufixos legais diferentes ou apenas semelhantes ficam na fila de revisão quando não há CNPJ. Rótulos genéricos e nomes com múltiplos CNPJs conhecidos não autorizam consolidação automática.

A carga CRM normaliza também os fornecedores já cadastrados. Administradores podem executar `POST /crm/market-intelligence/suppliers/normalize` ou usar **Normalizar fornecedores existentes** em **Revisão e feedback**. Consolidações remapeiam fatos e vínculos de produtos, preservam raw/aliases e gravam auditoria. Custos de vínculos colapsados permanecem na evidência da revisão; o valor canônico conhecido prevalece. Entidades substituídas ficam inativas com redirecionamento, impedindo que reimportações recriem duplicatas. Feedback humano original é conservado; sua leitura resolve o fornecedor canônico atual.

As telas distinguem dados ausentes, pendências, seleção rejeitada e lacuna confirmada. Rejeitar um candidato não prova que todo o catálogo falhou. OTIF/fill rate exigem quantidade recebida e datas prometida/recebida. Win rate do fornecedor usa o fornecedor da nossa oferta, e não o vencedor concorrente. Taxas e valores exibem suas amostras. Benchmark exige produto canônico, unidade, moeda, região e tipo de preço compatíveis; categoria isolada não comprova comparabilidade.

Modelos comerciais usam snapshots registrados antes do resultado, grupos de edital disjuntos e corte temporal. Decisões com resultado já conhecido são excluídas da aprendizagem de vitória. Requisitos iniciais: 100 rótulos, 20 grupos e pelo menos cinco exemplos de cada classe em treino/teste. Técnicos e resolução de identidade também exigem revisões humanas. Forecast exige 24 meses consecutivos observados, compara naive/sazonal em seis meses e escolhe menor MAE; não inventa meses vazios como zero. Clusters indicam similaridade exploratória, sem equivalência técnica automática. A margem é bruta estimada e não lucro líquido. Correlacionar preço e vitória não estima elasticidade causal.

Probabilidades comerciais só são expostas quando um modelo avaliado passa o gate frente ao baseline; seguem em observação com decisão humana. A coleta de rótulos e resultados reais é indispensável. Não há promoção automática nem retreino disparado por drift. MLflow registra modelos comerciais quando configurado; reports, datasets e versões também ficam no ledger por tenant.

## Validação e aceite de ambiente

Executar `python -m pytest analytics/tests -q` com dependências reais. Para PostgreSQL, definir `TEST_MARKET_PG_URL` apontando para uma base descartável nova cujo nome termine em `_test`. A suíte cria tenants/roles e aplica a migration analítica real; testa contexto ausente, leitura cruzada, escrita cruzada e impossibilidade de trocar o tenant das views BI por GUC. Nunca executar esse teste na base da aplicação. O workflow `.github/workflows/market-intelligence.yml` fornece PostgreSQL 16 para essa validação e faz parse do projeto dbt.

No frontend: `npm run test -- src/lib/commercial-intelligence.test.ts src/pages/CommercialIntelligence.test.tsx` e `npm run build`. A verificação global `npx tsc --noEmit -p tsconfig.app.json` também foi aprovada após corrigir os erros de tipos existentes.

O build dbt passou localmente com duas empresas e conta restrita: 17 modelos e 10 testes de dados por execução. A recarga real via Prefect após desativar um fato removeu a fatia obsoleta e preservou a outra empresa. A consulta pública da série IBGE 1737/2266 retornou HTTP 200, metadados de número-índice e observações mensais; isso valida o contrato de leitura, sem afirmar adequação econômica para todas as categorias. O CI inclui aplicação da migration, RLS e build dbt com duas empresas usando conta restrita; esse workflow ainda precisa executar no serviço remoto. A compilação do frontend, os testes específicos do painel e os testes analíticos locais passaram. O matching estruturado existente também passou em sua suíte de regressão.

Ao executar dbt diretamente, definir `PGOPTIONS=-c app.current_tenant_id=ID` além de `MARKET_TENANT_ID`. A rotina `python -m analytics.flows.pipeline --tenant ID --dbt` configura ambos, incluindo o contexto das conexões usadas pelos testes de dados.

Aceite antes de ativar em produção: migrations da cadeia completa, provisionamento das contas, RLS/API/BI com duas empresas, dbt build com ambas e recarga após exclusão, conferência de cinco produtos/pedidos/resultados por origem, credenciais OAuth e HMAC, recurso real de recebimento, backup/restore e consumo do worker. A migration analítica e o isolamento API/BI passaram com PostgreSQL 16 em container descartável. Um segundo banco com pgvector passou pelo bootstrap operacional completo, stamp 20260926_01, upgrade 20261009_01 e provisionamento da conta restrita. O worker real processou exemplos CRM de duas empresas, validando os valores e o isolamento. Fontes autenticadas ainda exigem homologação com as contas reais. A entrega do código não implica integração live ou modelo validado.

Rollback operacional: desligar worker/agendamento e retornar a interface/API à versão anterior; dados analíticos ficam preservados. Downgrade do warehouse requer revisar e remover previamente as relações dbt dependentes e executar como administrador. As colunas aditivas do catálogo/resultados são conservadas no downgrade para evitar perder dados de identificação.

## Resultado da verificação local

- 65 testes analíticos aprovados, incluindo 3 testes PostgreSQL com a migração real; incluem regressões da fila compartilhada, controle de desativação, relações, filtros e bootstrap.
- 52 testes do matching estruturado existente aprovados.
- Suíte frontend completa com 63 testes aprovados, compilação Vite aprovada e lint dos arquivos novos aprovado.
- dbt build aprovado para duas empresas e recarga após exclusão via Prefect aprovada; imagem analítica e worker CRM reais validados em filesystem somente leitura; composição de produção e verificação estática Python aprovadas.
- TypeScript global aprovado; a suíte completa inclui o painel e as telas/utilitários afetados pelos ajustes de tipos.

Contatos Bling sem papel de fornecedor confirmado ficam fora do Supplier 360, salvo quando há evidência de compra ou vínculo produto-fornecedor. Valores de pedidos são registros observados; não equivalem a pagamentos ou entregas concluídas.

A execução real identificou incompatibilidade do Prefect 3.4.22 com a implementação de roteamento do FastAPI 0.137+. O runtime analítico fixa FastAPI 0.116.1 e Starlette 0.47.3, verificados por pip check e por flow dbt completo. Referência: [issue de compatibilidade do Prefect](https://github.com/PrefectHQ/prefect/issues/22398). HOME, PREFECT_HOME e artefatos dbt usam /tmp no container. O CI cobre esse flow real e a recarga após exclusão.

Em Windows/OneDrive, construir o contexto com arquivos regulares usando `python -m analytics.build_image --tag ragmatch-market-worker:local`. O comando inclui apenas código backend/analytics, conserva o módulo de logs e exclui segredos `.env`, logs, caches e saídas dbt. A composição reutiliza `MARKET_WORKER_IMAGE`; após a construção, iniciar os serviços com `up -d --no-build worker-data`. Os mesmos cuidados de banco, migração e conta restrita se aplicam. O CI usa esse construtor.

## Teste integrado local no Docker

A composição `docker-compose.analytics.test.yaml` é independente, com nome de projeto
`ragmatch-market-test`, volume próprio e portas em loopback: portal 3088, API 8088 e
PostgreSQL 65441. Usa dependências das imagens API/portal indicadas na composição,
código backend atual montado somente para leitura e o bundle CRM atual. Não integra
fontes externas nem executa modelos Ollama neste teste. Os segredos explícitos da
composição são fictícios e exclusivos do ambiente local; não usar este arquivo em
produção.

O worker local também monta `backend/app` e `analytics` somente para leitura, usando
as dependências da imagem analítica. Após editar código, reiniciar API e worker;
após editar o CRM, recompilar o bundle. Essa montagem é exclusiva do teste local.

Em **Cargas e modelos**, o painel mostra saúde das cargas e previsões avaliadas.
`GET /crm/market-intelligence/operations?days=30` aceita de 1 a 90 dias: contagens e
taxa de falha cobrem a janela inteira; quantis usam até 2.000 execuções recentes;
pendências ativas incluem solicitações anteriores à janela. Os limiares são 48 h
sem atualização, 15 min na fila e 4 h em execução. O snapshot de qualidade conserva
essas métricas sem habilitar retreino automático.

Previsões `forecast-v2` comparam último mês, mediana móvel de três meses e último
ano nos seis meses finais observados. A faixa nominal de 90% usa erros anteriores
a essa comparação, exige pelo menos 12 meses de calibração e informa a cobertura
efetivamente observada nos seis meses finais. Não há garantia de cobertura futura;
revisões retrospectivas das fontes continuam uma limitação. Sem 24 meses
consecutivos, a interface informa insuficiência. A versão do dataset e a contagem
real de registros são persistidas com a avaliação.

Validação desta continuação: 55 testes analíticos e 56 testes frontend aprovados;
TypeScript global, lint Python e build do CRM aprovados. No Docker isolado, as duas
contas passaram novamente por login, cargas CRM, consulta operacional e exportação.
Jobs de qualidade e previsão concluíram e persistiram snapshot operacional e
dataset versionado no PostgreSQL. A aba **Cargas e modelos** foi verificada em Edge
headless após login real, com histórico insuficiente explícito e sem erros JavaScript.

```powershell
npm --prefix bid-buddy run build:embed
python -m analytics.build_image
docker compose -p ragmatch-market-test -f docker-compose.analytics.test.yaml up -d
docker compose -p ragmatch-market-test -f docker-compose.analytics.test.yaml run --rm seed-demo
python -m analytics.smoke_local
```

O seeder recusa outra base e tenants que não sejam os demos; uma nova execução
conserva os demos existentes. Contas `demo1@example.com` e `demo2@example.com`, senha
local `DockerTeste@2026`. Entrar em http://127.0.0.1:3088/login e acessar
http://127.0.0.1:3088/crm/inteligencia-comercial após o login.

O teste HTTP foi aprovado pelo proxy real do frontend: autenticação das duas contas,
HTTP 202 de cargas CRM, conclusão pelo worker, valores 6500/13000 isolados, relatório,
diagnóstico e CSV. API validou RLS no startup e health/ready respondeu 200. O bundle
CRM e seus assets foram servidos pelo nginx. O formulário de login também foi validado em Edge headless: resposta 200,
redirecionamento para /dashboard, sessão conservada após reload e acesso ao painel
Inteligência comercial sem erros JavaScript ou falha da ponte de sessão. O controle
do navegador integrado falhou ao iniciar; a validação visual usou Playwright.

Para interromper sem apagar os dados fictícios:
`docker compose -p ragmatch-market-test -f docker-compose.analytics.test.yaml down`.

## Backup, desempenho e desativação local

`python -m analytics.backup_local` executa backup consistente do demo, restaura em um banco novo, compara dados, valida a migration/RLS e remove somente o banco temporário criado pela execução. O dump e manifesto SHA-256 permanecem em `analytics/.validation/backups`. O comando recusa uma base com tenants que não sejam os demos e não aceita conexão de produção. Roles e grants devem ser provisionados separadamente após restauração real; não estão incluídos no dump sem ACLs.

`python -m analytics.benchmark_local --rows 5000` insere fatos fictícios em uma transação, mede consulta/cálculo/JSON e reverte a transação. O arquivo `analytics/.validation/benchmark.json` registra escopo e tempos. Não conserva os fatos e não mede throughput HTTP ou capacidade de produção.

Para desativar reversivelmente a funcionalidade, definir `MARKET_INTELLIGENCE_ENABLED=false` na API, worker e scheduler e recriar esses serviços. As rotas respondem 503 com mensagem explícita; o worker deixa de buscar jobs, o scheduler não enfileira e o histórico permanece armazenado. Um job já em andamento pode concluir. Reativar a configuração retoma a fila. A composição local e o overlay analítico expõem essa variável; no Docker local usar `up -d --no-deps api worker-data` após mudar o valor, preservando o volume.

O frontend tem gates próprios em `bid-buddy/.github/workflows/commercial-intelligence.yml`; o repositório principal conserva os gates analíticos. Como o frontend é um repositório Git independente, publicar ambos é necessário para executar ambos os workflows remotamente.

## Dashboard comercial, previsões e apresentação ao fornecedor

Após entrar no portal, abra `/crm/`. O dashboard mostra **Demanda e oportunidades comerciais** com a base CRM e a data da última carga. **Explorar produtos e fornecedores** expande a análise interativa. Os atalhos levam à seção comercial; a inteligência de atributos também oferece acesso a essas áreas.

Em **Inteligência comercial → Predição**, escolha demanda ou preço. O administrador solicita a avaliação, processada pelo worker. **Consultar resultado da avaliação** recarrega o resultado. A tela identifica fila, processamento e falhas; dados anteriores permanecem identificados como a última avaliação concluída. O gráfico usa grupos comparáveis; o detalhamento informa o mês previsto, método, erro e faixa histórica quando disponível. Os filtros de período não alteram a avaliação, que usa o histórico da empresa. Sem histórico elegível, a previsão permanece indisponível.

Em **Apresentar ao fornecedor**, aplique primeiro os filtros comerciais; escolha fornecedor, origem e busca. Vínculos do catálogo delimitam os produtos; não representam compras confirmadas. **Baixar apresentação para fornecedor** gera HTML autônomo com valores observados, amostras e cenário hipotético; abra no navegador e use Imprimir → Salvar como PDF. **Exportar demanda para fornecedor** gera CSV. As exportações incluem o recorte inteiro, mesmo quando a tabela limita a exibição a 200 produtos. Custos internos, margens e feedback não fazem parte dos arquivos compartilháveis.

O bootstrap do checklist padrão agora serializa a primeira criação por empresa no PostgreSQL, evitando colisão entre as consultas paralelas do dashboard. Um checklist existente que deixou de ser padrão é preservado.

## Publicações versionadas no Docker Hub

O usuário autorizou manter o Docker Hub atualizado conforme as implementações avançam. Após os checks e a homologação das imagens sem montagens do código, publicar uma tag nova comum para API, frontend e worker; preservar o registro dos digests e das evidências. A primeira versão publicada é `commercial-20261009-v1`, incluindo a tag correspondente da imagem MLflow existente. A versão atual publicada e executada no demo é `commercial-20261009-v4`, com planejamento, acompanhamento, composição de custos e relatório interno das negociações.

Procedimento, hashes e comandos: [release atual commercial-20261009-v4](releases/commercial-20261009-v4.md), [release v3](releases/commercial-20261009-v3.md), [release v2](releases/commercial-20261009-v2.md), [release anterior v1](releases/commercial-20261009-v1.md). O builder é `analytics/build_release.py`, e o overlay de validação é `docker-compose.analytics.release-test.yaml`. Publicação das imagens não implica implantação na VPS.

## Planejamento de compras e cotações

A entrega incremental adiciona o atalho **Planejar compras e cotações** no CRM e a aba **Planejamento e cotações** na Inteligência Comercial. Demanda, estoque físico/reservado e unidade ajudam a avaliar a quantidade; o usuário confirma a solicitação. Propostas incluem frete, impostos adicionais, disponibilidade, lote mínimo, prazo e validade. A escolha registra justificativa e histórico sem emitir pedido ou reservar estoque.

Procedimento e critérios: [planejamento e cotações](planejamento-compras-cotacoes.md). Migração adicional: `20261009_02`. Backup deve incluir as tabelas de solicitações e propostas. A normalização de fornecedores também atualiza os vínculos das cotações, preservando a evidência original.



Acompanhamento: indicadores clicáveis para solicitações sem propostas/com escolha e propostas vencidas, vencendo ou com condições não informadas. Filtros de estado, fornecedor e produto/referência recortam as solicitações; o resumo geral continua abrangendo a empresa inteira. **Propostas por fornecedor** usa a identidade normalizada. A comparação mostra preço unitário/unidade, referência e data do registro. Procedimento no [guia de planejamento e acompanhamento](planejamento-compras-cotacoes.md).


O relatório interno de negociação reúne composição de custo, diferenças entre propostas elegíveis, evidências e histórico. É identificado como interno e imprimível em PDF; a solicitação preparada para o fornecedor continua com campos restritos. Os filtros preservados na solicitação aparecem com rótulos legíveis. Procedimento no [guia de planejamento e negociação](planejamento-compras-cotacoes.md).
