# Auditoria de reinicios e preservacao do CRM

Verificacao local e remota do Git em 07/10/2026. A VPS ainda nao foi acessada;
nenhuma causa de reinicio foi confirmada e nenhuma mudanca foi implantada.

## Versoes verificadas

- RagMatch `origin/main`: `c40337d4a0068753cd075a63d55645449ef993b9`, 28/09/2026.
- Branch local `codex/conlicitacao-fases-1-2`: `909ab65c17fa97d0f8c789965a5c5d1d2b9903ec`, sete commits a frente de main, nenhum atras.
- CRM `bid-buddy`, main local e remoto: `82384b47d245c557f78fa2686bb9c493641e9867`.
- Ha alteracoes locais no backend, no codigo-fonte e build do CRM e em dependencias.
  Nao sobrescrever com checkout/reset/clean nem sincronizar o build automaticamente.
- Git instalado: `2.53.0.windows.2`. Este registro confere commits do projeto;
  nao afirma que essa seja a ultima versao do programa Git.
- A imagem realmente implantada na VPS ainda precisa ser conferida.

## Riscos observados no repositorio

1. `docker-compose.prod.yaml` nao define limites de memoria ou rotacao de logs.
   Ollama, API e workers compartilham os recursos do host. Isso pode causar pressao
   de memoria ou disco; OOM sozinho nao prova reinicio da maquina inteira.
2. Banco, Redis e MinIO usam volumes nomeados e os servicos permanentes usam
   `restart: unless-stopped`. Um reboot simples nao deveria apagar esses volumes.
   O nome do projeto Compose nao esta fixado: mudar diretorio/projeto pode conectar
   a stack a volumes novos, aparentando perda de dados. Conferir os mounts reais
   antes de fixar nomes; nao criar nem substituir volumes para corrigir isso.
3. `scripts/backup-production.sh` cobre PostgreSQL e MinIO, mas nao os bind mounts
   `./data` e `TOR_DOCUMENTS_HOST_PATH` nem MLflow. Documentos locais podem ficar
   fora da copia. E preciso mapear o armazenamento ativo para ampliar a cobertura.
4. A existencia do script de backup nao comprova agendamento, sucesso da copia
   externa ou restaurabilidade. A copia tar do MinIO em uso tambem exige um
   procedimento de consistencia validado em teste de restauracao.
5. O deploy executa migrations e `up --remove-orphans`, sem exigir backup recente
   no proprio script. Compartilhar o mesmo projeto Compose com outro CRM pode
   fazer containers desse CRM serem tratados como orfaos.

## Coleta segura na VPS

No diretorio da stack, execute o script deste repositorio atualizado (ou copie
somente o script, sem fazer deploy). Ele nao depende do Compose local nem de .env:

```bash
sudo bash scripts/diagnose-vps.sh
```

Para salvar o relatorio com acesso restrito:

```bash
umask 077
sudo bash scripts/diagnose-vps.sh > "$HOME/vps-diagnostico-$(date -u +%Y%m%dT%H%M%SZ).txt" 2>&1
```

O script nao reinicia servicos, nao instala pacotes, nao executa migrations, nao
remove dados e nao mostra variaveis de ambiente ou registros de clientes. A saida
contem metadados internos de infraestrutura: compartilhar apenas por canal privado.
Sem privilegios, alguns dados podem ficar indisponiveis. O codigo de saida final
nao certifica que todos os comandos tiveram sucesso; conferir os avisos.

Cruzar boots com horarios dos incidentes e hPanel. Novo boot ID/uptime confirma
reinicio do host; apenas StartedAt/RestartCount alterados pode ser restart de
container. `OOMKilled` pode perder historico ao recriar o container; por isso
tambem se consultam eventos de kernel. Journal sem boot anterior deixa o historico
inconclusivo; preparar persistencia e limites de journal depois de verificar disco.

## Ordem das correcoes apos obter evidencia

1. Identificar qual banco e quais volumes contem o CRM atual, confirmar mounts e
   versoes; mapear arquivos locais e conferir se houve perda real ou troca de base.
2. Criar copia externa consistente dos dados e documentos, guardar configuracao
   com protecao de segredos e testar restore em ambiente isolado. Snapshot no hPanel
   complementa essa protecao. Nao restaurar sobre o banco de producao para testar.
3. Conforme RAM/disco medidos, dimensionar IA, concorrencia, limites por servico e
   rotacao de logs, preservando capacidade para PostgreSQL e o CRM. Nao aplicar
   numeros genericos nem desligar servicos sem verificar dependencias.
4. Preservar a identidade atual do projeto/volumes e separar stacks que compartilhem
   indevidamente o projeto. Qualquer mudanca deve reutilizar os dados identificados.
5. Conferir Docker no boot, backups agendados, alertas e politicas de atualizacao.
   Atualizar codigo/imagens somente com backup validado e plano de rollback que
   considere migrations; voltar imagem nao reverte o esquema do banco.

Nao usar `docker compose down -v`, `docker volume prune`, `docker system prune
--volumes` ou reinstalacao da VPS como tentativa de corrigir o incidente.

Referencias: https://docs.docker.com/compose/how-tos/project-name/ e
https://docs.docker.com/reference/compose-file/volumes/.
