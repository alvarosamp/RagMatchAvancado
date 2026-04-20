/**
 * pages/Dashboard.jsx
 * ────────────────────
 * Painel principal da Tor Tecnologias — lista editais com stats e acesso rápido ao chat.
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { editaisApi, exportApi, downloadBlob } from '../api/client'
import { useAuth } from '../contexts/AuthContext'

function StatCard({ label, value, sub, color = 'azure' }) {
  const colors = {
    azure:  'from-azure/10 to-azure/5 border-azure/20 text-azure-glow',
    green:  'from-green-match/10 to-green-match/5 border-green-match/20 text-green-match',
    amber:  'from-amber/10 to-amber/5 border-amber/20 text-amber',
    yellow: 'from-yellow-warn/10 to-yellow-warn/5 border-yellow-warn/20 text-yellow-warn',
  }
  return (
    <div className={`rounded-xl border bg-gradient-to-br p-5 ${colors[color]}`}>
      <p className="text-xs font-mono text-gray-400 uppercase tracking-widest mb-1">{label}</p>
      <p className="font-display font-black text-3xl text-white">{value}</p>
      {sub && <p className="text-xs text-gray-500 font-body mt-1">{sub}</p>}
    </div>
  )
}

export default function Dashboard() {
  const [editais,   setEditais]   = useState([])
  const [loading,   setLoading]   = useState(true)
  const [exporting, setExporting] = useState(null)
  const { user, isEditor } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    editaisApi.list()
      .then(r => setEditais(r.data))
      .finally(() => setLoading(false))
  }, [])

  const handleExport = async (e, id, tipo) => {
    e.stopPropagation()
    setExporting(`${id}-${tipo}`)
    try {
      const fn = { xlsx: exportApi.xlsx, pdf: exportApi.pdf, csv: exportApi.csv }[tipo]
      const res = await fn(id)
      downloadBlob(res.data, `edital_${id}_resultado.${tipo}`)
    } catch { }
    finally { setExporting(null) }
  }

  const totalChunks = editais.reduce((s, e) => s + (e.chunks || 0), 0)
  const totalReqs   = editais.reduce((s, e) => s + (e.requirements || 0), 0)

  return (
    <div className="p-8">

      {/* ── Header ────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <p className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-1">
            {user?.tenant?.name || 'Tor Tec'}
          </p>
          <h1 className="font-display font-black text-3xl text-white">Dashboard</h1>
          <p className="text-gray-400 font-body text-sm mt-1">
            Análise de editais e atas de licitação
          </p>
        </div>
        {isEditor && (
          <button
            onClick={() => navigate('/upload')}
            className="btn-primary flex items-center gap-2"
          >
            <span className="font-mono text-base leading-none">↑</span>
            Novo Edital
          </button>
        )}
      </div>

      {/* ── Stats ─────────────────────────────────────────────────────── */}
      {!loading && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            label="Editais"
            value={editais.length}
            sub="documentos processados"
            color="azure"
          />
          <StatCard
            label="Chunks"
            value={totalChunks.toLocaleString('pt-BR')}
            sub="fragmentos indexados"
            color="yellow"
          />
          <StatCard
            label="Requisitos"
            value={totalReqs}
            sub="critérios extraídos"
            color="green"
          />
          <StatCard
            label="Foco"
            value="Switch"
            sub="Tor Tec"
            color="amber"
          />
        </div>
      )}

      {/* ── Lista de editais ──────────────────────────────────────────── */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="card animate-pulse h-52">
              <div className="h-4 bg-slate-border rounded w-3/4 mb-3" />
              <div className="h-3 bg-slate-border rounded w-1/2 mb-6" />
              <div className="h-3 bg-slate-border rounded w-full mb-2" />
              <div className="h-3 bg-slate-border rounded w-2/3" />
            </div>
          ))}
        </div>
      ) : editais.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-28 text-center">
          <div className="w-16 h-16 rounded-2xl border-2 border-dashed border-slate-border flex items-center justify-center text-3xl mb-4">
            📄
          </div>
          <p className="font-display font-semibold text-white text-lg">Nenhum edital ainda</p>
          <p className="text-gray-500 text-sm mt-1 mb-6">Faça upload de um PDF para começar</p>
          {isEditor && (
            <button onClick={() => navigate('/upload')} className="btn-primary">
              Fazer upload
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {editais.map((e, i) => (
            <div
              key={e.id}
              className="card hover:border-azure/40 hover:bg-slate-hover cursor-pointer transition-all duration-200 group animate-fade-up flex flex-col"
              style={{ animationDelay: `${i * 60}ms` }}
              onClick={() => navigate(`/editais/${e.id}`)}
            >
              {/* Nome + ícone */}
              <div className="flex items-start gap-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-azure/20 to-amber/10 border border-azure/20 flex items-center justify-center text-azure-glow font-mono text-xs flex-shrink-0 group-hover:from-azure/30 transition-all">
                  PDF
                </div>
                <div className="min-w-0 flex-1">
                  <p className="font-display font-semibold text-white text-sm leading-snug truncate group-hover:text-azure-glow transition-colors">
                    {e.filename}
                  </p>
                  <p className="text-xs text-gray-500 font-mono mt-0.5">
                    {e.parsed_at ? new Date(e.parsed_at).toLocaleDateString('pt-BR') : '—'}
                  </p>
                </div>
              </div>

              {/* Stats do edital */}
              <div className="flex gap-4 mb-4">
                <div className="flex-1 bg-ink-50 rounded-lg p-3 border border-slate-border">
                  <p className="text-xs text-gray-500 font-mono">chunks</p>
                  <p className="font-display font-bold text-white text-lg">{e.chunks}</p>
                </div>
                <div className="flex-1 bg-ink-50 rounded-lg p-3 border border-slate-border">
                  <p className="text-xs text-gray-500 font-mono">requisitos</p>
                  <p className="font-display font-bold text-white text-lg">{e.requirements}</p>
                </div>
              </div>

              {/* Ações */}
              <div
                className="flex gap-2 pt-3 border-t border-slate-border mt-auto"
                onClick={ev => ev.stopPropagation()}
              >
                {/* Chat RAG */}
                <button
                  onClick={() => navigate(`/editais/${e.id}/chat`)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono text-azure-glow border border-azure/30 hover:border-azure/60 hover:bg-azure/10 rounded-lg transition-all duration-150"
                  title="Perguntar sobre este edital"
                >
                  <span>💬</span> Chat
                </button>

                {/* Exportar */}
                <div className="flex gap-1 ml-auto">
                  {[['xlsx', 'XLS'], ['csv', 'CSV']].map(([tipo, label]) => (
                    <button
                      key={tipo}
                      disabled={!!exporting}
                      onClick={(ev) => handleExport(ev, e.id, tipo)}
                      className="px-2.5 py-1.5 text-xs font-mono text-gray-400 hover:text-white border border-slate-border hover:border-azure/40 rounded-lg transition-all duration-150 disabled:opacity-40"
                    >
                      {exporting === `${e.id}-${tipo}` ? '…' : label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
