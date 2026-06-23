import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { crmApi, editaisApi } from '../api/client'
import { useToast } from '../contexts/ToastContext'
import JobPoller from '../components/JobPoller'

const MAX_FILE_MB = 50

function validateFile(file) {
  if (!file) return 'Nenhum arquivo selecionado.'
  if (file.type !== 'application/pdf') return 'Apenas arquivos PDF (.pdf) sao aceitos.'
  if (file.size > MAX_FILE_MB * 1024 * 1024) return `O arquivo excede o limite de ${MAX_FILE_MB} MB.`
  return null
}

export default function Upload() {
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [jobId, setJobId] = useState(null)
  const [error, setError] = useState(null)
  const [sheetLoading, setSheetLoading] = useState(false)
  const [sheetError, setSheetError] = useState(null)
  const [sheetSummary, setSheetSummary] = useState(null)

  const inputRef = useRef(null)
  const sheetInputRef = useRef(null)
  const navigate = useNavigate()
  const { toast } = useToast()

  const applyFile = (next) => {
    const err = validateFile(next)
    if (err) {
      setError(err)
      setFile(null)
      return
    }
    setFile(next)
    setError(null)
  }

  const onDragOver = (e) => {
    e.preventDefault()
    setDragging(true)
  }
  const onDragLeave = () => setDragging(false)
  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    applyFile(e.dataTransfer.files[0])
  }
  const onFileChange = (e) => applyFile(e.target.files[0])

  const resetUpload = () => {
    setJobId(null)
    setFile(null)
    setError(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const err = validateFile(file)
    if (err) {
      setError(err)
      return
    }

    setLoading(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const res = await editaisApi.upload(formData)
      const jid = res.data?.job_id || res.data?.id

      if (jid) {
        setJobId(jid)
        toast({
          type: 'success',
          title: 'Upload concluido',
          message: 'Documento em processamento. Acompanhe o progresso abaixo.',
        })
      } else {
        toast({ type: 'success', title: 'Edital enviado', message: 'Acompanhe o processamento em Jobs.' })
        navigate('/jobs')
      }
    } catch (err2) {
      const msg = err2.response?.data?.detail ?? 'Falha ao enviar o arquivo. Tente novamente.'
      setError(msg)
      toast({ type: 'error', title: 'Erro no upload', message: msg })
    } finally {
      setLoading(false)
    }
  }

  const handleJobDone = (job) => {
    const editalId = job.result?.edital_id
    toast({
      type: 'success',
      title: 'Processamento concluido',
      message: 'O edital foi indexado e esta pronto para analise.',
      duration: 6000,
    })
    navigate(editalId ? `/editais/${editalId}` : '/dashboard')
  }

  const handleJobFailed = (job) => {
    const msg = job.error_message || 'O processamento falhou. Verifique o arquivo e tente novamente.'
    setError(msg)
    toast({ type: 'error', title: 'Erro no processamento', message: msg })
  }

  const handleSheetUpload = async (event) => {
    const sheet = event.target.files?.[0]
    if (!sheet) return

    setSheetLoading(true)
    setSheetError(null)
    setSheetSummary(null)

    try {
      const formData = new FormData()
      formData.append('file', sheet)
      const response = await crmApi.importSalesProcesses(formData)
      const summary = response.data?.summary || {}
      setSheetSummary(summary)
      toast({
        type: 'success',
        title: 'Planilha importada',
        message: `${summary.grupos_processados || 0} editais e ${summary.itens_processados || 0} itens sincronizados no CRM.`,
      })
    } catch (err) {
      const msg = err.response?.data?.detail || 'Nao foi possivel importar a planilha.'
      setSheetError(msg)
      toast({ type: 'error', title: 'Erro na planilha', message: msg })
    } finally {
      setSheetLoading(false)
      if (sheetInputRef.current) sheetInputRef.current.value = ''
    }
  }

  if (jobId) {
    return (
      <div className="p-6 lg:p-8 max-w-3xl mx-auto space-y-6">
        <div>
          <p className="text-sm text-stone-500 dark:text-gray-400">Documento recebido</p>
          <h1 className="mt-1 text-2xl font-semibold text-stone-950 dark:text-white">Estamos preparando o edital</h1>
          <p className="mt-2 text-sm text-stone-600 dark:text-gray-400">
            O sistema esta lendo o PDF, separando o texto e organizando as informacoes para consulta.
          </p>
        </div>

        <div className="card border-slate-border/80 space-y-4">
          <div className="flex items-center gap-3 pb-4 border-b border-slate-border">
            <div className="w-11 h-11 rounded-2xl bg-black/20 border border-white/10 flex items-center justify-center text-gray-200 text-xs font-semibold flex-shrink-0">
              PDF
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-white truncate">{file?.name}</p>
              <p className="text-xs text-gray-500 mt-0.5">
                {file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : ''}
              </p>
            </div>
            <span className="ml-auto text-green-match text-sm flex-shrink-0">OK</span>
          </div>

          <div>
            <p className="text-xs text-gray-500 font-medium mb-3">Progresso</p>
            <JobPoller jobId={jobId} onDone={handleJobDone} onFailed={handleJobFailed} />
          </div>

          {error && (
            <div className="flex items-start gap-2 px-4 py-3 rounded-xl bg-red-fail/5 border border-red-fail/20">
              <span className="text-red-fail text-sm mt-0.5">ERRO</span>
              <p className="text-sm text-red-fail leading-relaxed">{error}</p>
            </div>
          )}
        </div>

        <div className="flex gap-3">
          <button onClick={() => navigate('/jobs')} className="btn-ghost text-sm">
            Ver jobs
          </button>
          <button onClick={resetUpload} className="btn-ghost text-sm">
            Enviar outro arquivo
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto space-y-6">
      <div className="rounded-[32px] border border-stone-200 bg-white p-6 shadow-sm dark:border-slate-border dark:bg-slate-card/95">
        <p className="text-sm text-stone-500 dark:text-gray-400">Entrada de documentos</p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight text-stone-950 dark:text-white">Adicionar processos ao portal</h1>
        <p className="mt-3 max-w-2xl text-base leading-7 text-stone-600 dark:text-gray-400">
          Use PDF quando quiser analisar um edital novo. Use planilha quando o time ja trouxe uma lista de processos analisados para entrar no CRM.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6 rounded-[28px] border border-stone-200 bg-white p-6 shadow-sm dark:border-slate-border dark:bg-slate-card/95">
        <div>
          <p className="text-lg font-semibold text-stone-950 dark:text-white">1. Enviar PDF do edital</p>
          <p className="mt-1 text-sm text-stone-500 dark:text-gray-400">Ideal para OCR, busca no documento e analise dos requisitos.</p>
        </div>
        <div
          className={`border-2 border-dashed rounded-3xl p-10 flex flex-col items-center justify-center cursor-pointer transition-colors ${
            dragging
              ? 'border-red-300 bg-red-50 dark:border-azure/60 dark:bg-azure/5'
              : 'border-stone-200 bg-[#fbf8f3] hover:border-red-200 hover:bg-red-50/50 dark:border-slate-border dark:bg-transparent dark:hover:bg-slate-hover dark:hover:border-slate-border/80'
          }`}
          onClick={() => inputRef.current?.click()}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
        >
          <input ref={inputRef} type="file" accept="application/pdf" className="hidden" onChange={onFileChange} />

          {file ? (
            <div className="flex flex-col items-center text-center">
              <div className="w-14 h-14 rounded-2xl bg-red-50 border border-red-100 flex items-center justify-center text-red-700 font-semibold mb-3 dark:bg-black/20 dark:border-white/10 dark:text-gray-200">
                PDF
              </div>
              <p className="font-semibold text-stone-950 text-sm dark:text-white">{file.name}</p>
              <p className="text-xs text-stone-500 mt-1 dark:text-gray-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
              <button
                type="button"
                className="mt-3 text-xs font-medium text-gray-400 hover:text-white transition-colors px-3 py-1 rounded-xl border border-slate-border hover:bg-black/20"
                onClick={(e) => {
                  e.stopPropagation()
                  resetUpload()
                }}
              >
                Remover arquivo
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center text-center">
              <div className="w-16 h-16 rounded-2xl border border-stone-200 bg-white flex items-center justify-center text-stone-500 mb-4 dark:border-slate-border dark:bg-ink-50 dark:text-gray-300">
                PDF
              </div>
              <p className="font-semibold text-stone-950 dark:text-white">{dragging ? 'Solte o arquivo' : 'Arraste o PDF aqui'}</p>
              <p className="text-sm text-stone-500 mt-1 dark:text-gray-500">ou clique para selecionar no computador</p>
              <p className="text-xs text-stone-400 mt-3 dark:text-gray-600">Somente .pdf | max. {MAX_FILE_MB} MB</p>
            </div>
          )}
        </div>

        {error && (
          <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-red-fail/5 border border-red-fail/20">
            <span className="text-red-fail text-sm flex-shrink-0">ERRO</span>
            <p className="text-sm text-red-fail">{error}</p>
          </div>
        )}

        {!file && !error && (
          <div className="flex items-start gap-3 px-4 py-3 rounded-xl bg-stone-50 border border-stone-200 dark:bg-ink-50/60 dark:border-slate-border">
            <span className="text-xs text-stone-500 mt-0.5 flex-shrink-0 dark:text-gray-400">Dica</span>
            <p className="text-xs text-stone-500 leading-relaxed dark:text-gray-400">
              Depois do upload, voce pode acompanhar o job em tempo real e acessar o edital assim que terminar.
            </p>
          </div>
        )}

        <div className="flex gap-3">
          <button type="button" className="btn-ghost" onClick={() => navigate('/dashboard')} disabled={loading}>
            Cancelar
          </button>
          <button type="submit" className="btn-primary flex items-center gap-2 disabled:opacity-40" disabled={!file || loading}>
            {loading ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Enviando...
              </>
            ) : (
              <>Enviar edital</>
            )}
          </button>
        </div>
      </form>

      <section className="card border-slate-border/80 space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-sm text-stone-500 dark:text-gray-400">2. Importar planilha analisada</p>
            <h2 className="mt-1 text-xl font-semibold text-stone-950 dark:text-white">Levar processos direto para o CRM</h2>
            <p className="mt-2 max-w-2xl text-sm leading-7 text-stone-600 dark:text-gray-400">
              A planilha vira editais, lotes e itens no CRM, ja entrando na fase de triagem.
            </p>
          </div>
          <button
            type="button"
            className="btn-ghost text-sm"
            onClick={() => navigate('/crm')}
          >
            Abrir CRM
          </button>
        </div>

        <div className="rounded-2xl border border-dashed border-slate-border bg-ink-50/60 p-5 theme-card">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-semibold text-white">Selecione a planilha</p>
              <p className="mt-1 text-xs text-gray-500">Formato aceito: .xlsx</p>
            </div>
            <input
              ref={sheetInputRef}
              type="file"
              accept=".xlsx"
              className="block text-xs text-gray-300 file:mr-3 file:rounded-lg file:border file:border-azure/20 file:bg-azure/10 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-azure-glow cursor-pointer"
              onChange={handleSheetUpload}
              disabled={sheetLoading}
            />
          </div>

          {(sheetLoading || sheetSummary || sheetError) && (
            <div className="mt-4 border-t border-slate-border pt-4 text-sm">
              {sheetLoading && <p className="text-azure-glow animate-pulse">Importando e sincronizando...</p>}
              {sheetError && <p className="text-red-fail">{sheetError}</p>}
              {sheetSummary && (
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-green-match">
                    Importacao concluida: {sheetSummary.grupos_processados || 0} editais e {sheetSummary.itens_processados || 0} itens.
                  </p>
                  <button
                    type="button"
                    className="btn-primary text-sm"
                    onClick={() => navigate('/crm')}
                  >
                    Ver no CRM
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}

