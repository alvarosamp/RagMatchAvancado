# Hostinger — teste da inteligência de produtos

Este Compose constrói o código da branch `codex/inteligencia-produtos-hostinger`, incluindo
o commit do submódulo CRM. Não usa as imagens antigas da aplicação. A imagem base
da API está fixada por digest público; o frontend compila portal e CRM juntos.
A entrega usa uma branch exclusiva nos dois repositórios, com volumes do projeto
`ragmatch-products-test`.

## No gerenciador Docker da Hostinger

1. Crie um novo projeto chamado **ragmatch-products-test** no outro servidor.
2. Cole o conteúdo de `compose.hostinger.yaml` no editor de Compose.
3. Nas variáveis/arquivo de ambiente, cole o conteúdo do **hostinger.env** entregue
   separadamente. As senhas foram geradas para este teste e não estão no GitHub.
4. Faça o build e a implantação. A primeira construção baixa as dependências.

Se o gerenciador não aceitar build a partir de contexto Git remoto, use o terminal:

```sh
git clone --recurse-submodules --branch codex/inteligencia-produtos-hostinger https://github.com/alvarosamp/RagMatchAvancado.git ragmatch-products-test
cd ragmatch-products-test/deploy/products
# Coloque aqui o hostinger.env entregue, ou gere outro com: python3 make_env.py
export SOURCE_CONTEXT=../..
docker compose --env-file hostinger.env -f compose.hostinger.yaml up -d --build
```

Não reutilize `.env.prod` nem volumes do servidor principal. A API e o PostgreSQL
não publicam portas; somente o frontend publica **8088**. O projeto usa HTTP para
teste por IP. Ao colocar atrás de HTTPS, ajuste `AUTH_COOKIE_SECURE` para `1` no
Compose. O acesso por IP aceita qualquer Host e exige a mesma origem nas chamadas
do navegador; a configuração não é o deploy definitivo para clientes.

## Acessar e testar

- Abra `http://IP_DO_SERVIDOR:8088/login`.
- Entre com `ADMIN_EMAIL` e `ADMIN_PASSWORD` do arquivo de ambiente.
- Se aparecer a solicitação de completar cadastro, preencha ou feche o diálogo.
- Abra `http://IP_DO_SERVIDOR:8088/crm/inteligencia-mercado`.
- A seção **Inteligência de produtos** mostra perfis técnicos, qualidade,
  associação de modelo à marca do catálogo, fontes e exportação.
- `SEED_DEMO=1` cria dois editais e um produto **explicitamente fictícios** para
  você ver a análise imediatamente. Não são dados de mercado nem vendas reais.
  Para começar vazio, mude para `SEED_DEMO=0` antes da primeira implantação.
- Para seus dados, envie os JSONs em `/upload`, com **Somente análise, não
  sincronizar CRM** desmarcado, e cadastre/importe o catálogo no CRM. Marcas por
  modelo dependem do catálogo. Filtre os exemplos `DEMO` separadamente ou
  remova-os pela interface antes de analisar volumes reais.

O ambiente testa a análise implementada: não inclui a consolidação completa de
vendas próprias, o dossiê técnico final para fornecedores ou o workflow externo
n8n. OCR/LLM/Ollama e coleta automática estão desativados; a entrada é por JSON.

## Diagnóstico e preservação

```sh
docker compose --env-file hostinger.env -f compose.hostinger.yaml ps -a
docker compose --env-file hostinger.env -f compose.hostinger.yaml logs --tail=80 initialize api
```

O serviço `initialize` deve terminar com código zero antes da API iniciar. Ele
migra o banco novo, provisiona a conta restrita e cria o administrador. Reexecuções
não trocam senhas existentes nem apagam dados. Para parar, use `docker compose
--env-file hostinger.env -f compose.hostinger.yaml stop`; os dados ficam nos volumes.

Validação desta entrega: builds e testes de aplicação anteriores documentados no
repositório; sintaxe Compose e scripts conferidos separadamente. O Docker Desktop
local estava indisponível ao preparar este deploy. A implantação final precisa
atingir a saúde da API e o login no servidor de teste; não é apresentada como já
executada na Hostinger.
