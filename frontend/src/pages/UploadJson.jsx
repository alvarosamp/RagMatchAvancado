/**
 * pages/UploadJson.jsx
 * ──────────────────────
 * Ingestão em lote de JSONs de edital (schema v7.3). O usuário seleciona
 * uma pasta inteira (ou arrasta vários arquivos) — cada JSON vira um
 * AnalysisDocument via POST /analysis/documents. Processa com concorrência
 * limitada e mostra progresso + resumo por arquivo ao final.
 */

import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { analysisApi } from '../api/client'
import { useToast } from '../contexts/ToastContext'

const CONCURRENCY = 4

function readJsonFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      try {
        resolve(JSON.parse(reader.result))
      } catch (err) {
        reject(new Error('JSON inválido'))
      }
    }
    reader.onerror = () => reject(new Error('Falha ao ler o arquivo'))
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
  const [results, setResults] = useState([]) // { name, status: 'ok'|'error', id?, message? }
  const [doneCount, setDoneCount] = useState(0)

  const handleFiles = (fileList) => {
    const jsonFiles = Array.from(fileList).filter((f) => f.name.toLowerCase().endsWith('.json'))
    if (!jsonFiles.length) {
      toast({ type: 'error', message: 'Nenhum arquivo .json encontrado na seleção.' })
      return
    }
    setFiles(jsonFiles)
    setResults([])
    setDoneCount(0)
  }

  const handleProcess = async () => {
    if (!files.length) return
    setProcessing(true)
    setDoneCount(0)
    const outcomes = new Array(files.length)

    const tasks = files.map((file) => async () => {
      try {
        const parsed = await readJsonFile(file)
        if (!parsed.schema_version) {
          return { name: file.name, status: 'error', message: 'Sem "schema_version" — não parece um JSON de edital.' }
        }
        const response = await analysisApi.create({
          source_kind: 'edital',
          source_name: file.name,
          result: parsed,
        })
        return { name: file.name, status: 'ok', id: response.data.id }
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
      setDoneCount((c) => c + 1)
      setResults([...outcomes.filter(Boolean)])
    })

    setProcessing(false)
    const okCount = outcomes.filter((o) => o?.status === 'ok').length
    const errCount = outcomes.filter((o) => o?.status === 'error').length
    toast({
      type: errCount ? 'error' : 'success',
      message: `${okCount} edital(is) importado(s)${errCount ? `, ${errCount} com erro` : ''}.`,
    })
  }

  return (
    <div className="p-6 space-y-6 min-h-screen max-w-3xl mx-auto">
      <div>
        <h1 className="font-display font-black text-2xl text-white">Importar editais via JSON</h1>
        <p className="text-sm text-gray-500 font-mono mt-1">
          Selecione uma pasta com os JSONs de edital (schema v7.3) ou arraste vários arquivos.
        </p>
      </div>

      <div
        className="card border-2 border-dashed border-slate-border/60 p-10 text-center cursor-pointer hover:border-azure/40 transition-colors"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault()
          handleFiles(e.dataTransfer.files)
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
          onChange={(e) => handleFiles(e.target.files)}
        />
        <div className="text-4xl mb-3">📁</div>
        <p className="text-sm text-gray-300">
          Clique para escolher uma pasta ou arraste os arquivos .json aqui
        </p>
        {files.length > 0 && (
          <p className="text-xs text-gray-500 font-mono mt-2">{files.length} arquivo(s) selecionado(s)</p>
        )}
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={handleProcess}
          disabled={!files.length || processing}
          className="btn-primary text-sm px-4 py-2 disabled:opacity-40"
        >
          {processing ? `Processando ${doneCount}/${files.length}…` : `Importar ${files.length || ''} edital(is)`}
        </button>
        <button
          onClick={() => navigate('/analise/dashboard')}
          className="btn-ghost text-sm px-4 py-2"
        >
          Ir para o dashboard
        </button>
      </div>

      {files.length > 0 && processing && (
        <div className="w-full h-2 rounded-full bg-slate-card overflow-hidden">
          <div
            className="h-full bg-azure transition-all duration-300"
            style={{ width: `${(doneCount / files.length) * 100}%` }}
          />
        </div>
      )}

      {results.length > 0 && (
        <div className="card p-0 overflow-hidden">
          <div className="max-h-96 overflow-y-auto divide-y divide-slate-border/20">
            {results.map((r, i) => (
              <div key={i} className="px-4 py-2.5 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs text-gray-200 truncate font-mono">{r.name}</p>
                  {r.status === 'error' && (
                    <p className="text-[10px] text-red-400 mt-0.5">{r.message}</p>
                  )}
                </div>
                {r.status === 'ok' ? (
                  <button
                    onClick={() => navigate(`/analise/documentos/${r.id}`)}
                    className="text-[10px] font-mono text-azure-glow hover:underline whitespace-nowrap"
                  >
                    ✓ ver edital
                  </button>
                ) : (
                  <span className="text-[10px] font-mono text-red-400 whitespace-nowrap">✕ erro</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
