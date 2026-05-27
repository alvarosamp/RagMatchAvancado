import { useEffect, useMemo, useRef, useState } from 'react'
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

export default function CrmHub() {
  const { isAdmin } = useAuth()
  const [checking, setChecking] = useState(true)
  const [crmReady, setCrmReady] = useState(false)
  const [buildInfo, setBuildInfo] = useState(null)
  const [frameLoaded, setFrameLoaded] = useState(false)
  const [uploadingSheet, setUploadingSheet] = useState(false)
  const [sheetSummary, setSheetSummary] = useState(null)
  const [sheetError, setSheetError] = useState(null)
  const [showImportModal, setShowImportModal] = useState(false)
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

  const lastSyncLabel = useMemo(() => {
    return buildInfo ? formatDate(buildInfo.builtAt) : 'sincronizacao pendente'
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
      setShowImportModal(false)
      setFrameLoaded(false)
      setCrmRefreshToken(Date.now())
    } catch (error) {
      setSheetError(error.response?.data?.detail || 'Nao foi possivel importar a planilha agora.')
    } finally {
      setUploadingSheet(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  function openImport() {
    setSheetError(null)
    setSheetSummary(null)
    setShowImportModal(true)
  }

  function resetImportState() {
    setSheetError(null)
    setSheetSummary(null)
    setShowImportModal(true)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <div className="min-h-screen bg-ink text-white">
      <section className="relative h-screen flex flex-col overflow-hidden px-4 py-4 lg:px-6 lg:py-6">
        <div
          className="absolute inset-0 opacity-70"
          style={{
            backgroundImage:
              'radial-gradient(circle at top right, rgba(248,113,113,0.14), transparent 32%), radial-gradient(circle at top left, rgba(56,189,248,0.10), transparent 26%), radial-gradient(circle at bottom left, rgba(220,38,38,0.08), transparent 30%)',
          }}
        />

        <div className="relative mx-auto flex w-full max-w-[1680px] flex-1 flex-col gap-3 min-h-0">
          <div className="rounded-2xl border border-slate-border bg-ink-100/90 p-4 shadow-xl backdrop-blur-md">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <h1 className="text-lg font-black tracking-tight text-white">CRM de Licitacoes</h1>
                <p className="mt-1 text-sm text-gray-300 leading-relaxed max-w-2xl">
                  Gestao de oportunidades, monitoramento de disputas e operacao comercial por item.
                </p>
              </div>

              <div className="flex items-center gap-2 flex-wrap sm:justify-end">
                {isAdmin && (
                  <button
                    type="button"
                    className="btn-primary rounded-full px-4 py-2 text-xs font-semibold"
                    onClick={openImport}
                    disabled={!crmReady}
                    title={!crmReady ? 'CRM ainda nao esta disponivel.' : 'Importar planilha de processos.'}
                  >
                    Importar processos
                  </button>
                )}
                <button
                  type="button"
                  className="btn-ghost rounded-full px-4 py-2 text-xs font-semibold"
                  onClick={() => setCrmRefreshToken(Date.now())}
                  disabled={!crmReady}
                >
                  Atualizar
                </button>
              </div>
            </div>

            <details className="mt-3 group rounded-xl border border-slate-border/60 bg-ink-50/40 px-4 py-3">
              <summary className="flex items-center gap-2 text-xs text-gray-300 transition-colors cursor-pointer select-none">
                <span className="transition-transform group-open:rotate-90">▸</span>
                Info do ambiente
              </summary>
              <div className="mt-3 grid gap-3 grid-cols-2 sm:grid-cols-4 text-left">
                <div className="rounded-xl border border-slate-border bg-ink-50/50 p-2.5">
                  <p className="text-[10px] text-gray-500">Ultima atualizacao</p>
                  <p className="mt-1 text-xs font-semibold text-gray-300">{lastSyncLabel}</p>
                </div>
                <div className="rounded-xl border border-slate-border bg-ink-50/50 p-2.5">
                  <p className="text-[10px] text-gray-500">Status</p>
                  <p className="mt-1 text-xs font-semibold text-gray-300">{crmReady ? 'Disponivel' : 'Indisponivel'}</p>
                </div>
                <div className="rounded-xl border border-slate-border bg-ink-50/50 p-2.5">
                  <p className="text-[10px] text-gray-500">Sessao</p>
                  <p className="mt-1 text-xs font-semibold text-gray-300">Unificada</p>
                </div>
                <div className="rounded-xl border border-slate-border bg-ink-50/50 p-2.5">
                  <p className="text-[10px] text-gray-500">Rota</p>
                  <p className="mt-1 text-xs font-semibold text-gray-300">/crm</p>
                </div>
              </div>
            </details>
          </div>

          <div className="rounded-2xl border border-slate-border bg-[#060606] p-2 shadow-2xl flex-1 flex flex-col min-h-0">
            {checking ? (
              <div className="flex-1 grid place-items-center rounded-xl bg-ink-50">
                <div className="text-center">
                  <div className="mx-auto h-10 w-10 animate-spin rounded-full border-2 border-azure/25 border-t-azure" />
                  <p className="mt-4 text-xs font-semibold text-white">Carregando...</p>
                </div>
              </div>
            ) : crmReady ? (
              <div className="relative flex-1 flex flex-col min-h-0 rounded-xl bg-black/60 overflow-hidden">
                {!frameLoaded && (
                  <div className="absolute inset-0 z-10 grid place-items-center rounded-xl bg-ink-50/95">
                    <div className="text-center">
                      <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-azure/25 border-t-azure" />
                      <p className="mt-3 text-xs font-semibold text-white">Abrindo CRM...</p>
                    </div>
                  </div>
                )}
                <iframe
                  title="CRM de Licitacoes"
                  src={`${CRM_PORTAL_SRC}&refresh=${crmRefreshToken}`}
                  className="flex-1 w-full bg-transparent border-none rounded-xl"
                  onLoad={() => setFrameLoaded(true)}
                />
              </div>
            ) : (
              <div className="flex-1 grid place-items-center rounded-xl border border-dashed border-yellow-warn/30 bg-yellow-warn/5 p-6 text-center">
                <div className="max-w-md">
                  <p className="text-[10px] uppercase tracking-wide text-yellow-warn">Indisponivel</p>
                  <h2 className="mt-2 text-lg font-bold text-white">CRM nao esta carregado</h2>
                  <p className="mt-2 text-xs leading-relaxed text-gray-400">
                    O modulo do CRM ainda nao foi sincronizado neste ambiente.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {showImportModal && (
          <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 px-4">
            <div className="w-full max-w-xl rounded-2xl border border-slate-border bg-ink-100/95 shadow-2xl backdrop-blur">
              <div className="p-5 border-b border-slate-border">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-bold text-white">Importar processos (XLSX)</p>
                    <p className="mt-1 text-xs text-gray-400">
                      A planilha cria/atualiza editais e itens no CRM.
                    </p>
                  </div>
                  <button
                    type="button"
                    className="btn-ghost rounded-xl px-3 py-2 text-xs font-semibold"
                    onClick={() => setShowImportModal(false)}
                    disabled={uploadingSheet}
                  >
                    Fechar
                  </button>
                </div>
              </div>

              <div className="p-5 space-y-4">
                <div className="rounded-xl border border-dashed border-azure/20 bg-azure/5 p-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="text-sm font-semibold text-white">Selecione a planilha</p>
                      <p className="mt-1 text-xs text-gray-400">Formato aceito: .xlsx</p>
                    </div>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".xlsx"
                      className="block text-xs text-gray-300 file:mr-3 file:rounded-lg file:border file:border-azure/20 file:bg-azure/10 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-azure-glow cursor-pointer"
                      onChange={handleSheetUpload}
                      disabled={uploadingSheet}
                    />
                  </div>

                  {(uploadingSheet || sheetSummary || sheetError) && (
                    <div className="mt-3 border-t border-slate-border/30 pt-3 text-xs">
                      {uploadingSheet && <p className="text-azure-glow animate-pulse">Importando e sincronizando...</p>}
                      {sheetError && <p className="text-red-400">{sheetError}</p>}
                      {sheetSummary && (
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                          <p className="text-green-match font-medium">
                            ✓ Importacao concluida: {sheetSummary.grupos_processados} editais e {sheetSummary.itens_processados} itens.
                          </p>
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              className="btn-ghost px-3 py-1.5 text-xs font-semibold rounded-lg"
                              onClick={resetImportState}
                            >
                              Enviar outra
                            </button>
                            <button
                              type="button"
                              className="btn-primary px-3 py-1.5 text-xs font-semibold rounded-lg"
                              onClick={() => setCrmRefreshToken(Date.now())}
                            >
                              Atualizar CRM
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div className="text-xs text-gray-500">
                  Dica: apos importar, abra um edital e rode o match na aba Match.
                </div>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  )
}

