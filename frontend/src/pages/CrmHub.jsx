import { useEffect, useMemo, useState } from 'react'

const CRM_BASE = '/crm/'

function formatDate(value) {
  if (!value) return 'sincronizacao pendente'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'sincronizacao pendente'
  return date.toLocaleString('pt-BR')
}

function MetaCard({ label, value, hint }) {
  return (
    <div className="rounded-2xl border border-slate-border bg-ink-50/80 p-4">
      <p className="text-[11px] font-mono uppercase tracking-[0.28em] text-gray-500">{label}</p>
      <p className="mt-2 text-sm font-semibold text-white">{value}</p>
      {hint && <p className="mt-1 text-xs text-gray-500">{hint}</p>}
    </div>
  )
}

function StatusPill({ ok, label }) {
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-mono uppercase tracking-[0.2em] ${
        ok
          ? 'border-green-match/30 bg-green-match/10 text-green-match'
          : 'border-yellow-warn/30 bg-yellow-warn/10 text-yellow-warn'
      }`}
    >
      <span className={`h-2 w-2 rounded-full ${ok ? 'bg-green-match' : 'bg-yellow-warn'}`} />
      {label}
    </span>
  )
}

export default function CrmHub() {
  const [checking, setChecking] = useState(true)
  const [crmReady, setCrmReady] = useState(false)
  const [buildInfo, setBuildInfo] = useState(null)
  const [frameLoaded, setFrameLoaded] = useState(false)

  useEffect(() => {
    let active = true

    async function loadState() {
      setChecking(true)
      try {
        const [indexResponse, infoResponse] = await Promise.allSettled([
          fetch(`${CRM_BASE}index.html`, { cache: 'no-store' }),
          fetch(`${CRM_BASE}tor-sync.json?ts=${Date.now()}`, { cache: 'no-store' }),
        ])

        if (!active) return

        const hasIndex = indexResponse.status === 'fulfilled' && indexResponse.value.ok
        setCrmReady(hasIndex)

        if (infoResponse.status === 'fulfilled' && infoResponse.value.ok) {
          const info = await infoResponse.value.json()
          if (active) setBuildInfo(info)
        } else {
          setBuildInfo(null)
        }
      } catch {
        if (!active) return
        setCrmReady(false)
        setBuildInfo(null)
      } finally {
        if (active) setChecking(false)
      }
    }

    loadState()
    return () => {
      active = false
    }
  }, [])

  const commitLabel = useMemo(() => {
    if (!buildInfo?.sourceCommit) return 'nao informado'
    return buildInfo.sourceCommit.slice(0, 7)
  }, [buildInfo])

  return (
    <div className="p-6 lg:p-8 space-y-6">
      <section className="relative overflow-hidden rounded-[28px] border border-slate-border bg-gradient-to-br from-ink-100 via-[#160d0d] to-[#2b1111] p-6 lg:p-8">
        <div className="absolute inset-0 opacity-70" style={{ backgroundImage: 'radial-gradient(circle at top right, rgba(248,113,113,0.18), transparent 32%), radial-gradient(circle at bottom left, rgba(220,38,38,0.12), transparent 30%)' }} />
        <div className="relative grid gap-6 xl:grid-cols-[minmax(0,360px),1fr]">
          <div className="space-y-5">
            <div className="inline-flex rounded-full border border-azure/30 bg-azure/10 px-3 py-1 text-[11px] font-mono uppercase tracking-[0.24em] text-azure-glow">
              CRM Integrado
            </div>
            <div>
              <p className="text-sm font-mono uppercase tracking-[0.3em] text-gray-500">Bid Buddy dentro da Tor</p>
              <h1 className="mt-3 font-display text-3xl font-black text-white lg:text-4xl">Painel comercial e operacional em uma rota dedicada</h1>
              <p className="mt-3 max-w-xl text-sm leading-7 text-gray-300">
                O CRM continua separado do frontend principal, mas agora pode ser publicado dentro do site da Tor em <span className="text-white">/crm/</span>, com sincronizacao e build controlados.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <StatusPill ok={crmReady} label={crmReady ? 'build disponivel' : 'build pendente'} />
              <StatusPill ok={Boolean(buildInfo?.sourceCommit)} label={buildInfo?.sourceCommit ? 'repo identificado' : 'repo local'} />
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <MetaCard label="Ultima sync" value={buildInfo ? formatDate(buildInfo.builtAt) : 'aguardando primeira sincronizacao'} />
              <MetaCard label="Commit CRM" value={commitLabel} hint={buildInfo?.sourceBranch ? `branch ${buildInfo.sourceBranch}` : 'sem branch registrada'} />
              <MetaCard label="Origem" value={buildInfo?.sourceRepo || 'repositorio local bid-buddy'} hint="mantido separado do frontend principal" />
              <MetaCard label="Creditos" value="Alvaro Sampaio" hint="creditos exibidos em todo o portal" />
            </div>

            <div className="flex flex-wrap gap-3">
              <a
                href={CRM_BASE}
                target="_blank"
                rel="noreferrer"
                className="btn-primary inline-flex items-center justify-center"
              >
                Abrir CRM em tela cheia
              </a>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => window.location.reload()}
              >
                Atualizar status
              </button>
            </div>
          </div>

          <div className="rounded-[24px] border border-slate-border bg-[#060606] p-3 shadow-2xl shadow-black/30">
            {checking ? (
              <div className="grid min-h-[720px] place-items-center rounded-[20px] border border-slate-border bg-ink-50">
                <div className="text-center">
                  <div className="mx-auto h-12 w-12 animate-spin rounded-full border-2 border-azure/25 border-t-azure" />
                  <p className="mt-4 text-sm font-semibold text-white">Validando build do CRM</p>
                  <p className="mt-1 text-xs text-gray-500">Checando a rota /crm/ e os metadados da ultima sincronizacao.</p>
                </div>
              </div>
            ) : crmReady ? (
              <div className="relative rounded-[20px] border border-slate-border bg-black/50">
                {!frameLoaded && (
                  <div className="absolute inset-0 z-10 grid place-items-center rounded-[20px] bg-ink-50/95">
                    <div className="text-center">
                      <div className="mx-auto h-10 w-10 animate-spin rounded-full border-2 border-azure/25 border-t-azure" />
                      <p className="mt-4 text-sm font-semibold text-white">Carregando o CRM embarcado</p>
                      <p className="mt-1 text-xs text-gray-500">A aplicacao do Bid Buddy esta sendo aberta dentro do portal.</p>
                    </div>
                  </div>
                )}
                <iframe
                  title="Licita CRM"
                  src={CRM_BASE}
                  className="min-h-[720px] w-full rounded-[20px] bg-white"
                  onLoad={() => setFrameLoaded(true)}
                />
              </div>
            ) : (
              <div className="grid min-h-[720px] place-items-center rounded-[20px] border border-dashed border-yellow-warn/40 bg-yellow-warn/5 p-8 text-center">
                <div className="max-w-lg">
                  <p className="text-sm font-mono uppercase tracking-[0.3em] text-yellow-warn">Sync necessaria</p>
                  <h2 className="mt-3 font-display text-2xl font-bold text-white">O build do CRM ainda nao foi copiado para o frontend principal</h2>
                  <p className="mt-3 text-sm leading-7 text-gray-300">
                    Rode o script de sincronizacao para gerar a versao embarcada do <span className="text-white">bid-buddy</span> dentro da pasta <span className="text-white">frontend/public/crm</span>.
                  </p>
                  <pre className="mt-5 overflow-x-auto rounded-2xl border border-slate-border bg-ink px-4 py-4 text-left text-xs text-gray-300">
node ./scripts/sync-bid-buddy.mjs --pull
                  </pre>
                  <p className="mt-4 text-xs text-gray-500">
                    Depois disso, o CRM passa a responder pela rota <span className="text-white">/crm/</span> dentro do site da Tor.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
