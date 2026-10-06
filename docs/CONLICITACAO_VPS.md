# ConLicitação na VPS

## IP autorizado

Cadastre o IP público de saída da VPS na ConLicitação. Para a VPS atual, o IP informado é `179.199.133.174`; confirme no próprio servidor antes de cadastrar:

```bash
curl -4 https://api.ipify.org
```

No formulário da ConLicitação, selecione **Servidor em nuvem**. Se a VPS estiver atrás de NAT, proxy ou gateway, use o IP exibido pelo comando, não o IP privado da interface.

## Variáveis de produção

Configure no `.env.prod` da VPS, sem versionar o token:

```dotenv
CONLICITACAO_ENABLED=1
CONLICITACAO_BASE_URL=https://consultaonline.conlicitacao.com.br
CONLICITACAO_TOKEN=<token fornecido pela ConLicitação>
CONLICITACAO_TENANT_IDS=<id numérico da empresa no RagMatch>
```

`CONLICITACAO_TENANT_IDS` aceita IDs separados por vírgula. O mesmo valor precisa chegar à API, ao scheduler e ao `worker-conlicitacao`.

## Subida e validação

Depois de publicar as imagens da versão escolhida:

```bash
export IMAGE_TAG=sha-<commit-publicado>
docker compose --env-file .env.prod -f docker-compose.prod.yaml config --quiet
docker compose --env-file .env.prod -f docker-compose.prod.yaml up -d api frontend worker-conlicitacao scheduler
docker compose --env-file .env.prod -f docker-compose.prod.yaml ps
docker compose --env-file .env.prod -f docker-compose.prod.yaml logs --tail=100 worker-conlicitacao scheduler
```

Entre como administrador e abra `/integracoes/conlicitacao`. A página permite:

- confirmar se integração, token e empresa estão habilitados;
- testar todos os endpoints de leitura disponíveis;
- ver campos, tipos, contagens e latência sem expor valores sensíveis;
- exportar o diagnóstico sanitizado em JSON;
- enfileirar a sincronização com o RagMatch;
- iniciar ou parar um acompanhamento, mediante confirmação explícita.

Uma resposta `401` ou `403` registrada dentro do diagnóstico normalmente indica token incorreto ou IP de saída ainda não autorizado pela ConLicitação. Um item “não executado” não é necessariamente erro: boletim e mensagens dependem de haver filtro, boletim ou licitação acompanhada disponível na conta.
