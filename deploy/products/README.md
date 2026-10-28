# Hostinger — branch de inteligência de produtos

Compose exclusivo de `codex/inteligencia-produtos-hostinger`. A stack completa é
baseada na composição completa de produção, com imagens Linux amd64
da aplicação e do CRM fixado no submódulo. Não altera a `main`.

## Pelo painel Docker

1. No **servidor de teste**, crie um projeto `ragmatch-products-test`.
2. Cole `docker-compose.prod.yaml` desta branch no editor do painel.
   `deploy/products/compose.hostinger.yaml` contém a mesma composição.
3. Preencha as variáveis conforme `hostinger.env.example`. Para gerar senhas novas,
   execute `python3 deploy/products/make_env.py`; o arquivo `hostinger.env` é privado
   e não vai para o Git. Se esse arquivo já existir de uma entrega anterior,
   preserve as senhas e acrescente as novas variáveis do exemplo.
4. Defina `PUBLIC_ORIGIN=http://IP_DO_SERVIDOR:8088`, com o IP real do teste, e
   libere a porta 8088 no firewall desse servidor. Para outra porta, ajuste também
   `HTTP_PORT` e `PUBLIC_ORIGIN`.
5. Na primeira instalação com banco vazio, use `ALLOW_EMPTY_DATABASE_BOOTSTRAP=1`.
   Depois da primeira implantação bem-sucedida, volte para `0`.
6. Implante e confira `migrate`, `db-bootstrap` e `initialize`: devem terminar com
   código zero. API saudável libera a inicialização do frontend.

Abra `http://IP_DO_SERVIDOR:8088/login` e entre com `ADMIN_EMAIL` e `ADMIN_PASSWORD`.
A inteligência de produtos fica em `/crm/inteligencia-mercado`.

O modo sem build no painel exige antes a publicação das imagens.
Enquanto a publicação não estiver disponível, use o build pelo terminal abaixo. A tag padrão identifica o build local desta entrega da branch.
Se alterar `IMAGE_TAG`, reconstrua as imagens com o mesmo arquivo de ambiente.
A publicação de imagens e a implantação no painel são etapas distintas.

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
HTTPS, ajuste `PUBLIC_ORIGIN` e `AUTH_COOKIE_SECURE=1`. O Nginx encaminha `/api` e
usa a configuração do frontend da branch, incluindo os cabeçalhos de segurança.

## Build no servidor pelo terminal (sem publicação no Docker Hub)

Clone com `--recurse-submodules --branch codex/inteligencia-produtos-hostinger`.
O Git precisa ter acesso de leitura ao repositório do CRM. Na raiz do clone,
gere o ambiente com `python3 deploy/products/make_env.py`, copie o arquivo gerado
para `.env.prod` e execute `python3 deploy/products/set_origin.py` para informar
a URL do servidor de teste. Esse comando funciona também no macOS/zsh.

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
