# Hostinger — branch de inteligência de produtos

Compose exclusivo de `codex/inteligencia-produtos-hostinger`. A stack completa é
baseada na composição completa de produção, com imagens Linux amd64
da aplicação e do CRM fixado no submódulo. Não altera a `main`.

## Colar Compose e ambiente no painel Docker

Use **`deploy/products/compose.panel.yaml`**: é um único arquivo independente,
com imagens prontas no Docker Hub. Não depende de checkout, submódulo ou build no
painel. O Docker Manager observado pulou o build e tentou criar `migrate` antes
de existir a imagem local; por isso o fluxo do painel usa somente pull.

Release: `products-hostinger-20261028-v4`, nos repositórios
`alvarocareli/ragmatch-api`, `alvarocareli/ragmatch-frontend` e
`alvarocareli/ragmatch-mlflow`. A aplicação vem do commit
`7fc43556cfb16f3e18cd46c39a42257f402dcd1e` desta branch, com o ajuste de proxy
validado em `8b458a3`. O frontend inclui a correção `8ba9c68`: cadastro e
recuperação de senha permanecem abertos quando a consulta inicial de sessão
retorna 401. API e MLflow reutilizam as imagens validadas da v3, com a mesma tag
v4 do frontend. Inclui o relatório por marca e não usa `PUBLIC_ORIGIN`.

1. No servidor de teste, abra o projeto existente (na implantação acompanhada,
   **`servidor2`**). Preserve esse nome para reutilizar os volumes já criados.
   Para uma instalação nova, use `ragmatch-products-test`.
2. Cole todo o conteúdo de `compose.panel.yaml` no editor de Compose.
3. Nas variáveis de ambiente, cole os valores de um arquivo gerado conforme
   `hostinger.env.example`. Use credenciais novas numa instalação nova; se o
   projeto já possui banco/storage, preserve as senhas dessa instalação.
4. Não é necessário informar IP ou domínio no ENV. O proxy preserva o endereço
   e a porta usados pelo navegador; a API valida requisições da mesma origem.
   Para outra porta, ajuste `HTTP_PORT` e libere essa porta no firewall.
5. Na primeira instalação com banco vazio, use `ALLOW_EMPTY_DATABASE_BOOTSTRAP=1`.
   Depois da implantação bem-sucedida, volte para `0` nas variáveis do painel.
6. Implante. O painel baixa as imagens prontas; o Ollama também baixa os modelos.
   `migrate`, `db-bootstrap` e `initialize` devem terminar com código zero.

Abra `http://IP_DO_SERVIDOR:8088/login` usando `ADMIN_EMAIL` e `ADMIN_PASSWORD`.
O relatório por marca fica em `/crm/inteligencia-mercado`.

`docker-compose.prod.yaml` e `compose.hostinger.yaml` continuam sendo a composição
para build a partir do checkout pelo terminal, usando o overlay `compose.build.yaml`.
O arquivo para **colar sozinho no painel** é `compose.panel.yaml`.

## Serviços e isolamento

A composição inclui PostgreSQL/pgvector, PgBouncer, Redis persistente, MinIO,
Ollama, MLflow, migração, provisionamento do banco, inicialização do administrador,
API, workers, scheduler e frontend. Somente o frontend publica uma porta no host.
Não exige domínio, Traefik ou rede externa. Os volumes pertencem ao projeto de
Compose escolhido; nunca use o nome/volumes do servidor principal.

A sequência é banco saudável → migração → usuário restrito → administrador de
teste → API saudável → frontend. A aplicação usa a conta restrita; a conta de
administração do PostgreSQL fica nos serviços de inicialização. Reimplantar não
redefine a senha do administrador existente. O inicializador recusa bancos com
nome diferente de `ragmatch_products_test`.

`SEED_DEMO=0` começa sem exemplos; com `1`, cria editais/produto explicitamente
fictícios. Para dados reais de teste, envie os JSONs em `/upload` com a opção
**Somente análise, não sincronizar CRM** desmarcada, e importe o catálogo no CRM.

Ollama baixa os modelos na primeira implantação (`OLLAMA_PULL_MODELS=1`); falha
no download interrompe essa etapa em vez de declarar sucesso. Para validar apenas
JSONs/interface sem modelos, use `OLLAMA_PULL_MODELS=0`. LLM e coletas agendadas
ficam desligados por padrão; ligue as variáveis correspondentes quando necessário.
O worker analítico separado e os overlays de BI não fazem parte do Compose base.

Este acesso por IP usa HTTP e `AUTH_COOKIE_SECURE=0`. Ao configurar um proxy com
HTTPS, ajuste `AUTH_COOKIE_SECURE=1`. O Nginx encaminha `/api` e
usa a configuração do frontend da branch, incluindo os cabeçalhos de segurança.

## Build no servidor pelo terminal (sem publicação no Docker Hub)

Clone com `--recurse-submodules --branch codex/inteligencia-produtos-hostinger`.
O Git precisa ter acesso de leitura ao repositório do CRM. Na raiz do clone,
gere o ambiente com `python3 deploy/products/make_env.py`, copie o arquivo gerado
para `.env.prod`. Não é necessário executar `set_origin.py` nem configurar
`PUBLIC_ORIGIN`; o Compose desta branch não usa essa variável.

```sh
docker compose --env-file .env.prod -f docker-compose.prod.yaml -f deploy/products/compose.build.yaml config --quiet
docker compose --env-file .env.prod -f docker-compose.prod.yaml -f deploy/products/compose.build.yaml build api frontend mlflow
docker compose --env-file .env.prod -f docker-compose.prod.yaml pull db pgbouncer redis minio ollama ollama-setup
docker compose --env-file .env.prod -f docker-compose.prod.yaml up -d --no-build --pull never --wait --wait-timeout 900
```

API e todos os workers/migradores usam a mesma imagem construída localmente.
Depois de subir, volte `ALLOW_EMPTY_DATABASE_BOOTSTRAP` para `0` em `.env.prod`.
Nenhuma imagem da aplicação é enviada para um registro por esses comandos.
Os downloads de dependências e imagens base continuam necessários.

## Diagnóstico

```sh
docker compose --env-file deploy/products/hostinger.env -f deploy/products/compose.hostinger.yaml config --quiet
docker compose --env-file deploy/products/hostinger.env -f deploy/products/compose.hostinger.yaml up -d --wait --wait-timeout 600
docker compose --env-file deploy/products/hostinger.env -f deploy/products/compose.hostinger.yaml ps -a
docker compose --env-file deploy/products/hostinger.env -f deploy/products/compose.hostinger.yaml logs --tail=80 migrate db-bootstrap initialize api
```

Use `stop` para pausar sem apagar dados. Não use `down -v` em uma instalação com
dados que devem ser preservados. Se já existe um projeto com o Compose de produção
nesse servidor de teste, esta composição tem banco e volumes próprios: não é uma
migração automática dos volumes daquela outra stack.

## Validação local

Builds Linux amd64 do portal, CRM, API e MLflow; Nginx e versão MLflow conferidos.
Stack completa iniciada com projeto isolado e banco vazio. Migração, provisionamento
e administrador terminaram com código zero; API saudável e workers iniciados.
Teste HTTP pelo Nginx aprovou readiness, bloqueio de origem indevida, login com
cookie, importação JSON e leitura persistida no CRM usando a conta restrita.
O download de modelos foi desativado nesta validação; inferência com LLM e a
implantação na Hostinger ainda não foram executadas.

Teste HTTP opcional, que cria um edital fictício no ambiente de teste:

```sh
python3 deploy/products/smoke_test.py --base-url http://IP_DO_SERVIDOR:8088 --env-file .env.prod
```

O Compose único `compose.panel.yaml` também teve o build remoto de API, frontend
e MLflow aprovado localmente. A stack foi iniciada a partir dessas imagens;
readiness, login com cookie, bloqueio CSRF e importação/leitura CRM passaram pelo
frontend. A execução na Hostinger ainda depende de colar os arquivos no painel.

O acesso sem `PUBLIC_ORIGIN` foi validado localmente na porta 18088: o Nginx
preserva `Host` com a porta, a API aceita a origem do próprio acesso e rejeita
origens externas. Readiness, login por cookie e importação/leitura CRM passaram
sem `CSRF_TRUSTED_ORIGINS` no ambiente.

A variante de build remoto foi testada localmente, mas o log real do painel
confirmou que esse fluxo não executou o build. O arquivo `compose.panel.yaml`
agora usa somente imagens publicadas e `pull_policy: always`. Preserve o projeto
`servidor2`, o ENV existente e os volumes; atualize apenas `IMAGE_TAG` para a nova
release e substitua o Compose pelo arquivo atual.

Na v4, os 50 testes do frontend passaram. O navegador validou as páginas públicas
com a resposta inicial 401 simulada, reproduzindo o comportamento observado na
VPS: cadastro permanece aberto e páginas privadas redirecionam para login.
Para permitir cadastro, mantenha `REGISTER_ENABLED=1` e acesse
`/cadastro-tor-gestao-interna`. É necessário reimplantar para carregar a imagem nova.
