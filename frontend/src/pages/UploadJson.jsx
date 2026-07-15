import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { analysisApi } from '../api/client'
import { useToast } from '../contexts/ToastContext'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'

const CONCURRENCY = 4

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

export default function UploadJson() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const inputRef = useRef(null)

  const [files, setFiles] = useState([])
  const [processing, setProcessing] = useState(false)
  const [results, setResults] = useState([])
  const [doneCount, setDoneCount] = useState(0)

  const handleFiles = (fileList) => {
    const selected = Array.from(fileList || []).filter((file) => file.name.toLowerCase().endsWith('.json'))
    if (!selected.length) {
      toast({ type: 'error', message: 'Selecione ao menos um arquivo de analise (.json).' })
      return
    }
    setFiles(selected)
    setResults([])
    setDoneCount(0)
  }

  const processFiles = async () => {
    if (!files.length) return
    setProcessing(true)
    setDoneCount(0)
    const outcomes = new Array(files.length)

    const tasks = files.map((file) => async () => {
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
          status: response.data.duplicate ? 'duplicate' : 'ok',
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

    await runWithConcurrency(tasks, CONCURRENCY, (index, outcome) => {
      outcomes[index] = outcome
      setDoneCount((count) => count + 1)
      setResults([...outcomes.filter(Boolean)])
    })

    setProcessing(false)
    const okCount = outcomes.filter((outcome) => outcome?.status === 'ok').length
    const dupCount = outcomes.filter((outcome) => outcome?.status === 'duplicate').length
    const errCount = outcomes.filter((outcome) => outcome?.status === 'error').length
    toast({
      type: errCount ? 'error' : 'success',
      message: `${okCount} analise(s) importada(s)`
        + `${dupCount ? `, ${dupCount} ja existente(s) (ignorada(s))` : ''}`
        + `${errCount ? `, ${errCount} com erro` : ''}.`,
    })
  }

  return (
    <div className="min-h-screen bg-surface p-6 text-slate-950 dark:bg-surface-dark dark:text-white lg:p-8">
      <div className="mx-auto max-w-5xl space-y-6">
        <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">Importacao</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 dark:text-white">Importar analises de editais</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600 dark:text-slate-300">
              Envie um ou varios arquivos de analise. O sistema atualiza o BI e sincroniza automaticamente edital, itens e documentos no CRM.
            </p>
          </div>
          <button
            type="button"
            onClick={() => navigate('/analise/dashboard')}
            className="rounded-lg border border-slate-300 bg-white px-5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
          >
            Ver BI
          </button>
        </header>

        <Card className="p-6">
          <div
            className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 p-10 text-center hover:border-brand dark:border-slate-700 dark:bg-slate-900 dark:hover:border-brand-light"
            onClick={() => inputRef.current?.click()}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault()
              handleFiles(event.dataTransfer.files)
            }}
          >
            <input
              ref={inputRef}
              type="file"
              multiple
              accept=".json"
              webkitdirectory=""
              directory=""
              className="hidden"
              onChange={(event) => handleFiles(event.target.files)}
            />
            <p className="text-lg font-semibold text-slate-950 dark:text-white">Selecione uma pasta ou arraste os arquivos aqui</p>
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">Formato aceito: arquivo de analise em JSON.</p>
            {files.length > 0 && (
              <p className="mt-4 rounded border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                {files.length} arquivo(s) selecionado(s)
              </p>
            )}
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={processFiles}
              disabled={!files.length || processing}
              className="rounded-lg bg-brand px-5 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-50 dark:bg-brand-light dark:hover:bg-brand"
            >
              {processing ? `Processando ${doneCount}/${files.length}` : 'Importar analises'}
            </button>
            <button
              type="button"
              onClick={() => {
                setFiles([])
                setResults([])
                setDoneCount(0)
                if (inputRef.current) inputRef.current.value = ''
              }}
              disabled={processing || (!files.length && !results.length)}
              className="rounded-lg border border-slate-300 bg-white px-5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
            >
              Limpar
            </button>
          </div>

          {files.length > 0 && processing && (
            <div className="mt-5 h-2 overflow-hidden rounded bg-slate-100 dark:bg-slate-700">
              <div className="h-2 rounded bg-brand dark:bg-brand-light" style={{ width: `${(doneCount / files.length) * 100}%` }} />
            </div>
          )}
        </Card>

        {results.length > 0 && (
          <Card className="overflow-hidden">
            <div className="border-b border-slate-200 px-5 py-4 dark:border-slate-700">
              <h2 className="text-lg font-semibold text-slate-950 dark:text-white">Resultado da importacao</h2>
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
                  {results.map((result, index) => (
                    <tr key={`${result.name}-${index}`}>
                      <td className="px-5 py-4 text-sm font-medium text-slate-950 dark:text-white">{result.name}</td>
                      <td className="px-5 py-4">
                        <Badge tone={result.status === 'ok' ? 'emerald' : result.status === 'duplicate' ? 'amber' : 'red'}>
                          {result.status === 'ok' ? 'Importado' : result.status === 'duplicate' ? 'Ja existente' : 'Erro'}
                        </Badge>
                      </td>
                      <td className="px-5 py-4 text-sm text-slate-700 dark:text-slate-300">
                        {result.status === 'duplicate' ? 'Nao reprocessado' : result.crmNoticeId ? 'Sincronizado' : result.message || '-'}
                      </td>
                      <td className="px-5 py-4 text-sm text-slate-700 dark:text-slate-300">{result.products ?? '-'}</td>
                      <td className="px-5 py-4 text-sm text-slate-700 dark:text-slate-300">{result.documents ?? '-'}</td>
                      <td className="px-5 py-4 text-right">
                        {(result.status === 'ok' || result.status === 'duplicate') && (
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
