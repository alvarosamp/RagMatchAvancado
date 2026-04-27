/**
 * pages/Upload.jsx
 * ─────────────────
 * Upload de edital PDF com progresso em tempo real via JobPoller.
 * Após envio bem-sucedido, mostra barra de processamento inline.
 * Ao concluir, redireciona para a página do edital automaticamente.
 */

import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { editaisApi } from '../api/client'
import { useToast }   from '../contexts/ToastContext'
import JobPoller      from '../components/JobPoller'

const MAX_FILE_MB = 50

export default function Upload() {
  const [file,     setFile]     = useState(null)
  const [dragging, setDragging] = useState(false)
  const [loading,  setLoading]  = useState(false)
  const [jobId,    setJobId]    = useState(null)   // job_id retornado pela API
  const [error,    setError]    = useState(null)

  const inputRef  = useRef(null)
  const navigate  = useNavigate()
  const { toast } = useToast()

  // ── Validação de arquivo ──────────────────────────────────────────────────

  const validateFile = (f) => {
    if (!f) return 'Nenhum arquivo selecionado.'
    if (f.type !== 'application/pdf') return 'Apenas arquivos PDF (.pdf) são aceitos.'
    if (f.size > MAX_FILE_MB * 1024 * 1024) return `O arquivo excede o limite de ${MAX_FILE_MB} MB.`
    return null
  }

  const applyFile = (f) => {
    const err = validateFile(f)
    if (err) { setError(err); setFile(null) }
    else     { setFile(f);   setError(null) }
  }

  // ── Drag & Drop ───────────────────────────────────────────────────────────

  const onDragOver  = (e) => { e.preventDefault(); setDragging(true)  }
  const onDragLeave = ()  => { setDragging(false) }
  const onDrop      = (e) => {
    e.preventDefault()
    setDragging(false)
    applyFile(e.dataTransfer.files[0])
  }
  const onFileChange = (e) => applyFile(e.target.files[0])

  // ── Submit ────────────────────────────────────────────────────────────────

  const handleSubmit = async (e) => {
    e.preventDefault()
    const err = validateFile(file)
    if (err) { setError(err); return }

    setLoading(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const res = await editaisApi.upload(formData)
      const jid = res.data?.job_id || res.data?.id

      if (jid) {
        // API retornou job_id — mostra barra de progresso inline
        setJobId(jid)
        toast({
          type:    'success',
          title:   'Upload concluído',
          message: 'Documento em processamento. Acompanhe o progresso abaixo.',
        })
      } else {
        // API não retornou job_id — redireciona para Jobs
        toast({ type: 'success', title: 'Edital enviado!', message: 'Acompanhe o processamento em Jobs.' })
        navigate('/jobs')
      }
    } catch (err) {
      const msg = err.response?.data?.detail ?? 'Falha ao enviar o arquivo. Tente novamente.'
      setError(msg)
      toast({ type: 'error', title: 'Erro no upload', message: msg })
    } finally {
      setLoading(false)
    }
  }

  // ── Callbacks do JobPoller ────────────────────────────────────────────────

  const handleJobDone = (job) => {
    const editalId = job.result?.edital_id
    toast({
      type:     'success',
      title:    'Processamento concluído!',
      message:  'O edital foi indexado e está pronto para análise.',
      duration: 6000,
    })
    navigate(editalId ? `/editais/${editalId}` : '/dashboard')
  }

  const handleJobFailed = (job) => {
    const msg = job.error_message || 'O processamento falhou. Verifique o arquivo e tente novamente.'
    setError(msg)
    toast({ type: 'error', title: 'Erro no processamento', message: msg })
  }

  const resetUpload = () => {
    setJobId(null)
    setFile(null)
    setError(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  // ── Render: estado pós-upload (polling) ───────────────────────────────────

  if (jobId) {
    return (
      <div className="p-8 max-w-2xl mx-auto">
        <div className="mb-8">
          <h1 className="font-display font-bold text-3xl text-white">Processando edital</h1>
          <p className="text-gray-400 font-body mt-1">
            O documento está sendo indexado. Isso pode levar alguns minutos.
          </p>
        </div>

        <div className="card border-azure/20 space-y-4">
          {/* Arquivo enviado */}
          <div className="flex items-center gap-3 pb-4 border-b border-slate-border">
            <div className="w-10 h-10 rounded-xl bg-azure/10 border border-azure/20 flex items-center justify-center text-azure-glow font-mono text-xs flex-shrink-0">
              PDF
            </div>
            <div className="min-w-0">
              <p className="text-sm font-display font-semibold text-white truncate">{file?.name}</p>
              <p className="text-xs text-gray-500 font-mono mt-0.5">
                {file ? `${(file.size / 1024).toFixed(0)} KB · ` : ''}enviado com sucesso
              </p>
            </div>
            <span className="ml-auto text-green-match font-mono text-sm flex-shrink-0">✓</span>
          </div>

          {/* JobPoller */}
          <div>
            <p className="text-xs text-gray-500 font-mono uppercase tracking-wider mb-3">
              Progresso do processamento
            </p>
            <JobPoller
              jobId={jobId}
              onDone={handleJobDone}
              onFailed={handleJobFailed}
            />
          </div>

          {/* Erro inline (se falhou) */}
          {error && (
            <div className="flex items-start gap-2 px-4 py-3 rounded-lg bg-red-fail/5 border border-red-fail/20">
              <span className="text-red-fail font-mono text-sm mt-0.5">✕</span>
              <p className="text-sm text-red-fail font-body leading-relaxed">{error}</p>
            </div>
          )}
        </div>

        <div className="flex gap-3 mt-4">
          <button onClick={() => navigate('/jobs')} className="btn-ghost text-sm">
            Ver todos os Jobs
          </button>
          <button onClick={resetUpload} className="btn-ghost text-sm">
            Enviar outro arquivo
          </button>
        </div>
      </div>
    )
  }

  // ── Render: formulário de upload ──────────────────────────────────────────

  return (
    <div className="p-8 max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-display font-bold text-3xl text-white">Upload de Edital</h1>
        <p className="text-gray-400 font-body mt-1">
          Envie um PDF para análise automática de requisitos e matching de produtos.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">

        {/* Drop zone */}
        <div
          className={`border-2 border-dashed rounded-xl p-12 flex flex-col items-center
                      justify-center cursor-pointer transition-all duration-200
                      ${dragging
                        ? 'border-azure bg-azure/5 scale-[1.01]'
                        : 'border-slate-border hover:border-azure/50 hover:bg-slate-hover'
                      }`}
          onClick={() => inputRef.current?.click()}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
        >
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf"
            className="hidden"
            onChange={onFileChange}
          />

          {file ? (
            /* Arquivo selecionado */
            <div className="flex flex-col items-center text-center">
              <div className="w-14 h-14 rounded-2xl bg-azure/10 border border-azure/30 flex items-center justify-center text-azure-glow font-mono font-bold mb-3">
                PDF
              </div>
              <p className="font-display font-semibold text-white text-sm">{file.name}</p>
              <p className="text-xs text-gray-500 font-mono mt-1">
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </p>
              <button
                type="button"
                className="mt-3 text-xs font-mono text-gray-500 hover:text-red-fail transition-colors px-3 py-1 rounded border border-transparent hover:border-red-fail/30"
                onClick={(e) => { e.stopPropagation(); resetUpload() }}
              >
                ✕ Remover arquivo
              </button>
            </div>
          ) : (
            /* Estado inicial */
            <div className="flex flex-col items-center text-center">
              <div className={`w-16 h-16 rounded-2xl border-2 border-dashed flex items-center justify-center text-3xl mb-4 transition-all ${
                dragging ? 'border-azure text-azure-glow' : 'border-slate-border'
              }`}>
                📄
              </div>
              <p className="font-display font-semibold text-white">
                {dragging ? 'Solte o arquivo aqui' : 'Arraste um PDF aqui'}
              </p>
              <p className="text-sm text-gray-500 mt-1">ou clique para selecionar</p>
              <p className="text-xs text-gray-600 font-mono mt-3">
                Somente .pdf · máx. {MAX_FILE_MB} MB
              </p>
            </div>
          )}
        </div>

        {/* Erro */}
        {error && (
          <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-red-fail/5 border border-red-fail/20">
            <span className="text-red-fail font-mono text-sm flex-shrink-0">✕</span>
            <p className="text-sm text-red-fail font-body">{error}</p>
          </div>
        )}

        {/* Informações adicionais */}
        {!file && !error && (
          <div className="flex items-start gap-3 px-4 py-3 rounded-lg bg-azure/5 border border-azure/15">
            <span className="text-azure-glow font-mono text-xs mt-0.5 flex-shrink-0">ℹ</span>
            <p className="text-xs text-gray-400 font-body leading-relaxed">
              Após o upload, o documento será processado automaticamente: OCR, chunking e indexação para busca semântica e matching de produtos.
            </p>
          </div>
        )}

        {/* Ações */}
        <div className="flex gap-3">
          <button
            type="button"
            className="btn-ghost"
            onClick={() => navigate('/dashboard')}
            disabled={loading}
          >
            Cancelar
          </button>
          <button
            type="submit"
            className="btn-primary flex items-center gap-2 disabled:opacity-40"
            disabled={!file || loading}
          >
            {loading ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Enviando…
              </>
            ) : (
              <>
                <span className="font-mono text-base leading-none">↑</span>
                Enviar edital
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  )
}
