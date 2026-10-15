# Prévia local — revisão documental e comparação técnica

Endereço: http://localhost:13089/laboratorio-tecnico

Conta exclusivamente de teste:

- E-mail: alpha-admin@example.com
- Senha: Quality-Test-Only-2026!

No menu **Análise → Revisão documental**, selecione um item e um produto da LPU, envie os PDFs e escolha as páginas do item/modelo. Também existem dois exemplos simulados para experimentar o fluxo.

## O que funciona

- Leitura do PDF, com arquivo, SHA-256, página e trecho em cada valor.
- Extração explícita de portas RJ45/SFP/SFP+, orçamento PoE, capacidade, alcance, Tx/Rx, gerenciamento, fibra e conector.
- Operadores mínimo, máximo, acima/inferior e conversão km/m e Mbps/Gbps.
- Revisão individual dos requisitos e dos atributos antes da decisão.
- Preservação das partes não reconhecidas e de alternativas/escopos complexos.
- Conflitos entre valores do datasheet, com escolha limitada aos candidatos realmente extraídos.
- Identificação do modelo da LPU nas páginas do documento. Modelo não identificado e versão física ausente bloqueiam aprovação da prévia.
- Matriz usando o motor de comparação do projeto, com resultados ATENDE, VERIFICAR e NAO_ATENDE.
- Exportação do JSON completo com fontes, revisão e usuário.

Esta etapa é uma prévia sem gravação de requisitos, ficha técnica ou seleção comercial no CRM. Foram copiados 188 produtos da LPU fornecida para o banco local, mantendo o Excel original. Editais reais da VPS não são acessados por esse ambiente. Os dados e PDFs dos botões de exemplo são explicitamente simulados.

## Limites claros

Não é um extrator universal nem afirma capturar integralmente qualquer edital. Tabelas de várias versões/modelos, protocolos não suportados, alternativas e condições ficam pendentes. Trechos explicitamente obrigatórios não podem ser aprovados apenas por uma justificativa de exclusão. PDFs sem texto precisam de OCR, que não é executado nesta prévia. Não há crawler nem download automático de datasheets online.

Um item carregado apenas pela descrição da triagem não ganha uma página de PDF inventada; fica pendente até que o documento seja enviado. Informar a revisão do hardware é uma declaração do revisor, não comprovação automática da versão física. A classificação é preliminar e não confirma um match operacional.

## Containers

Projeto: ragmatch-technical-preview. Banco, volumes, rede e cookie próprios; somente o frontend está exposto, em 127.0.0.1:13089. A API usa a base de dependências anterior em cache e copia o código atual da branch (265ce4c mais as mudanças locais desta prévia). Não há montagem do código-fonte em runtime.

```bash
docker build -f preview/Dockerfile -t ragmatch-technical-preview-api:local .
docker build -t ragmatch-technical-preview-frontend:local frontend
docker compose -f preview/compose.yaml up -d --wait
```

Para parar mantendo os dados locais:

```bash
docker compose -f preview/compose.yaml stop
```

## Validação

11 testes unitários do extrator dentro da imagem. Smoke HTTP com PDF real gerado pelo servidor, revisão e comparação; testes de anônimo 401, viewer 403, outro tenant 404 e PDF corrompido 422. LPU importada no banco isolado. Interface validada no navegador real: envio multipart dos PDFs, VERIFICAR antes da revisão, ATENDE com evidências revistas e NAO_ATENDE para PoE de 180 W diante de mínimo de 370 W. Screenshot em output/technical-preview/preview.png. Os relatórios ficam em output/technical-preview.

## Sessão renovável

JWT curto (padrão 60 minutos) renovado por cookie HttpOnly. Sem Manter conectado, cookies de sessão e prazo absoluto de 12 horas. Com a opção marcada, cookies persistentes e prazo absoluto de 30 dias. Os limites são configuráveis por AUTH_SESSION_HOURS e AUTH_REMEMBER_DAYS; uso e renovação não estendem esse prazo. Alguns navegadores restauram cookies de sessão ao restaurar janelas; para encerrar o acesso, use Sair.

A renovação gira a geração do token, com 15 segundos de tolerância para abas simultâneas. Reutilização fora da tolerância revoga a sessão. Logout revoga o registro no banco; troca ou recuperação da senha, conta e tenant desativados bloqueiam acesso e renovação. O refresh só aceita requisição com X-Session-Refresh: 1 e passa pela validação de origem do aplicativo.

Portal Axios e CRM fetch renovam ao receber 401 e repetem a chamada uma vez. O aplicativo verifica a sessão a cada cinco minutos enquanto visível e ao voltar para a aba. Tokens não são guardados no localStorage. É necessário fazer login uma vez após atualizar para criar a sessão renovável. SECRET_KEY precisa permanecer estável entre reinícios/réplicas.

O CRM foi compilado do commit privado 463f56b, usando uma cópia isolada em output/technical-preview/crm-session-source. O checkout bid-buddy original foi preservado. O patch reproduzível do logout está em docs/crm-session-source.patch. O script sync-bid-buddy.mjs aplica o patch e injeta /session.js antes de gerar hashes dos artefatos. Para reconstruir usando essa cópia:

```bash
node scripts/sync-bid-buddy.mjs --source-path=output/technical-preview/crm-session-source
```

### Testes de sessão

62 testes HTTP com API e PostgreSQL reais (autenticação existente + 12 casos de sessões). 42 testes do frontend, incluindo a opção Manter conectado, e cinco testes do cliente de renovação em frontend/tests/session.check.mjs. Migrations verificadas a partir de quatro revisões anteriores, com preservação dos dados, e em banco vazio separado. O navegador real permaneceu autenticado após um token temporário de um minuto expirar: o registro passou para geração 1 sem novo login. O CRM renovou a mesma sessão até geração 3; Sair do CRM a revogou no banco. O override de um minuto foi removido e a prévia voltou ao prazo normal de 60 minutos.

```bash
node --test frontend/tests/session.check.mjs
# no container local:
docker exec -e QA_API_URL=http://127.0.0.1:8000 -e QA_ADMIN_URL=postgresql://postgres:quality-admin-only@db:5432/ragmatch_quality -e QA_SEED_PATH=/reports/seed.json ragmatch-technical-preview-api-1 python -m pytest -q /qa/test_auth.py /qa/test_browser_sessions.py
```

## Match no próprio edital

A aba Match do CRM agora lista os itens e abre o popup manual por item. Na aba Itens, Exportar JSON está ao lado de Detalhes. O edital EXEMPLO-MATCH-MANUAL demonstra importação do JSON, categoria, filtros ponto a ponto, seleção e confirmação. Seus produtos e PDF são explicitamente simulados. Consulte docs/manual-match-local.md para o contrato e os limites. A confirmação do exemplo foi reaberta no navegador com fonte JSON, filtros e seleção preservados.
