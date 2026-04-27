/**
 * pages/EditalDetail.jsx
 * ───────────────────────
 * Resultados de matching + acesso ao chat RAG do edital.
 */

import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { editaisApi, exportApi, downloadBlob } from '../api/client'
import { useToast } from '../contexts/ToastContext'

const STATUS_CFG = {
  atende:     { label: 'Atende',      cls: 'badge-atende',    dot: 'bg-green-match' },
  nao_atende: { label: 'Não atende',  cls: 'badge-falhou',    dot: 'bg-red-fail'    },
  verificar:  { label: 'Verificar',   cls: 'badge-verificar', dot: 'bg-yellow-warn' },
}

export default function EditalDetail() {
  const { id }                    = useParams()
  const navigate                  = useNavigate()
  const { toast }                 = useToast()
  const [results,   setResults]   = useState([])
  const [loading,   setLoading]   = useState(true)
  const [selected,  setSelected]  = useState(null)
  const [exporting, setExporting] = useState(null)

  useEffect(() => {
    editaisApi.results(id)
      .then(r => {
        const byProduct = {}
        for (const row of r.data.results) {
          if (!byProduct[row.product]) byProduct[row.product] = { product: row.product, rows: [] }
          byProduct[row.product].rows.push(row)
        }
        const produtos = Object.values(byProduct).map(p => {
          const scores = p.rows.map(r => r.score || 0)
          const avg    = scores.reduce((a, b) => a + b, 0) / (scores.length || 1)
          return { ...p, avgScore: avg }
        }).sort((a, b) => b.avgScore - a.avgScore)

        setResults(produtos)
        if (produtos[0]) setSelected(produtos[0].product)
      })
      .finally(() => setLoading(false))
  }, [id])

  const handleExport = async (tipo) => {
    setExporting(tipo)
    try {
      const fn  = { xlsx: exportApi.xlsx, pdf: exportApi.pdf, csv: exportApi.csv }[tipo]
      const res = await fn(id)
      downloadBlob(res.data, `edital_${id}_resultado.${tipo}`)
      toast({ type: 'success', message: `Exportação ${tipo.toUpperCase()} concluída.` })
    } catch (err) {
      toast({
        type:    'error',
        title:   'Erro ao exportar',
        message: err.response?.data?.detail || `Não foi possível exportar como ${tipo.toUpperCase()}.`,
      })
    } finally {
      setExporting(null)
    }
  }

  const selectedData = results.find(p => p.product === selected)

  if (loading) return (
    <div className="p-8">
      <div className="animate-pulse space-y-4">
        <div className="h-8 bg-slate-border rounded w-64" />
        <div className="h-4 bg-slate-border rounded w-48" />
        <div className="grid grid-cols-3 gap-4 mt-6">
          {[1,2,3].map(i => <div key={i} className="h-24 bg-slate-card rounded-xl border border-slate-border" />)}
        </div>
      </div>
    </div>
  )

  return (
    <div className="p-8">

      {/* ── Header ──────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <button
              onClick={() => navigate('/dashboard')}
              className="text-xs font-mono text-gray-500 hover:text-azure-glow transition-colors"
            >
              ← Dashboard
            </button>
            <span className="text-gray-600 text-xs">/</span>
            <p className="text-xs font-mono text-gray-500">Edital #{id}</p>
          </div>
          <h1 className="font-display font-black text-3xl text-white">Resultados</h1>
          <p className="text-gray-400 text-sm mt-1">{results.length} produtos analisados</p>
        </div>

        {/* Ações do header */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Análise LLM */}
          <button
            onClick={() => navigate(`/editais/${id}/analise-llm`)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-amber/30 bg-amber/10 hover:border-amber/60 text-amber font-body text-sm transition-all duration-200"
          >
            <span>🤖</span>
            Análise LLM
          </button>

          {/* Chat RAG — destaque */}
          <button
            onClick={() => navigate(`/editais/${id}/chat`)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-azure/20 to-amber/20 border border-azure/30 hover:border-azure/60 text-azure-glow font-body text-sm transition-all duration-200 hover:shadow-lg hover:shadow-azure/10"
          >
            <span>💬</span>
            Perguntar ao edital
          </button>

          {/* Exportar */}
          {[['xlsx','XLS ↓'], ['csv','CSV ↓']].map(([tipo, label]) => (
            <button
              key={tipo}
              disabled={!!exporting}
              onClick={() => handleExport(tipo)}
              className="btn-ghost text-xs px-3 py-2 disabled:opacity-40"
            >
              {exporting === tipo ? '…' : label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">

        {/* ── Ranking lateral ──────────────────────────────────────── */}
        <div className="col-span-4 space-y-2">
          <p className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-3">
            Ranking de Produtos
          </p>
          {results.length === 0 ? (
            <div className="card text-center py-12 text-gray-500 text-sm">
              Nenhum resultado ainda.<br />Execute o matching primeiro.
            </div>
          ) : (
            results.map((p, i) => {
              const pct        = Math.round(p.avgScore * 100)
              const isSelected = selected === p.product
              return (
                <button
                  key={p.product}
                  onClick={() => setSelected(p.product)}
                  className={`w-full text-left card py-3.5 px-4 transition-all duration-200
                    ${isSelected
                      ? 'border-azure/50 bg-azure/5 shadow-sm shadow-azure/10'
                      : 'hover:border-slate-border/80 hover:bg-slate-hover'
                    }`}
                >
                  <div className="flex items-center gap-3">
                    <span className={`font-display font-bold text-lg w-6 flex-shrink-0 ${i === 0 ? 'text-amber' : 'text-gray-600'}`}>
                      {i + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className={`font-mono text-sm font-medium truncate ${isSelected ? 'text-azure-glow' : 'text-white'}`}>
                        {p.product}
                      </p>
                      <div className="mt-1.5 h-1 bg-slate-border rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-700 ${pct >= 75 ? 'bg-green-match' : pct >= 45 ? 'bg-yellow-warn' : 'bg-red-fail'}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                    <span className={`font-mono text-xs font-bold flex-shrink-0 ${pct >= 75 ? 'text-green-match' : pct >= 45 ? 'text-yellow-warn' : 'text-red-fail'}`}>
                      {pct}%
                    </span>
                  </div>
                </button>
              )
            })
          )}
        </div>

        {/* ── Detalhes do produto selecionado ──────────────────────── */}
        <div className="col-span-8">
          {selectedData ? (
            <>
              <div className="flex items-center justify-between mb-5">
                <div>
                  <p className="font-display font-bold text-xl text-white">{selectedData.product}</p>
                  <p className="text-xs text-gray-500 font-mono mt-0.5">{selectedData.rows.length} requisito{selectedData.rows.length !== 1 ? 's' : ''} avaliado{selectedData.rows.length !== 1 ? 's' : ''}</p>
                </div>
                <div className="text-right">
                  <span className="font-mono text-3xl font-black text-azure-glow">
                    {Math.round(selectedData.avgScore * 100)}%
                  </span>
                  <p className="text-xs text-gray-500 font-mono">compatibilidade</p>
                </div>
              </div>

              {/* Barra de progresso geral */}
              <div className="h-1.5 bg-slate-border rounded-full overflow-hidden mb-5">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-azure to-amber transition-all duration-1000"
                  style={{ width: `${Math.round(selectedData.avgScore * 100)}%` }}
                />
              </div>

              <div className="space-y-2">
                {selectedData.rows.map((row, i) => {
                  const cfg = STATUS_CFG[row.status] || STATUS_CFG.verificar
                  const pct = Math.round((row.score || 0) * 100)
                  return (
                    <div
                      key={i}
                      className="card py-4 animate-fade-up"
                      style={{ animationDelay: `${i * 40}ms` }}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3">
                          <div className={`w-2 h-2 rounded-full flex-shrink-0 ${cfg.dot}`} />
                          <p className="font-mono text-sm text-white font-medium">{row.attribute}</p>
                        </div>
                        <span className={cfg.cls}>{cfg.label}</span>
                      </div>

                      <div className="h-0.5 bg-slate-border rounded-full overflow-hidden mb-3">
                        <div
                          className={`h-full rounded-full transition-all duration-700 ${
                            row.status === 'atende'     ? 'bg-green-match' :
                            row.status === 'verificar'  ? 'bg-yellow-warn' : 'bg-red-fail'
                          }`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>

                      {row.reasoning && (
                        <p className="text-xs text-gray-500 font-body leading-relaxed">{row.reasoning}</p>
                      )}
                    </div>
                  )
                })}
              </div>
            </>
          ) : (
            <div className="card h-64 flex flex-col items-center justify-center gap-3 text-gray-500">
              <span className="text-3xl">📊</span>
              <p className="text-sm">Selecione um produto no ranking</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
