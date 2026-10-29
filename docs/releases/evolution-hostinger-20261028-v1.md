# Evolution — imagem de teste para Hostinger

Branch: `codex/evolution-whatsapp`.
Fonte das imagens API/frontend: `a976bb22a67543ef6832402e3ead447b0ae72878`.
Tag publicada: `evolution-hostinger-20261028-v1`.

**Status: três imagens publicadas no Docker Hub em 29/10/2026, após autorização
explícita do usuário para os repositórios públicos. Digests remotos verificados.**
Os digests estão em `evolution-hostinger-20261028-v1.json`. A publicação não
executou implantação em nenhuma VPS.

No painel da VPS de teste, informe:

```env
IMAGE_TAG=evolution-hostinger-20261028-v1
```

Use o Compose único e a lista de variáveis abaixo. Se atualizar o mesmo projeto
de teste, preserve as credenciais e volumes existentes. Preencha o número de
atendimento em `EVOLUTION_BOT_PHONE`; após a implantação, conecte esse número
pelo QR Code em `http://IP_DA_VPS:8090/manager`.

Arquivos para o painel:

- `deploy/evolution/compose.panel.yaml`: composição única, somente pull.
- `deploy/evolution/hostinger.env.example`: lista de variáveis, sem credenciais reais.
- `deploy/evolution/README.md`: portas, QR Code e sequência de instalação.

Imagens de destino:

- `alvarocareli/ragmatch-api:evolution-hostinger-20261028-v1`
- `alvarocareli/ragmatch-frontend:evolution-hostinger-20261028-v1`
- `alvarocareli/ragmatch-mlflow:evolution-hostinger-20261028-v1`

Validação local concluída:

- 13 testes da integração backend e 4 testes do frontend dentro do build Linux.
- Build da API e do frontend em Linux amd64; imports e Alembic head `20261028_01`.
- PostgreSQL vazio → snapshot → migração → provisionamento de conta restrita →
  inicialização do administrador → API saudável, com validação RLS ativa.
- Login, cookie, proteção de origem, importação JSON fictícia e leitura no CRM
  pelo proxy Nginx com usuário de banco restrito.
- Geração e cancelamento de vínculo, rejeição de webhook sem segredo e descarte
  de eventos não suportados através dos endpoints reais.
- Evolution upstream v2.3.7, Manager acessível, criação da instância Baileys e
  webhook persistido com segredo; nova execução do configurador preservou a instância.

O teste de navegador não foi concluído porque o container de QA disponível não
contém o executável Chromium esperado. A tela tem testes de componente e build
aprovados. Dois testes históricos sobre o Compose de produção falham também na
base anterior (host opcional e download de Ollama); esses arquivos não foram
alterados nesta release. O teste específico do bootstrap passou.

Nenhum número foi conectado e nenhuma mensagem real foi enviada. O operador
precisa conectar seu número pelo QR Code na VPS e concluir os testes reais.
Nenhuma VPS, produção ou tag de produção foi alterada.
