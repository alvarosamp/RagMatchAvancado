# Testes automatizados

O CI verifica a aplicação em quatro camadas: testes unitários, integração HTTP,
PostgreSQL/Redis reais e navegação no frontend compilado. Publicação no Docker Hub
e deploy dependem dessas verificações. Não é necessário configurar credenciais da
VPS para executar os testes de um pull request.

## Cenários cobertos

- Login real, cookies HttpOnly, logout, JWT inválido/expirado, troca de senha,
  invalidação de sessões, recuperação com token expirável e de uso único.
- Administrador/editor/leitor, alterações de papel com auditoria, proteção do
  último administrador, CSRF, hosts permitidos e limite de login no Redis.
- Três empresas isoladas: consultas e alterações por API, RLS por SQL direto,
  contexto ausente, transações com commit/rollback e usuário de banco sem DDL.
- CRUD com persistência, conflitos, filtros, paginação, ordenação e consultas
  simultâneas que criam apenas um checklist padrão.
- Suspensão, retomada, cancelamento e reabertura de editais, histórico auditável,
  transições inválidas, exportação CSV e agenda ICS.
- Dashboard com dados reais e falha parcial de permissão no PostgreSQL: uma seção
  indisponível não deve virar zero nem impedir as outras consultas.
- Relatórios com notas 0, 0,5 e 1: média, mediana, desvio, classificação, histograma,
  evolução e ausência de resultados pertencentes a outra empresa.
- Upload e download com conferência dos bytes, versões que preservam o original,
  metadados persistidos, exportação ZIP e acesso entre empresas bloqueado.
- Telas do portal e CRM em 390 e 1440 pixels, Chromium e Firefox: carregamento,
  dados da empresa correta, login/reload, redirecionamento por permissão e erros
  visíveis quando o backend falha. Os testes de falha de interface interceptam
  apenas a requisição que deve falhar; os demais usam a aplicação real.

## Cobertura

A cobertura do backend combina o processo dos testes unitários com o servidor
real e as verificações de ORM. A meta global é 50% das linhas de **todo**
`backend/app`, com metas independentes para módulos críticos: autenticação 90%,
dependências de autorização 85%, proteção HTTP 95%, sessão de banco 85% e
dashboard CRM 95%. `qa/check_coverage.py` bloqueia o pipeline se alguma meta cair.

O relatório unitário do frontend inclui todo `src`, com limites específicos para
autenticação e utilitários; a navegação de ponta a ponta é uma verificação
separada. Não se deve interpretar a cobertura de três utilitários como cobertura
de todas as telas. As suítes de inteligência comercial, modelos e transformações
dbt continuam como verificações obrigatórias no workflow dedicado.

## Execução local

Requisitos: Docker Compose v2, Python 3.11+ e Node 24 para compilar o CRM.
Execute na raiz do repositório:

```bash
pip install -r qa/requirements.txt
python -m playwright install chromium firefox
mkdir -p .validation test-results/functional
cd bid-buddy && npm ci && npm run build:embed && cd ..
python qa/build.py api --tag ragmatch-api:qa
python qa/build.py frontend --tag ragmatch-frontend:qa --crm-assets bid-buddy/dist-embed
python qa/build.py qa --tag ragmatch-quality-api
docker compose -f qa/compose.yaml up -d --no-build --wait --wait-timeout 300
pytest qa --ignore=qa/test_browser.py --junitxml=test-results/functional/api.xml
pytest qa/test_browser.py --browser chromium --browser firefox --tracing=retain-on-failure --screenshot=only-on-failure --output=test-results/functional/browser
docker compose -f qa/compose.yaml stop api
docker compose -f qa/compose.yaml down --volumes
```

No Windows/OneDrive, `qa/build.py` cria um contexto Docker com arquivos regulares,
evitando problemas com placeholders. Para compilar o CRM sem instalar Node local,
use `python qa/build.py crm --tag ragmatch-crm:qa`, crie um container temporário
dessa imagem e copie `/app/dist-embed` para `.validation/crm-dist`; use essa pasta
em `--crm-assets`. O helper não altera `frontend/public/crm`.

A stack usa apenas `ragmatch_quality`, portas locais 13089/18089/18439, senhas
sintéticas e armazenamento PostgreSQL temporário. Remova e recrie essa stack para
cada execução completa. Nunca substitua suas URLs por um banco de produção.
O bootstrap e as fixtures SQL recusam nomes de banco diferentes.

O GitHub Actions guarda JUnit, logs, relatórios HTML/XML de cobertura e capturas e
traces dos testes de navegador que falharem. Encerre a API antes de copiar
`.coverage.functional`, para que o processo grave os dados.

Integrações externas com IA, SMTP, PNCP, assinatura e Bling exigem cenários
específicos e ambientes próprios. Esta suíte não comprova a disponibilidade dos
provedores nem a configuração de domínio/TLS da VPS.
