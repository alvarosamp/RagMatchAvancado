/**
 * pages/Dashboard.jsx
 * ────────────────────
 * Lista todos os editais do tenant com acesso rápido às ações.
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { editaisApi, exportApi, downloadBlob } from '../api/client'
import { useAuth } from '../contexts/AuthContext'

export default function Dashboard() {
  const [editais,  setEditais]  = useState([])
  const [loading,  setLoading]  = useState(true)
  const [exporting, setExporting] = useState(null)
  const { user, isEditor }      = useAuth()
  const navigate                = useNavigate()

  useEffect(() => {
    editaisApi.list()
      .then(r => setEditais(r.data))
      .finally(() => setLoading(false))
  }, [])

  const handleExport = async (id, tipo, filename) => {
    setExporting(`${id}-${tipo}`)
    try {
      const fn = { xlsx: exportApi.xlsx, pdf: exportApi.pdf, csv: exportApi.csv }[tipo]
      const res = await fn(id)
      downloadBlob(res.data, filename)
    } catch { /* silencioso */ }
    finally { setExporting(null) }
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <p className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-1">{user?.tenant?.slug}</p>
          <h1 className="font-display font-bold text-3xl text-white">Dashboard</h1>
          <p className="text-gray-400 font-body mt-1">{editais.length} edital{editais.length !== 1 && 'is'} processados</p>
        </div>
        {isEditor && (
          <button onClick={() => navigate('/upload')} className="btn-primary flex items-center gap-2">
            <span className="font-mono text-lg leading-none">↑</span> Novo Edital
          </button>
        )}
      </div>

      {/* Lista */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {[1,2,3].map(i => (
            <div key={i} className="card animate-pulse h-44">
              <div className="h-4 bg-slate-border rounded w-3/4 mb-3" />
              <div className="h-3 bg-slate-border rounded w-1/2 mb-6" />
              <div className="h-3 bg-slate-border rounded w-full mb-2" />
              <div className="h-3 bg-slate-border rounded w-2/3" />
            </div>
          ))}
        </div>
      ) : editais.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <div className="w-16 h-16 rounded-2xl border-2 border-dashed border-slate-border flex items-center justify-center text-3xl mb-4">📄</div>
          <p className="font-display font-semibold text-white text-lg">Nenhum edital ainda</p>
          <p className="text-gray-500 text-sm mt-1 mb-6">Faça upload de um PDF para começar</p>
          {isEditor && <button onClick={() => navigate('/upload')} className="btn-primary">Fazer upload</button>}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {editais.map((e, i) => (
            <div
              key={e.id}
              className="card hover:border-azure/40 hover:bg-slate-hover cursor-pointer transition-all duration-200 group animate-fade-up"
              style={{ animationDelay: `${i * 60}ms` }}
              onClick={() => navigate(`/editais/${e.id}`)}
            >
              {/* Nome */}
              <div className="flex items-start gap-3 mb-4">
                <div className="w-9 h-9 rounded-lg bg-azure/10 border border-azure/20 flex items-center justify-center text-azure-glow font-mono text-sm flex-shrink-0 group-hover:bg-azure/20 transition-colors">
                  PDF
                </div>
                <div className="min-w-0">
                  <p className="font-display font-semibold text-white text-sm leading-snug truncate group-hover:text-azure-glow transition-colors">
                    {e.filename}
                  </p>
                  <p className="text-xs text-gray-500 font-mono mt-0.5">
                    {e.parsed_at ? new Date(e.parsed_at).toLocaleDateString('pt-BR') : '—'}
                  </p>
                </div>
              </div>

              {/* Stats */}
              <div className="flex gap-4 mb-4">
                <div>
                  <p className="text-xs text-gray-500 font-mono">chunks</p>
                  <p className="font-display font-bold text-white">{e.chunks}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 font-mono">requisitos</p>
                  <p className="font-display font-bold text-white">{e.requirements}</p>
                </div>
              </div>

              {/* Exportar */}
              <div className="flex gap-2 pt-3 border-t border-slate-border" onClick={ev => ev.stopPropagation()}>
                {[['xlsx','XLSX'], ['pdf','PDF'], ['csv','CSV']].map(([tipo, label]) => (
                  <button
                    key={tipo}
                    disabled={!!exporting}
                    onClick={() => handleExport(e.id, tipo, `edital_${e.id}_resultado.${tipo}`)}
                    className="flex-1 py-1.5 text-xs font-mono text-gray-400 hover:text-white border border-slate-border hover:border-azure/40 rounded-lg transition-all duration-150 disabled:opacity-40"
                  >
                    {exporting === `${e.id}-${tipo}` ? '…' : label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
