# Comercial v7 — dashboards guiados e TorTecDash

Tag: `commercial-20261010-v7`, namespace Docker Hub `alvarocareli`.

O CRM agora abre a inteligência comercial com um resumo em linguagem simples, números maiores e quatro ações: explorar demanda, prever demanda, planejar compras e apresentar ao fornecedor. Filtros globais, controles de comparação, tabelas completas e ferramentas administrativas ficam recolhidos.

Na inteligência de mercado, a consulta inclui editais ainda sem resultado e exclui os abandonados após a leitura. O filtro SQL anterior podia eliminar resultados nulos. Os itens da triagem aparecem com descrição, categoria, quantidade, atributos BI e características técnicas cadastradas. Falha ou carregamento mostram indicadores indisponíveis, sem zeros falsos.

O projeto independente `supplier-portal` (TorTecDash) consulta dados reais da API. Administradores e editores geram links por fornecedor canônico, fonte e filtros, válidos de 1 a 30 dias, e podem revogar o acesso. O token usa audiência exclusiva e hash persistido; não concede login no CRM. Empresas desativadas também perdem acesso. A resposta tem somente empresa, fornecedor, recorte, datas e demanda de produtos vinculados, sem custos, margens ou identificadores internos. O navegador consulta novamente a cada cinco minutos e mostra a última sincronização.

## Atualização do portal

Aplicar a migração Alembic `20261010_03` em banco existente, antes de iniciar a API v7. A tabela de links tem ENABLE e FORCE RLS; a migração replica os privilégios limitados da tabela de fatos. O bootstrap de bancos totalmente novos permanece sujeito à validação específica do script existente.

Atualizar as imagens `ragmatch-api`, `ragmatch-frontend` e `ragmatch-market-worker` para a tag acima. O overlay `docker-compose.analytics.prod.yaml` ativa o agendador do CRM por padrão, com os tenants explicitamente configurados e intervalo `MARKET_SCHEDULE_SECONDS` (padrão 3600 segundos). O ambiente local isolado sincroniza a cada 300 segundos. A frequência de consulta da página não substitui a frequência de sincronização do portal.

Publicação das imagens não atualiza automaticamente a VPS. Os arquivos públicos da VPS foram conferidos nesta entrega: os painéis do CRM ainda não continham as novas seções ou o compartilhamento ao vivo. Não houve acesso administrativo à VPS.

## Vercel

Importar o repositório e escolher `supplier-portal` como Root Directory, framework Other, sem build. Nome sugerido: `tortecdash`. O proxy em `vercel.json` aponta exclusivamente para o endpoint de apresentação na VPS conhecida; confirmar esse domínio ao configurar o ambiente real. Após o deploy e atualização da API, informar a URL publicada no CRM para gerar os links. A publicação no Vercel exige acesso autenticado à conta; não foi inferida a existência do domínio sugerido.

## Validação

79 testes do CRM; 91 testes analíticos e 5 PostgreSQL opcionais omitidos por falta de banco descartável configurado; 5 testes das páginas narrativas do portal; 2 testes do TorTecDash. TypeScript, lint dos componentes modificados e build do CRM passaram. Migração e privilégios verificados no PostgreSQL Docker local com dados fictícios. Fluxo real no navegador: login, leitura da triagem, gráficos, compartilhamento, audiência de tokens, cenário, busca, revogação e largura 390/1440. Capturas disponíveis em `analytics/.validation/v7-*.png` (artefatos locais ignorados).

Bling segue integração futura. Simulação aritmética não é predição; os modelos existentes continuam exigindo amostra suficiente e validação temporal.
