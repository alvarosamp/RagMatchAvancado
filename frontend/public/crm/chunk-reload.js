const recoveryKey = "ragmatch:crm-chunk-reload";
const recoveryWindowMs = 10_000;
const now = Date.now();
const lastRecovery = Number(window.sessionStorage.getItem(recoveryKey) || 0);

if (!lastRecovery || now - lastRecovery > recoveryWindowMs) {
  window.sessionStorage.setItem(recoveryKey, String(now));
  window.location.reload();
} else {
  console.error("Nao foi possivel recuperar os arquivos atualizados do CRM.");
}

export default function StaleChunkRecovery() {
  return null;
}
