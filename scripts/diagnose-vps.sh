#!/usr/bin/env bash
# Read-only host inventory. No restart, deploy, cleanup, database query or env dump.
set -uo pipefail
export LC_ALL=C

section() { printf '\n### %s\n' "$1"; }
probe() {
  "$@" 2>&1 || printf 'AVISO: comando indisponivel, sem permissao ou sem resultados (status %s).\n' "$?"
}

section 'Horario UTC e boot atual'
probe date -u
probe uptime
probe uptime -s
probe cat /proc/sys/kernel/random/boot_id
probe last -x -n 25 reboot shutdown

section 'Historico de boots (ausencia pode indicar journal nao persistente)'
probe journalctl --list-boots --no-pager
section 'Kernel: OOM, panic e erros de disco no boot anterior'
probe journalctl -k -b -1 --no-pager -n 120 --grep='[Oo]ut of memory|[Oo]om|[Kk]illed process|[Pp]anic|I/O error|EXT4-fs error|[Ww]atchdog'
section 'Kernel: mesmos eventos no boot atual'
probe journalctl -k -b 0 --no-pager -n 120 --grep='[Oo]ut of memory|[Oo]om|[Kk]illed process|[Pp]anic|I/O error|EXT4-fs error|[Ww]atchdog'
section 'Encerramento do boot anterior'
probe journalctl -b -1 --no-pager -n 80 --grep='[Rr]eboot|[Ss]hutdown|[Pp]ower|[Ww]atchdog'

section 'Memoria, swap e pressao atual'
probe free -h
probe swapon --show
probe cat /proc/pressure/memory
probe vmstat 1 3
section 'Disco e inodes'
probe df -hT
probe df -i

section 'Reinicio automatico por atualizacoes e politica do kernel'
if [[ -f /var/run/reboot-required ]]; then probe cat /var/run/reboot-required; fi
probe grep -R -E '^[[:space:]]*Unattended-Upgrade::Automatic-Reboot' /etc/apt/apt.conf.d
probe sysctl vm.panic_on_oom kernel.panic kernel.panic_on_oops
probe systemctl is-enabled docker
probe systemctl is-active docker
probe systemctl list-timers --all --no-pager

if command -v docker >/dev/null 2>&1; then
  section 'Projetos Compose e containers (inclui parados)'
  probe docker compose ls -a
  probe docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
  section 'Consumo atual dos containers'
  probe docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.PIDs}}'
  section 'Boot/restart, OOM, limites, logging e mounts reais; sem variaveis secretas'
  ids="$(docker ps -aq 2>/dev/null)" || ids=''
  if [[ -n "$ids" ]]; then
    while IFS= read -r id; do
      probe docker inspect --format 'container={{.Name}} image={{.Config.Image}} image_id={{.Image}} project={{index .Config.Labels "com.docker.compose.project"}} service={{index .Config.Labels "com.docker.compose.service"}} started={{.State.StartedAt}} finished={{.State.FinishedAt}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}} restarts={{.RestartCount}} restart_policy={{.HostConfig.RestartPolicy.Name}} memory_limit_bytes={{.HostConfig.Memory}} log_driver={{.HostConfig.LogConfig.Type}} log_options={{json .HostConfig.LogConfig.Config}}{{range .Mounts}}{{printf "\n"}}mount type={{.Type}} name={{.Name}} source={{.Source}} destination={{.Destination}} rw={{.RW}}{{end}}' "$id"
    done <<< "$ids"
  fi
  section 'Volumes existentes; comparar com mounts para localizar bancos antigos'
  probe docker volume ls
fi

section 'Versao Git no diretorio atual; nao consulta rede nem modifica checkout'
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  probe git branch --show-current
  probe git log -5 --format='%h %cs %s'
  printf 'Arquivos rastreados com alteracoes: '
  git status --porcelain --untracked-files=no | wc -l
fi

section 'Arquivos de backup locais (existencia nao comprova restaurabilidade)'
backup_dir="${BACKUP_DIR:-/opt/backups/ragmatch}"
if [[ -d "$backup_dir" ]]; then
  probe find "$backup_dir" -maxdepth 1 -type f -printf '%TY-%Tm-%Td %TH:%TM %s bytes %f\n'
else
  printf 'Diretorio nao encontrado: %s\n' "$backup_dir"
fi
printf '\nColeta concluida. Avisos devem ser resolvidos antes de concluir o diagnostico.\n'
