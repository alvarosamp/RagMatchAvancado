# Hostinger — teste da Evolution API

Branch: `codex/evolution-whatsapp`. Tag das imagens do sistema:
`evolution-hostinger-20261028-v1`. Somente ambiente de teste; sem deploy automático.

## No painel Docker da VPS de teste

1. Para um projeto novo, use `ragmatch-evolution-test`. Para atualizar o projeto
   de teste que já existe, preserve seu nome, volumes e credenciais de banco,
   usuário de aplicação, storage e administrador. Nunca use o projeto da produção.
2. Cole **todo** o arquivo `deploy/evolution/compose.panel.yaml` no editor.
   É um Compose único, sem build, checkout, arquivos extras ou volumes de código.
3. Cole a lista de `deploy/evolution/hostinger.env.example` no ambiente do painel.
   Troque os marcadores por senhas/chaves próprias. A variável `IMAGE_TAG` é
   `evolution-hostinger-20261028-v1`.
4. Defina `EVOLUTION_BOT_PHONE` com o número de atendimento que conectará ao
   WhatsApp: DDI + DDD + número, somente dígitos. Não é o telefone de cada cliente.
5. Em banco novo, use `ALLOW_EMPTY_DATABASE_BOOTSTRAP=1` na primeira instalação;
   depois do sucesso, altere para `0`. Se atualizar um banco de teste existente,
   use `0` e preserve as credenciais atuais. Deixe `OLLAMA_PULL_MODELS=0` para
   testar WhatsApp por comandos sem baixar modelos nem usar IA paga.
6. Implante. O painel baixa as imagens e executa a migração, provisiona o usuário
   restrito e inicializa o administrador. A Evolution usa PostgreSQL/Redis próprios.
   `evolution-setup` cria a instância Baileys e configura o webhook com segredo;
   deve terminar com código zero. Ele pode tentar novamente por até três minutos
   enquanto a Evolution inicia; se ela precisar de mais tempo, reexecute esse serviço.

## Acessos

- Sistema: `http://IP_DA_VPS:8088/login`, com `ADMIN_EMAIL` e `ADMIN_PASSWORD`.
- Evolution Manager: `http://IP_DA_VPS:8090/manager`.
- No login do Manager, use como URL da API `http://IP_DA_VPS:8090` e a chave
  `EVOLUTION_API_KEY` definida no ambiente. Abra a instância `ragmatch` e leia
  o QR Code pelo WhatsApp do número de atendimento.
- No sistema, entre em Configurações → WhatsApp → Vincular meu WhatsApp.
  Envie a mensagem pronta do seu telefone de usuário para o número de atendimento,
  então clique em “Já enviei, verificar vínculo”. Teste `RESUMO`, `EDITAIS` e `PRAZOS`.
- Ative o resumo diário se quiser recebê-lo. `PARAR` cancela os resumos.

O Manager usa a porta 8090 e o portal usa 8088; libere essas portas na VPS de teste.
Esse acesso direto por IP é destinado a teste. Para produção, o Manager deve ficar
atrás de HTTPS/controle de acesso e o portal deve usar cookie seguro.

## Publicação e retorno

API, frontend e MLflow compartilham a tag da branch. Workers, scheduler e
inicializadores reutilizam a imagem da API. MLflow é o mesmo runtime já validado
na v4; o CRM também preserva o bundle privado já publicado na v4.
A imagem da Evolution é a upstream `evoapicloud/evolution-api:v2.3.7`.

Os volumes de Evolution são persistentes. Reimplantar com os mesmos nomes não
apaga a sessão. Não execute `down --volumes` em uma instalação que deseja manter.
Antes de promover para produção, valide o QR Code, envio/recebimento real,
isolamento entre duas empresas e o resumo diário com dados de teste.

Para atualizar a composição gerada após alterar os overlays:
`python deploy/evolution/generate_compose.py` (requer PyYAML). O painel não precisa
executar esse script; o arquivo resultante já está pronto para colar.
