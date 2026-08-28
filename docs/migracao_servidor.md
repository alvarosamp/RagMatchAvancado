# Migração segura de servidor

O pacote de migração contém um dump PostgreSQL completo, arquivos persistentes,
objetos do MinIO, planilha XLSX de auditoria e um manifesto com hashes. O dump
PostgreSQL é a fonte oficial de restauração; a planilha é usada para conferência.

## 1. Antes do corte

1. Confirme que a stack antiga está saudável.
2. Faça um primeiro backup de ensaio e valide-o.
3. Copie o pacote para um local externo ao servidor antigo.
4. Restaure-o no servidor novo e teste login, CRM, editais e download de arquivos.
5. Mantenha o servidor antigo ligado até a aprovação final.

## 2. Backup no servidor antigo

Coloque a aplicação em modo somente leitura antes do backup final, para evitar
registros novos durante a cópia. No diretório do projeto, execute:

```bash
docker compose -f docker-compose.prod.yaml run --rm api \
  python scripts/create_migration_bundle.py \
  --output /data/backups/migracao_YYYYMMDD
```

O diretório de saída deve estar vazio. Em seguida, valide a integridade sem
alterar nada:

```bash
docker compose -f docker-compose.prod.yaml run --rm --no-deps api \
  python scripts/restore_migration_bundle.py \
  --mode validate --bundle /data/backups/migracao_YYYYMMDD
```

Copie a pasta completa de `/data/backups/migracao_YYYYMMDD` para fora do
servidor. Não dependa apenas do disco do servidor que será desativado.

## 3. Restauração no servidor novo

1. Suba a stack nova uma vez para criar PostgreSQL, Redis e MinIO.
2. Copie o pacote para `/data/backups/` no novo servidor.
3. Execute a validação do pacote.
4. Faça um backup do banco vazio/de teste do novo servidor, caso precise voltar.
5. Execute a restauração explícita:

```bash
docker compose -f docker-compose.prod.yaml run --rm --no-deps api \
  python scripts/restore_migration_bundle.py \
  --mode restore --confirm-restore \
  --bundle /data/backups/migracao_YYYYMMDD
```

O comando de restauração usa `pg_restore --clean --if-exists`: ele sobrescreve
as tabelas do banco de destino. Por isso exige `--confirm-restore`.

## 4. Critérios de aprovação

- A validação do pacote não apresenta hashes divergentes.
- A conferência pós-restauração informa `database_matches: true`.
- As abas `CRM Editais`, `Editais`, `Requisitos` e `Resultados` em
  `auditoria.xlsx` têm os dados esperados.
- Usuários conseguem entrar, abrir CRM, abrir editais e baixar documentos.
- Um novo upload e matching são concluídos no servidor novo.

Só aponte o domínio para o novo servidor depois desses testes. Preserve o
servidor anterior por pelo menos 14 dias após o corte.
