# WhatsApp com Evolution API gratuita

Esta integração usa uma instalação própria da Evolution API v2 e conexão
`WHATSAPP-BAILEYS`. Não requer API oficial da Meta nem chamadas de IA paga.
A máquina ou VPS que hospeda a Evolution continua sendo responsabilidade do operador.
O provedor é identificado em Configurações, conforme a licença da Evolution.

## Funcionalidades desta versão

- Configurações → WhatsApp: vínculo individual, teste, resumo diário opcional e desvinculação.
- O usuário autenticado gera um código aleatório de uso único, válido por dez minutos.
  Ele envia a mensagem pronta a partir do próprio WhatsApp para provar o vínculo.
  O cadastro de telefone do perfil, sozinho, nunca concede acesso.
- `RESUMO`: totais de editais no CRM da empresa e resultados pendentes.
- `EDITAIS`: últimos cinco editais cadastrados no CRM e suas etapas.
- `PRAZOS`: até cinco próximas sessões pendentes nos sete dias seguintes,
  com horário de Brasília. Usa a data da sessão cadastrada no CRM.
- `AJUDA`: lista os comandos. `PARAR` desativa resumos, `VOLTAR` autoriza-os
  e `DESVINCULAR` remove o acesso.
- O scheduler envia um resumo por usuário/dia após 9h de Brasília, somente
  com consentimento explícito. O horário pode ser alterado pelo operador.

O atendimento usa comandos e consultas diretas ao banco. Perguntas livres sobre
documentos, áudio, avisos imediatos de novos editais e alertas individuais por evento
não fazem parte desta primeira versão. Nenhum modelo pago é chamado.

## Ativação

### Sem uma Evolution instalada: arquivos preparados para a VPS

O arquivo `deploy/docker-compose.evolution.yml` acrescenta Evolution v2.3.7,
PostgreSQL e Redis próprios à rede `app-internal` da configuração de produção.
A imagem está fixada na versão estável indicada pelo
[exemplo oficial de implantação](https://github.com/evolution-foundation/evolution-api/blob/main/Docker/swarm/evolution_api_v2.yaml).
O banco e as sessões têm volumes persistentes; inclua-os nos backups da VPS.
Use esse arquivo somente junto da base de produção, que define essa rede.

Além das variáveis abaixo, defina `EVOLUTION_DB_PASSWORD` com uma senha aleatória
hexadecimal (evita caracteres que precisam de escape na URL PostgreSQL).
Gere três valores independentes para essa senha, a chave da API e o segredo do
webhook. Confira se a porta local 8080 está livre na VPS.

```sh
docker compose --env-file .env.prod \
  -f docker-compose.prod.yaml \
  -f deploy/docker-compose.whatsapp.yml \
  -f deploy/docker-compose.evolution.yml \
  config --quiet

docker compose --env-file .env.prod \
  -f docker-compose.prod.yaml \
  -f deploy/docker-compose.whatsapp.yml \
  -f deploy/docker-compose.evolution.yml \
  up -d evolution-db evolution-redis evolution
```

Depois de publicar as novas imagens e migrar o banco do RagMatch, suba também
API e scheduler com os três arquivos. O terceiro arquivo define a URL interna
`http://evolution:8080`; o webhook pode usar `http://api:8000/integrations/whatsapp/webhook`.
Para abrir o gerenciador pelo computador, crie um túnel:
`ssh -L 8080:127.0.0.1:8080 USUARIO@SUA-VPS`, então abra
`http://localhost:8080/manager`. O número é conectado pelo QR Code ali.
Os serviços ainda não foram instalados ou iniciados na VPS.

Ao atualizar o processo de deploy existente, preserve os dois overlays nas
próximas recriações da API e scheduler; sem eles, essas variáveis não serão
passadas aos containers. As instruções abaixo também atendem instalações externas.

### Configuração da instância e do portal

1. Instale a Evolution v2 em ambiente próprio com PostgreSQL e Redis, seguindo
   o [guia oficial](https://github.com/evolution-foundation/docs-evolution/blob/main/v2/en/install/docker.mdx).
   Use uma versão estável com suporte a cabeçalhos personalizados em webhooks;
   confira a licença da versão instalada. Não contrate Evolution Cloud ou Meta Cloud API.
2. No gerenciador da Evolution, crie a instância `ragmatch` com integração
   `WHATSAPP-BAILEYS` e conecte o número do atendimento pelo QR Code.
3. Copie as variáveis de `.env.whatsapp.example` para o ambiente de implantação.
   Defina a URL acessível **de dentro dos containers** da API e scheduler,
   a chave da Evolution, o nome da instância e o número conectado (DDI + DDD + número).
   Gere um segredo aleatório exclusivo para o webhook, por exemplo com
   `python3 -c 'import secrets; print(secrets.token_hex(32))'`.
   Em Linux, `host.docker.internal` pode exigir configuração adicional;
   prefira o DNS interno da Evolution em uma rede compartilhada.
4. Execute a migração com as credenciais habituais de migração:
   `cd backend && alembic upgrade head`. Em desenvolvimento, o `init_db`
   também conhece as novas tabelas. Em produção, use novas imagens da API,
   scheduler e frontend contendo esta alteração antes de ativar.
5. Ao iniciar o Compose, acrescente o overlay:
   `docker compose --env-file .env.prod -f docker-compose.prod.yaml -f deploy/docker-compose.whatsapp.yml up -d`.
   Esse comando é uma instrução de implantação; não foi executado automaticamente.
   Para desenvolvimento, substitua o arquivo base pelo usado no seu ambiente.
   O overlay passa as variáveis apenas para API e scheduler; não instala a Evolution.
6. Na instância da Evolution, configure o webhook (contrato v2
   `POST /webhook/set/ragmatch`):

   ```json
   {
     "webhook": {
       "enabled": true,
       "url": "https://SEU-PORTAL/api/integrations/whatsapp/webhook",
       "byEvents": false,
       "base64": false,
       "headers": {"x-webhook-secret": "SEGREDO-DEFINIDO-NO-AMBIENTE"},
       "events": ["MESSAGES_UPSERT"]
     }
   }
   ```

   Se os dois serviços compartilham a rede interna, a URL pode ser
   `http://api:8000/integrations/whatsapp/webhook`, sem o prefixo do proxy `/api`.
   Confirme que a Evolution realmente consegue alcançar essa URL e envia o
   cabeçalho. O backend rejeita webhooks sem segredo; não o coloque na query string.
7. Defina `EVOLUTION_ENABLED=1` e reinicie API e scheduler com as variáveis.
   Em Configurações, clique em **Vincular meu WhatsApp**, envie a mensagem pronta
   e clique em **Já enviei, verificar vínculo**. Depois, envie `RESUMO`, `EDITAIS`
   e `PRAZOS`. Ative o resumo diário apenas se quiser recebê-lo.

## Isolamento e entrega

O webhook identifica o usuário pelo vínculo confirmado e confere usuário ativo,
empresa ativa, versão de autenticação e empresa original do vínculo. Mudança de
senha que revogue sessões ou mudança de empresa exige novo vínculo. Em seguida,
configura o contexto RLS e filtra as consultas pelo `tenant_id` do usuário.
Um telefone só pode estar vinculado a uma conta por vez.

As tabelas `whatsapp_contacts` e `whatsapp_deliveries` são uma ponte de identidade,
como os tokens de recuperação de senha: precisam ser acessíveis antes de descobrir
o tenant. Não contêm textos das mensagens nem dados de editais. As rotas de conta
filtram pelo usuário autenticado. As tabelas de negócio mantêm seu RLS existente.

Grupos, status, mensagens próprias e eventos antigos são ignorados. Esta versão
exige uma identidade `numero@s.whatsapp.net` no remetente ou em `remoteJidAlt`
quando o remetente é um LID direto. Eventos com apenas LID são ignorados;
a instalação precisa fornecer a identidade de telefone antes de ativar.
Não se deduz um número a partir dos dígitos de um LID.

Há deduplicação persistente e intervalo mínimo entre comandos. Cada mensagem
recebida e resumo diário tem **no máximo uma tentativa de resposta/envio**.
Uma falha ou timeout não é reenviado automaticamente, evitando duplicatas quando
o provedor aceita a mensagem mas perde a resposta. Isso pode perder um envio;
não há garantia de entrega, fila de reenvio ou confirmação de leitura. O endpoint
de webhook retorna `send_failed` quando detecta falha do provedor. O scheduler
registra a falha sem conteúdo ou credenciais. A deduplicação é conservada por
14 dias e limpa pelo scheduler com a integração configurada.

## Validação

Os testes usam SQLAlchemy real com SQLite e simulam somente o transporte da
Evolution. Execute-os separadamente dos testes antigos, cujo conftest substitui
SQLAlchemy por mocks:

```sh
PYTHONPATH=backend pytest backend/tests/test_evolution.py -q
cd frontend
npm test -- src/components/WhatsAppSettings.test.jsx
npm run build
```

SQLite não valida RLS ou locks concorrentes do PostgreSQL. Antes de colocar em
produção, conclua o teste com duas empresas, um número conectado e o scheduler
real. Baileys depende do WhatsApp Web: quedas de sessão e mudanças no protocolo
podem interromper o serviço.

Referências do contrato: [OpenAPI v2 oficial](https://github.com/evolution-foundation/docs-evolution/blob/main/openapi/openapi-v2.json)
e [licença da Evolution](https://github.com/evolution-foundation/evolution-api/blob/main/LICENSE).
