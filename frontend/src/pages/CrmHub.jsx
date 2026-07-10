import { useEffect, useState } from 'react'

const CRM_BASE = '/crm/'
const CRM_PORTAL_SRC = '/crm/?portal=1'

export default function CrmHub() {
  const [checking, setChecking] = useState(true)
  const [crmReady, setCrmReady] = useState(false)
  const [frameLoaded, setFrameLoaded] = useState(false)

  useEffect(() => {
    let active = true

    async function loadState() {
      setChecking(true)
      try {
        const response = await fetch(`${CRM_BASE}index.html`, { cache: 'no-store' })
        if (active) setCrmReady(response.ok)
      } catch {
        if (active) setCrmReady(false)
      } finally {
        if (active) setChecking(false)
      }
    }

    loadState()
    return () => {
      active = false
    }
  }, [])

  return (
    <div className="min-h-screen bg-[#f6f1ea] text-slate-950 dark:bg-surface-dark dark:text-white">
      <section className="relative h-screen overflow-hidden">
        {checking ? (
          <div className="grid h-full place-items-center">
            <div className="text-center">
              <div className="mx-auto h-10 w-10 animate-spin rounded-full border-2 border-red-200 border-t-red-700 dark:border-red-600/25 dark:border-t-red-600" />
              <p className="mt-4 text-sm font-semibold">Carregando CRM...</p>
            </div>
          </div>
        ) : crmReady ? (
          <div className="relative h-full">
            {!frameLoaded && (
              <div className="absolute inset-0 z-10 grid place-items-center bg-white/95 dark:bg-slate-900/95">
                <div className="text-center">
                  <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-red-200 border-t-red-700 dark:border-red-600/25 dark:border-t-red-600" />
                  <p className="mt-3 text-sm font-semibold">Abrindo CRM...</p>
                </div>
              </div>
            )}
            <iframe
              title="CRM de Licitacoes"
              src={CRM_PORTAL_SRC}
              className="h-full w-full border-none bg-transparent"
              onLoad={() => setFrameLoaded(true)}
            />
          </div>
        ) : (
          <div className="grid h-full place-items-center p-6 text-center">
            <div className="max-w-md rounded-lg border border-dashed border-yellow-300 bg-yellow-50 p-8 dark:border-yellow-warn/30 dark:bg-yellow-warn/5">
              <p className="text-xs uppercase tracking-wide text-yellow-warn">Indisponivel</p>
              <h1 className="mt-2 text-xl font-bold">CRM nao esta carregado</h1>
              <p className="mt-2 text-sm leading-7 text-slate-600 dark:text-slate-300">
                O modulo do CRM ainda nao foi sincronizado neste ambiente.
              </p>
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
