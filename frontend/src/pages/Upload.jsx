/**
 * pages/Upload.jsx
 * ─────────────────
 * Tela de upload de edital PDF — envia o arquivo para a API e redireciona
 * para o dashboard após o enfileiramento do job de processamento.
 */

import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { editaisApi } from '../api/client'

export default function Upload() {
  const [file,     setFile]     = useState(null)
  const [dragging, setDragging] = useState(false)
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState(null)
  const inputRef               = useRef(null)
  const navigate               = useNavigate()

  // ── drag & drop ────────────────────────────────────────────────────────────
  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped?.type === 'application/pdf') {
      setFile(dropped)
      setError(null)
    } else {
      setError('Apenas arquivos PDF são aceitos.')
    }
  }

  const onFileChange = (e) => {
    const chosen = e.target.files[0]
    if (chosen) { setFile(chosen); setError(null) }
  }

  // ── submit ─────────────────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file) { setError('Selecione um arquivo PDF.'); return }

    setLoading(true)
    setError(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      await editaisApi.upload(formData)
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Erro ao enviar arquivo. Tente novamente.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-8 max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-display font-bold text-3xl text-white">Upload de Edital</h1>
        <p className="text-gray-400 font-body mt-1">Envie um PDF para análise e matching automático de produtos.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Drop zone */}
        <div
          className={`border-2 border-dashed rounded-xl p-12 flex flex-col items-center justify-center cursor-pointer transition-all duration-200
            ${dragging ? 'border-azure bg-azure/5' : 'border-slate-border hover:border-azure/50 hover:bg-slate-hover'}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
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
            <>
              <div className="w-12 h-12 rounded-xl bg-azure/10 border border-azure/20 flex items-center justify-center text-azure-glow font-mono text-lg mb-3">
                PDF
              </div>
              <p className="font-display font-semibold text-white text-sm">{file.name}</p>
              <p className="text-xs text-gray-500 font-mono mt-1">{(file.size / 1024).toFixed(0)} KB</p>
              <button
                type="button"
                className="mt-3 text-xs text-gray-500 hover:text-red-400 transition-colors"
                onClick={(e) => { e.stopPropagation(); setFile(null) }}
              >
                Remover
              </button>
            </>
          ) : (
            <>
              <div className="w-14 h-14 rounded-2xl border-2 border-dashed border-slate-border flex items-center justify-center text-3xl mb-4">
                📄
              </div>
              <p className="font-display font-semibold text-white">Arraste um PDF aqui</p>
              <p className="text-sm text-gray-500 mt-1">ou clique para selecionar</p>
            </>
          )}
        </div>

        {/* Error */}
        {error && (
          <p className="text-sm text-red-400 font-body bg-red-dim/20 border border-red-fail/20 rounded-lg px-4 py-2.5">
            {error}
          </p>
        )}

        {/* Actions */}
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
            className="btn-primary flex items-center gap-2"
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
