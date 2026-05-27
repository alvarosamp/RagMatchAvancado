import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { editaisApi } from '../api/client'
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

  const inputRef = useRef(null)
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

  if (jobId) {
    return (
      <div className="p-6 lg:p-8 max-w-3xl mx-auto space-y-6">
        <div>
          <p className="text-sm text-gray-400">Novo edital</p>
          <h1 className="mt-1 text-2xl font-semibold text-white">Processando</h1>
          <p className="mt-2 text-sm text-gray-400">
            Estamos indexando o documento. Isso pode levar alguns minutos.
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
    <div className="p-6 lg:p-8 max-w-3xl mx-auto space-y-6">
      <div>
        <p className="text-sm text-gray-400">Novo edital</p>
        <h1 className="mt-1 text-2xl font-semibold text-white">Upload de PDF</h1>
        <p className="mt-2 text-sm text-gray-400">
          Envie um PDF para processamento automatico (OCR, indexacao e extracao de requisitos).
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div
          className={`border-2 border-dashed rounded-2xl p-10 flex flex-col items-center justify-center cursor-pointer transition-colors ${
            dragging
              ? 'border-azure/60 bg-azure/5'
              : 'border-slate-border hover:bg-slate-hover hover:border-slate-border/80'
          }`}
          onClick={() => inputRef.current?.click()}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
        >
          <input ref={inputRef} type="file" accept="application/pdf" className="hidden" onChange={onFileChange} />

          {file ? (
            <div className="flex flex-col items-center text-center">
              <div className="w-14 h-14 rounded-2xl bg-black/20 border border-white/10 flex items-center justify-center text-gray-200 font-semibold mb-3">
                PDF
              </div>
              <p className="font-semibold text-white text-sm">{file.name}</p>
              <p className="text-xs text-gray-500 mt-1">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
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
              <div className="w-16 h-16 rounded-2xl border border-slate-border flex items-center justify-center text-gray-300 mb-4">
                Arraste aqui
              </div>
              <p className="font-semibold text-white">{dragging ? 'Solte o arquivo' : 'Arraste um PDF'}</p>
              <p className="text-sm text-gray-500 mt-1">ou clique para selecionar</p>
              <p className="text-xs text-gray-600 mt-3">Somente .pdf | max. {MAX_FILE_MB} MB</p>
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
          <div className="flex items-start gap-3 px-4 py-3 rounded-xl bg-ink-50/60 border border-slate-border">
            <span className="text-xs text-gray-400 mt-0.5 flex-shrink-0">INFO</span>
            <p className="text-xs text-gray-400 leading-relaxed">
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
    </div>
  )
}

