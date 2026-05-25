import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { crmApi } from '../api/client'
import { useAuth } from '../contexts/AuthContext'

const CRM_BASE = '/crm/'
const CRM_PORTAL_SRC = '/crm/?portal=1'

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
  const { isAdmin } = useAuth()
  const [checking, setChecking] = useState(true)
  const [crmReady, setCrmReady] = useState(false)
  const [buildInfo, setBuildInfo] = useState(null)
  const [frameLoaded, setFrameLoaded] = useState(false)
  const [uploadingSheet, setUploadingSheet] = useState(false)
  const [sheetSummary, setSheetSummary] = useState(null)
  const [sheetError, setSheetError] = useState(null)
  const [showImportPanel, setShowImportPanel] = useState(false)
  const [crmRefreshToken, setCrmRefreshToken] = useState(0)
  const fileInputRef = useRef(null)

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

  async function handleSheetUpload(event) {
    const file = event.target.files?.[0]
    if (!file) return

    setUploadingSheet(true)
    setSheetError(null)
    setSheetSummary(null)

    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await crmApi.importSalesProcesses(formData)
      setSheetSummary(response.data?.summary || null)
      setShowImportPanel(false)
      setFrameLoaded(false)
      setCrmRefreshToken(Date.now())
    } catch (error) {
      setSheetError(error.response?.data?.detail || 'Nao foi possivel importar a planilha agora.')
    } finally {
      setUploadingSheet(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  function resetImportState() {
    setSheetError(null)
    setSheetSummary(null)
    setShowImportPanel(true)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <div className="min-h-screen bg-ink text-white">
      <section className="relative min-h-screen overflow-hidden px-4 py-4 lg:px-6 lg:py-6">
        <div className="absolute inset-0 opacity-70" style={{ backgroundImage: 'radial-gradient(circle at top right, rgba(248,113,113,0.16), transparent 30%), radial-gradient(circle at top left, rgba(56,189,248,0.12), transparent 24%), radial-gradient(circle at bottom left, rgba(220,38,38,0.1), transparent 28%)' }} />
        <div className="relative mx-auto flex max-w-[1680px] flex-col gap-4">
          <div className="rounded-[28px] border border-slate-border bg-ink-100/95 p-5 shadow-2xl shadow-black/30 lg:p-6">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="inline-flex rounded-full border border-azure/30 bg-azure/10 px-3 py-1 text-[11px] font-mono uppercase tracking-[0.24em] text-azure-glow">
                    Modulo Comercial
                  </span>
                  <StatusPill ok={crmReady} label={crmReady ? 'crm online' : 'build pendente'} />
                  <StatusPill ok label="sessao unificada" />
                </div>

                <div>
                  <p className="text-sm font-mono uppercase tracking-[0.3em] text-gray-500">Bid Bunny dentro da linguagem Tor</p>
                  <h1 className="mt-3 font-display text-3xl font-black text-white lg:text-4xl">
                    CRM como parte do site, com a mesma identidade visual e sem cara de app externa
                  </h1>
                  <p className="mt-3 max-w-3xl text-sm leading-7 text-gray-300">
                    Essa entrada agora funciona como uma pagina dedicada do ecossistema Tor. O portal autentica o acesso,
                    o CRM abre com a mesma sessao e a experiencia fica concentrada no modulo comercial.
                  </p>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 xl:w-[420px]">
                <MetaCard label="Ultima sync" value={buildInfo ? formatDate(buildInfo.builtAt) : 'aguardando sincronizacao'} />
                <MetaCard label="Commit CRM" value={commitLabel} hint={buildInfo?.sourceBranch ? `branch ${buildInfo.sourceBranch}` : 'sem branch registrada'} />
                <MetaCard label="Origem" value={buildInfo?.sourceRepo || 'repositorio local bid-buddy'} hint="modulo publicado em /crm/" />
                <MetaCard label="Publicacao" value="Integrada ao portal" hint="mesma sessao, mesma rota e mesmo ambiente operacional" />
              </div>
            </div>

            <div className="mt-5 flex flex-wrap gap-3 border-t border-slate-border pt-4">
              <Link to="/dashboard" className="btn-ghost inline-flex items-center justify-center">
                Voltar ao portal
              </Link>
              <button type="button" className="btn-ghost" onClick={() => window.location.reload()}>
                Atualizar modulo
              </button>
            </div>

            {isAdmin && (
              <div className="mt-5 rounded-[24px] border border-slate-border bg-black/20 p-4">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                  <div>
                    <p className="text-[11px] font-mono uppercase tracking-[0.28em] text-gray-500">Carga comercial</p>
                    <h2 className="mt-2 font-display text-xl font-bold text-white">Importar planilha de processos de vendas para o CRM</h2>
                    <p className="mt-2 max-w-2xl text-sm leading-7 text-gray-400">
                      A planilha XLSX cria ou atualiza editais no tenant da conta logada e fica disponivel tambem em producao.
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-3 xl:justify-end">
                    <button type="button" className="btn-ghost" onClick={() => setShowImportPanel((value) => !value)}>
                      {showImportPanel ? 'Ocultar upload' : 'Importar planilha'}
                    </button>
                    {sheetSummary && (
                      <button type="button" className="btn-ghost" onClick={resetImportState}>
                        Enviar outra planilha
                      </button>
                    )}
                  </div>
                </div>

                {showImportPanel && (
                  <div className="mt-4 rounded-2xl border border-slate-border bg-ink-50 px-4 py-4">
                    <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                      <div>
                        <p className="text-sm font-semibold text-white">Selecione a planilha XLSX da automacao comercial</p>
                        <p className="mt-1 text-xs text-gray-500">O upload atualiza os editais sem recarregar a pagina toda.</p>
                      </div>
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept=".xlsx"
                        className="block text-sm text-gray-300 file:mr-4 file:rounded-xl file:border file:border-azure/20 file:bg-azure/10 file:px-4 file:py-2 file:text-xs file:font-mono file:uppercase file:tracking-[0.18em] file:text-azure-glow"
                        onChange={handleSheetUpload}
                        disabled={uploadingSheet}
                      />
                    </div>
                  </div>
                )}

                {(uploadingSheet || sheetSummary || sheetError) && (
                  <div className="mt-4 rounded-2xl border border-slate-border bg-ink-50 px-4 py-3 text-sm">
                    {uploadingSheet && <p className="text-azure-glow">Importando planilha para o CRM e sincronizando os editais...</p>}
                    {sheetError && <p className="text-red-300">{sheetError}</p>}
                    {sheetSummary && (
                      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                        <p className="text-green-match">
                          Importacao concluida: {sheetSummary.grupos_processados} editais e {sheetSummary.itens_processados} itens para o tenant {sheetSummary.tenant}.
                        </p>
                        <button type="button" className="btn-ghost" onClick={() => setCrmRefreshToken(Date.now())}>
                          Atualizar CRM
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="rounded-[30px] border border-slate-border bg-[#060606] p-3 shadow-2xl shadow-black/40">
            {checking ? (
              <div className="grid h-[calc(100vh-270px)] min-h-[720px] place-items-center rounded-[24px] border border-slate-border bg-ink-50">
                <div className="text-center">
                  <div className="mx-auto h-12 w-12 animate-spin rounded-full border-2 border-azure/25 border-t-azure" />
                  <p className="mt-4 text-sm font-semibold text-white">Validando o modulo comercial</p>
                  <p className="mt-1 text-xs text-gray-500">Checando a rota /crm/ e o ultimo pacote publicado no portal.</p>
                </div>
              </div>
            ) : crmReady ? (
              <div className="relative rounded-[24px] border border-slate-border bg-black/60">
                {!frameLoaded && (
                  <div className="absolute inset-0 z-10 grid place-items-center rounded-[24px] bg-ink-50/95">
                    <div className="text-center">
                      <div className="mx-auto h-10 w-10 animate-spin rounded-full border-2 border-azure/25 border-t-azure" />
                      <p className="mt-4 text-sm font-semibold text-white">Abrindo o Bid Bunny com a sessao do portal</p>
                      <p className="mt-1 text-xs text-gray-500">O CRM esta sendo carregado como modulo interno da Tor.</p>
                    </div>
                  </div>
                )}
                <iframe
                  title="Licita CRM"
                  src={`${CRM_PORTAL_SRC}&refresh=${crmRefreshToken}`}
                  className="h-[calc(100vh-270px)] min-h-[720px] w-full rounded-[24px] bg-transparent"
                  onLoad={() => setFrameLoaded(true)}
                />
              </div>
            ) : (
              <div className="grid h-[calc(100vh-270px)] min-h-[720px] place-items-center rounded-[24px] border border-dashed border-yellow-warn/40 bg-yellow-warn/5 p-8 text-center">
                <div className="max-w-lg">
                  <p className="text-sm font-mono uppercase tracking-[0.3em] text-yellow-warn">Sync necessaria</p>
                  <h2 className="mt-3 font-display text-2xl font-bold text-white">O build do CRM ainda nao foi incorporado ao site principal</h2>
                  <p className="mt-3 text-sm leading-7 text-gray-300">
                    Gere a versao embarcada do <span className="text-white">bid-buddy</span> dentro de
                    <span className="text-white"> frontend/public/crm</span> para publicar o modulo comercial com a identidade da Tor.
                  </p>
                  <pre className="mt-5 overflow-x-auto rounded-2xl border border-slate-border bg-ink px-4 py-4 text-left text-xs text-gray-300">
node ./scripts/sync-bid-buddy.mjs --pull
                  </pre>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
