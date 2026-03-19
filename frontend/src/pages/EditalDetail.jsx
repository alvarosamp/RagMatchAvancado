1/**
 * pages/EditalDetail.jsx
 * ───────────────────────
 * Resultados de matching de um edital — ranking de produtos + detalhes.
 */

import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { editaisApi, exportApi, downloadBlob } from '../api/client'

const STATUS_CFG = {
  atende:     { label: 'Atende',      cls: 'badge-atende',    dot: 'bg-green-match' },
  nao_atende: { label: 'Não atende',  cls: 'badge-falhou',    dot: 'bg-red-fail'    },
  verificar:  { label: 'Verificar',   cls: 'badge-verificar', dot: 'bg-yellow-warn' },
}

export default function EditalDetail() {
  const { id }                     = useParams()
  const [results,   setResults]    = useState([])
  const [loading,   setLoading]    = useState(true)
  const [selected,  setSelected]   = useState(null)   // produto selecionado
  const [exporting, setExporting]  = useState(null)

  useEffect(() => {
    editaisApi.results(id)
      .then(r => {
        // Agrupa por produto
        const byProduct = {}
        for (const row of r.data.results) {
          if (!byProduct[row.product]) byProduct[row.product] = { product: row.product, rows: [] }
          byProduct[row.product].rows.push(row)
        }
        // Calcula score médio por produto
        const produtos = Object.values(byProduct).map(p => {
          const scores = p.rows.map(r => r.score || 0)
          const avg    = scores.reduce((a,b) => a+b, 0) / (scores.length || 1)
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
      const fn = { xlsx: exportApi.xlsx, pdf: exportApi.pdf, csv: exportApi.csv }[tipo]
      const res = await fn(id)
      downloadBlob(res.data, `edital_${id}_resultado.${tipo}`)
    } catch { }
    finally { setExporting(null) }
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

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <p className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-1">Edital #{id}</p>
          <h1 className="font-display font-bold text-3xl text-white">Resultados</h1>
          <p className="text-gray-400 text-sm mt-1">{results.length} produtos analisados</p>
        </div>

        {/* Exportar */}
        <div className="flex gap-2">
          {[['xlsx','XLSX ↓'], ['pdf','PDF ↓'], ['csv','CSV ↓']].map(([tipo, label]) => (
            <button key={tipo} disabled={!!exporting} onClick={() => handleExport(tipo)}
              className="btn-ghost text-xs px-3 py-2 disabled:opacity-40">
              {exporting === tipo ? '…' : label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">

        {/* ── Ranking lateral ──────────────────────────────────────────── */}
        <div className="col-span-4 space-y-2">
          <p className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-3">Ranking</p>
          {results.map((p, i) => {
            const pct        = Math.round(p.avgScore * 100)
            const isSelected = selected === p.product
            return (
              <button
                key={p.product}
                onClick={() => setSelected(p.product)}
                className={`w-full text-left card py-4 px-4 transition-all duration-200
                  ${isSelected ? 'border-azure/50 bg-azure/5' : 'hover:border-slate-border/80 hover:bg-slate-hover'}`}
              >
                <div className="flex items-center gap-3">
                  <span className={`font-display font-bold text-lg w-6 ${i === 0 ? 'text-amber' : 'text-gray-600'}`}>
                    {i + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className={`font-mono text-sm font-medium truncate ${isSelected ? 'text-azure-glow' : 'text-white'}`}>
                      {p.product}
                    </p>
                    {/* Mini barra de score */}
                    <div className="mt-1.5 h-1 bg-slate-border rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${pct >= 75 ? 'bg-green-match' : pct >= 45 ? 'bg-yellow-warn' : 'bg-red-fail'}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                  <span className={`font-mono text-xs font-bold ${pct >= 75 ? 'text-green-match' : pct >= 45 ? 'text-yellow-warn' : 'text-red-fail'}`}>
                    {pct}%
                  </span>
                </div>
              </button>
            )
          })}
        </div>

        {/* ── Detalhes do produto selecionado ──────────────────────────── */}
        <div className="col-span-8">
          {selectedData ? (
            <>
              <div className="flex items-center justify-between mb-4">
                <p className="font-display font-bold text-xl text-white">{selectedData.product}</p>
                <span className="font-mono text-2xl font-bold text-azure-glow">
                  {Math.round(selectedData.avgScore * 100)}%
                </span>
              </div>

              <div className="space-y-2">
                {selectedData.rows.map((row, i) => {
                  const cfg = STATUS_CFG[row.status] || STATUS_CFG.verificar
                  const pct = Math.round((row.score || 0) * 100)
                  return (
                    <div key={i} className="card py-4 animate-fade-up" style={{ animationDelay: `${i * 40}ms` }}>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3">
                          <div className={`w-2 h-2 rounded-full flex-shrink-0 ${cfg.dot}`} />
                          <p className="font-mono text-sm text-white font-medium">{row.attribute}</p>
                        </div>
                        <span className={cfg.cls}>{cfg.label}</span>
                      </div>

                      {/* Barra de score */}
                      <div className="h-0.5 bg-slate-border rounded-full overflow-hidden mb-3">
                        <div
                          className={`h-full rounded-full transition-all duration-700 ${
                            row.status === 'atende' ? 'bg-green-match' :
                            row.status === 'verificar' ? 'bg-yellow-warn' : 'bg-red-fail'
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
            <div className="card h-64 flex items-center justify-center text-gray-500">
              Selecione um produto no ranking
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
