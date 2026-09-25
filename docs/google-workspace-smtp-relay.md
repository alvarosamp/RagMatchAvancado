# Google Workspace SMTP Relay

O RagMatch envia e-mails transacionais pelo `smtp-relay.gmail.com` com TLS na
porta 587. Em produção, a opção preferida é autenticar pelo IP público fixo da
VPS, sem armazenar senha de usuário Google.

## 1. Dados necessários

- domínio verificado no Google Workspace;
- acesso de administrador com permissão **Configurações do Gmail**;
- IPv4 público fixo da VPS Hostinger;
- remetente no domínio, por exemplo `nao-responda@empresa.com`;
- endereço externo para o primeiro teste.

Não envie senhas pelo chat, issue tracker ou repositório. O relay por IP não usa
`SMTP_USER` nem `SMTP_PASSWORD`.

## 2. Configuração no Google Admin Console

1. Acesse **Apps > Google Workspace > Gmail > Roteamento** na organização de
   nível superior.
2. Em **Serviço de redirecionamento SMTP**, escolha **Configurar**.
3. Nomeie a regra como `RagMatch VPS`.
4. Em **Remetentes permitidos**, selecione **Apenas endereços nos meus domínios**.
   Assim, `nao-responda@...` pode ser um endereço técnico do domínio sem liberar
   remetentes arbitrários.
5. Em **Autenticação**, marque **Aceitar apenas e-mails dos endereços IP
   especificados**, adicione somente o IP público da VPS e mantenha o menor
   intervalo possível (`/32` para um único IPv4).
6. Não marque **Exigir autenticação SMTP** quando usar autenticação por IP.
7. Marque **Exigir criptografia TLS** e salve. A propagação pode levar até 24
   horas, embora normalmente seja mais rápida.

## 3. DNS do domínio

Confirme SPF e DKIM antes do envio. Se o Google Workspace for o único emissor, o
SPF recomendado é `v=spf1 include:_spf.google.com ~all`. Edite o registro SPF
existente; não publique dois registros SPF. Gere a chave DKIM no Admin Console,
publique o TXT informado no DNS e depois ative a autenticação. Após SPF e DKIM
estarem estáveis, implante DMARC gradualmente, começando por `p=none`.

## 4. Variáveis da VPS

No `.env.prod`:

```dotenv
SMTP_HOST=smtp-relay.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=nao-responda@empresa.com
SMTP_USE_TLS=1
SMTP_USE_SSL=0
SMTP_TIMEOUT_SECONDS=15
SMTP_LOCAL_HOSTNAME=api.empresa.com
PASSWORD_RESET_URL_BASE=https://app.empresa.com/redefinir-senha
PASSWORD_RESET_EXPIRE_MINUTES=30
```

O `SMTP_FROM_EMAIL` precisa pertencer a um domínio aceito na regra. O
`SMTP_LOCAL_HOSTNAME` deve ser um nome DNS válido da aplicação, não `localhost`.
Confirme também que a VPS permite conexões TCP de saída na porta 587.

## 5. Aplicação e teste

Recrie a API para carregar as variáveis:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yaml up -d --force-recreate api
```

Envie um teste pelo mesmo código usado pela API:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yaml exec api \
  python scripts/test_smtp.py --to destinatario-externo@exemplo.com
```

Depois, solicite uma redefinição de senha por uma conta de teste. Confira caixa
de entrada, spam, link HTTPS e expiração. Se houver rejeição, consulte os logs da
API e a **Pesquisa de registro de e-mail** no Admin Console. Erros `relay denied`
normalmente indicam IP não autorizado, domínio do remetente divergente ou regra
ainda não propagada.

## 6. Critério para ativação

- envio externo chega com TLS;
- SPF e DKIM aparecem como `PASS` nos cabeçalhos;
- link de redefinição abre o domínio correto e funciona uma única vez;
- nenhum segredo SMTP foi incluído em Git, logs ou mensagens;
- alerta e pesquisa de logs do Google Workspace estão acessíveis aos operadores.
