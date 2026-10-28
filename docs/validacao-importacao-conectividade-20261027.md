# Validação da entrada de conectividade — 27/10/2026

## Fluxo confirmado pelo usuário

Baixador → n8n → pasta de JSONs → upload manual no RagMatch.
O teste começa no JSON; não executa downloads nem o workflow externo n8n.

## Ambiente

Projeto Docker Compose isolado: `ragmatch-connectivity-qa`.
PostgreSQL pgvector 16, Redis, API com o código atual e frontend compilado.
Banco descartável `ragmatch_quality`, com migrações, conta restrita e RLS.
As imagens usadas são `ragmatch-connectivity-api:qa` e
`ragmatch-connectivity-frontend:qa`. Nenhuma implantação de produção foi feita.

## Resultados

- Teste HTTP `qa/test_connectivity_import.py`: aprovado. Importa as sete categorias,
  verifica atributos, evidência original, reimportação sem duplicação, inclusão de
  um oitavo item no mesmo documento/CRM, rankings e isolamento entre empresas.
- Teste Chromium `qa/test_connectivity_upload_browser.py`: aprovado. Seleciona o
  arquivo na tela `/upload`, mantém sincronização CRM habilitada, processa e
  confirma sete itens pela API, sem erros de JavaScript.
- Exemplo atual do produtor `itaberaba_componentes_contextuais_v7_4_7.json`:
  importado pelo proxy do frontend; seis itens confirmados no banco/CRM,
  preservando atributos e representação original. Identificador alterado para
  um prefixo QA para manter o exemplo restrito ao teste.
- Verificações anteriores: 38 testes unitários backend e 6 testes de interface
  aprovados. Build do frontend em Docker aprovado.

## Correções incluídas

Normalização dos nomes das categorias; rankings de atributos para Patch cord,
DAC e AOC; novos atributos de switches/APs, incluindo combinações de redundância;
remoção do limite de quatro categorias e dois atributos no painel de análise.

## Limites

A validação comprova ingestão, persistência e leitura dos dados técnicos. Não
comprova identificação automática de fabricantes por modelo, enriquecimento por
datasheet ou acurácia de matching. O painel legado `/analise/dashboard` continua
dependendo da configuração existente `VITE_AI_FEATURES_ENABLED=1`; o build padrão
não altera essa opção. O teste de navegador cobre a tela de upload disponível no
build padrão, e os rankings são verificados pela API e pelos testes de interface.

Na seleção de pasta de histórico, a interface ativa o modo somente análise por
padrão. Para sincronizar os itens com o CRM, desmarcar
"Somente analise, nao sincronizar CRM" antes de processar.
