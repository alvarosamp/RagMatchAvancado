import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { analysisApi, editaisApi } from '../api/client'
import { useToast } from '../contexts/ToastContext'
import JobPoller from '../components/JobPoller'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'

const MAX_PDF_MB = 50
const JSON_CONCURRENCY = 4

function isPdfFile(file) {
  return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
}

function isJsonFile(file) {
  return file.name.toLowerCase().endsWith('.json')
}

function validatePdf(file) {
  if (!file) return 'Nenhum arquivo selecionado.'
  if (!isPdfFile(file)) return 'Apenas arquivos PDF (.pdf) sao aceitos.'
  if (file.size > MAX_PDF_MB * 1024 * 1024) return `O arquivo excede o limite de ${MAX_PDF_MB} MB.`
  return null
}

function readJsonFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      try {
        resolve(JSON.parse(reader.result))
      } catch {
        reject(new Error('Arquivo de analise invalido.'))
      }
    }
    reader.onerror = () => reject(new Error('Falha ao ler o arquivo.'))
    reader.readAsText(file)
  })
}

async function runWithConcurrency(tasks, limit, onEach) {
  let cursor = 0
  async function worker() {
    while (cursor < tasks.length) {
      const index = cursor++
      const result = await tasks[index]()
      onEach(index, result)
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, tasks.length) }, worker))
}

export default function Upload() {
  // ── PDF (edital unico → OCR) ────────────────────────────────────────────
  const [pdfFiles, setPdfFiles] = useState([])
  const [loading, setLoading] = useState(false)
  const [jobs, setJobs] = useState([])
  const [error, setError] = useState(null)

  // ── JSON (um ou varios arquivos de analise → BI + CRM) ──────────────────
  const [jsonFiles, setJsonFiles] = useState([])
  const [jsonProcessing, setJsonProcessing] = useState(false)
  const [jsonResults, setJsonResults] = useState([])
  const [jsonDoneCount, setJsonDoneCount] = useState(0)

  const [dragging, setDragging] = useState(false)

  const inputRef = useRef(null)
  const navigate = useNavigate()
  const { toast } = useToast()

  const clearAll = () => {
    setPdfFiles([])
    setJsonFiles([])
    setJsonResults([])
    setJsonDoneCount(0)
    setJobs([])
    setError(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  const applyFiles = (fileList) => {
    const all = Array.from(fileList || [])
    const jsons = all.filter(isJsonFile)
    const pdfs = all.filter(isPdfFile)

    if (jsons.length) {
      setJsonFiles(jsons)
      setJsonResults([])
      setJsonDoneCount(0)
      setPdfFiles([])
      setError(null)
      return
    }
    if (pdfs.length) {
      const err = pdfs.map(validatePdf).find(Boolean)
      if (err) {
        setError(err)
        setPdfFiles([])
        return
      }
      setPdfFiles(pdfs)
      setJsonFiles([])
      setJsonResults([])
      setError(null)
      return
    }
    setError('Envie um PDF (.pdf) ou arquivo(s) de analise (.json).')
  }

  const onDragOver = (e) => {
    e.preventDefault()
    setDragging(true)
  }
  const onDragLeave = () => setDragging(false)
  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    applyFiles(e.dataTransfer.files)
  }
  const onFileChange = (e) => applyFiles(e.target.files)

  const handlePdfSubmit = async () => {
    const err = pdfFiles.length ? pdfFiles.map(validatePdf).find(Boolean) : 'Nenhum arquivo selecionado.'
    if (err) {
      setError(err)
      return
    }

    setLoading(true)
    setError(null)

    try {
      const submitted = []
      for (const file of pdfFiles) {
        const formData = new FormData()
        formData.append('file', file)
        const res = await editaisApi.upload(formData)
        const jid = res.data?.job_id || res.data?.id
        if (jid) {
          submitted.push({ id: jid, filename: file.name, size: file.size })
        }
      }
      setJobs(submitted)
      toast({
        type: 'success',
        title: 'Upload concluido',
        message: `${submitted.length} documento(s) em processamento.`,
      })
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
    if (jobs.length <= 1) navigate(editalId ? `/editais/${editalId}` : '/dashboard')
  }

  const handleJobFailed = (job) => {
    const msg = job.error_message || 'O processamento falhou. Verifique o arquivo e tente novamente.'
    setError(msg)
    toast({ type: 'error', title: 'Erro no processamento', message: msg })
  }

  const processJsonFiles = async () => {
    if (!jsonFiles.length) return
    setJsonProcessing(true)
    setJsonDoneCount(0)
    const outcomes = new Array(jsonFiles.length)

    const tasks = jsonFiles.map((file) => async () => {
      try {
        const parsed = await readJsonFile(file)
        if (!parsed.schema_version) {
          return { name: file.name, status: 'error', message: 'Arquivo fora do modelo de importacao.' }
        }
        const response = await analysisApi.create({
          source_kind: 'edital',
          source_name: file.name,
          result: parsed,
        })
        return {
          name: file.name,
          status: 'ok',
          id: response.data.id,
          crmNoticeId: response.data.crm_sync?.notice_id,
          products: response.data.crm_sync?.products ?? 0,
          documents: response.data.crm_sync?.documents ?? 0,
        }
      } catch (err) {
        return {
          name: file.name,
          status: 'error',
          message: err.response?.data?.detail || err.message || 'Erro ao processar arquivo.',
        }
      }
    })

    await runWithConcurrency(tasks, JSON_CONCURRENCY, (index, outcome) => {
      outcomes[index] = outcome
      setJsonDoneCount((count) => count + 1)
      setJsonResults([...outcomes.filter(Boolean)])
    })

    setJsonProcessing(false)
    const okCount = outcomes.filter((outcome) => outcome?.status === 'ok').length
    const errCount = outcomes.filter((outcome) => outcome?.status === 'error').length
    toast({
      type: errCount ? 'error' : 'success',
      message: `${okCount} analise(s) importada(s)${errCount ? `, ${errCount} com erro` : ''}.`,
    })
  }

  if (jobs.length > 0) {
    return (
      <div className="min-h-screen bg-surface p-6 text-slate-950 dark:bg-surface-dark dark:text-white lg:p-8">
        <div className="mx-auto max-w-3xl space-y-6">
          <div>
            <p className="text-sm text-slate-500 dark:text-slate-400">Documento recebido</p>
            <h1 className="mt-1 text-2xl font-semibold text-slate-950 dark:text-white">Estamos preparando o edital</h1>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
              O sistema esta lendo o PDF, separando o texto e organizando as informacoes para consulta.
            </p>
          </div>

          <Card className="space-y-4 p-6">
            <div className="flex items-center gap-3 border-b border-slate-200 pb-4 dark:border-slate-700">
              <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-slate-50 text-xs font-semibold text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
                PDF
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-slate-950 dark:text-white">{jobs.length} documento(s) recebido(s)</p>
                <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">Acompanhe cada processamento abaixo.</p>
              </div>
              <Badge tone="emerald" className="ml-auto flex-shrink-0">Recebido</Badge>
            </div>

            <div className="space-y-4">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">Progresso</p>
              {jobs.map((item) => (
                <div key={item.id} className="rounded-lg border border-slate-200 p-4 dark:border-slate-700">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <p className="truncate text-sm font-semibold text-slate-950 dark:text-white">{item.filename}</p>
                    <span className="text-xs text-slate-500 dark:text-slate-400">{(item.size / 1024 / 1024).toFixed(2)} MB</span>
                  </div>
                  <JobPoller jobId={item.id} onDone={handleJobDone} onFailed={handleJobFailed} />
                </div>
              ))}
            </div>

            {error && (
              <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 dark:border-red-800 dark:bg-red-950/40">
                <span className="mt-0.5 text-sm text-red-700 dark:text-red-300">Erro</span>
                <p className="text-sm leading-relaxed text-red-700 dark:text-red-300">{error}</p>
              </div>
            )}
          </Card>

          <div className="flex gap-3">
            <button onClick={() => navigate('/jobs')} className="rounded-lg border border-slate-300 bg-white px-5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700">
              Ver jobs
            </button>
            <button onClick={clearAll} className="rounded-lg border border-slate-300 bg-white px-5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700">
              Enviar outro arquivo
            </button>
          </div>
        </div>
      </div>
    )
  }

  const hasSelection = pdfFiles.length > 0 || jsonFiles.length > 0

  return (
    <div className="min-h-screen bg-surface p-6 text-slate-950 dark:bg-surface-dark dark:text-white lg:p-8">
      <div className="mx-auto max-w-5xl space-y-6">
        <Card className="p-6">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">Entrada de documentos</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 dark:text-white">Adicionar processos ao portal</h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600 dark:text-slate-300">
            Arraste o PDF do edital para OCR e analise dos requisitos, ou um (ou vários) arquivo de análise em JSON
            para atualizar o BI e o CRM automaticamente — a mesma área reconhece o tipo do arquivo.
          </p>
        </Card>

        <Card className="space-y-6 p-6">
          <div
            className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-10 text-center transition-colors ${
              dragging
                ? 'border-brand bg-blue-50 dark:border-brand-light dark:bg-brand/10'
                : 'border-slate-300 bg-slate-50 hover:border-brand dark:border-slate-700 dark:bg-slate-900 dark:hover:border-brand-light'
            }`}
            onClick={() => inputRef.current?.click()}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
          >
            <input
              ref={inputRef}
              type="file"
              accept="application/pdf,.pdf,.json"
              multiple
              className="hidden"
              onChange={onFileChange}
            />

            {pdfFiles.length > 0 ? (
              <div className="flex flex-col items-center">
                <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-lg border border-slate-200 bg-white font-semibold text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                  PDF
                </div>
                <p className="text-sm font-semibold text-slate-950 dark:text-white">{pdfFiles.length} PDF(s) selecionado(s)</p>
                <p className="mt-1 max-w-xl text-xs text-slate-500 dark:text-slate-400">
                  {pdfFiles.slice(0, 3).map((file) => file.name).join(', ')}{pdfFiles.length > 3 ? '...' : ''}
                </p>
                <button
                  type="button"
                  className="mt-3 rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                  onClick={(e) => { e.stopPropagation(); clearAll() }}
                >
                  Remover arquivo
                </button>
              </div>
            ) : jsonFiles.length > 0 ? (
              <div className="flex flex-col items-center">
                <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-lg border border-slate-200 bg-white font-semibold text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                  JSON
                </div>
                <p className="text-sm font-semibold text-slate-950 dark:text-white">
                  {jsonFiles.length} arquivo(s) de analise selecionado(s)
                </p>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  {jsonFiles.slice(0, 3).map((f) => f.name).join(', ')}{jsonFiles.length > 3 ? '…' : ''}
                </p>
                <button
                  type="button"
                  className="mt-3 rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                  onClick={(e) => { e.stopPropagation(); clearAll() }}
                >
                  Remover selecao
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center">
                <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">
                  +
                </div>
                <p className="font-semibold text-slate-950 dark:text-white">{dragging ? 'Solte o(s) arquivo(s)' : 'Arraste o PDF ou o(s) JSON aqui'}</p>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">ou clique para selecionar no computador</p>
                <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
                  PDF: um ou varios arquivos, max. {MAX_PDF_MB} MB cada - JSON: um ou varios arquivos de analise
                </p>
              </div>
            )}
          </div>

          {error && (
            <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 dark:border-red-800 dark:bg-red-950/40">
              <span className="flex-shrink-0 text-sm text-red-700 dark:text-red-300">Erro</span>
              <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
            </div>
          )}

          {!hasSelection && !error && (
            <div className="flex items-start gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-900">
              <span className="mt-0.5 flex-shrink-0 text-xs text-slate-500 dark:text-slate-400">Dica</span>
              <p className="text-xs leading-relaxed text-slate-500 dark:text-slate-400">
                PDF: acompanhe cada job em tempo real e acesse o edital assim que terminar o OCR. JSON: o edital, os
                itens e os documentos sao sincronizados automaticamente no CRM na mesma importacao.
              </p>
            </div>
          )}

          {jsonFiles.length > 0 && jsonProcessing && (
            <div className="h-2 overflow-hidden rounded bg-slate-100 dark:bg-slate-700">
              <div className="h-2 rounded bg-brand dark:bg-brand-light" style={{ width: `${(jsonDoneCount / jsonFiles.length) * 100}%` }} />
            </div>
          )}

          <div className="flex gap-3">
            <button
              type="button"
              className="rounded-lg border border-slate-300 bg-white px-5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
              onClick={() => navigate('/dashboard')}
              disabled={loading || jsonProcessing}
            >
              Cancelar
            </button>
            {jsonFiles.length > 0 ? (
              <button
                type="button"
                onClick={processJsonFiles}
                disabled={jsonProcessing}
                className="flex items-center gap-2 rounded-lg bg-brand px-5 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-40 dark:bg-brand-light dark:hover:bg-brand"
              >
                {jsonProcessing ? `Importando ${jsonDoneCount}/${jsonFiles.length}` : 'Importar analise(s)'}
              </button>
            ) : (
              <button
                type="button"
                onClick={handlePdfSubmit}
                disabled={pdfFiles.length === 0 || loading}
                className="flex items-center gap-2 rounded-lg bg-brand px-5 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-40 dark:bg-brand-light dark:hover:bg-brand"
              >
                {loading ? (
                  <>
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                    Enviando...
                  </>
                ) : (
                  <>Enviar edital</>
                )}
              </button>
            )}
          </div>
        </Card>

        {jsonResults.length > 0 && (
          <Card className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4 dark:border-slate-700">
              <h2 className="text-lg font-semibold text-slate-950 dark:text-white">Resultado da importacao</h2>
              <button
                type="button"
                onClick={() => navigate('/analise/dashboard')}
                className="text-sm font-medium text-brand hover:underline dark:text-brand-light"
              >
                Ver BI
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left">
                <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Arquivo</th>
                    <th className="px-5 py-3 font-semibold">Status</th>
                    <th className="px-5 py-3 font-semibold">CRM</th>
                    <th className="px-5 py-3 font-semibold">Itens</th>
                    <th className="px-5 py-3 font-semibold">Documentos</th>
                    <th className="px-5 py-3 font-semibold"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                  {jsonResults.map((result, index) => (
                    <tr key={`${result.name}-${index}`}>
                      <td className="px-5 py-4 text-sm font-medium text-slate-950 dark:text-white">{result.name}</td>
                      <td className="px-5 py-4">
                        <Badge tone={result.status === 'ok' ? 'emerald' : 'red'}>
                          {result.status === 'ok' ? 'Importado' : 'Erro'}
                        </Badge>
                      </td>
                      <td className="px-5 py-4 text-sm text-slate-700 dark:text-slate-300">{result.crmNoticeId ? 'Sincronizado' : result.message || '-'}</td>
                      <td className="px-5 py-4 text-sm text-slate-700 dark:text-slate-300">{result.products ?? '-'}</td>
                      <td className="px-5 py-4 text-sm text-slate-700 dark:text-slate-300">{result.documents ?? '-'}</td>
                      <td className="px-5 py-4 text-right">
                        {result.status === 'ok' && (
                          <button
                            type="button"
                            onClick={() => navigate(`/analise/documentos/${result.id}`)}
                            className="text-sm font-medium text-brand hover:underline dark:text-brand-light"
                          >
                            Abrir
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
