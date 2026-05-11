/**
 * pages/AnaliseAta.jsx
 * ─────────────────────
 * Exibe os itens extraídos pelo pipeline LLM (pipelinellm.py) de um edital.
 * Dados: ResultadoAnalise { numero_ata, orgao, data_assinatura, vigencia,
 *                           objeto, itens: ItemAta[], tokens_usados, aviso }
 */

import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { llmApi } from '../api/client'
import { useToast } from '../contexts/ToastContext'

// ── Sub-components ────────────────────────────────────────────────────────────

function Currency({ value }) {
  if (value == null) return <span className="text-gray-600 font-mono text-xs">—</span>
  return (
    <span className="text-white font-mono text-xs">
      {Number(value).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
    </span>
  )
}

function TipoTag({ text }) {
  if (!text) return null
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono
                     bg-azure/10 border border-azure/20 text-azure-glow whitespace-nowrap">
      {text}
    </span>
  )
}

function SpecList({ specs }) {
  if (!specs?.length) return null
  const visible = specs.slice(0, 3)
  const rest    = specs.length - 3
  return (
    <div className="flex flex-wrap gap-1 mt-1.5">
      {visible.map((s, i) => (
        <span key={i} className="text-[10px] font-mono text-gray-600 bg-ink-50 border border-slate-border/40 px-1.5 py-0.5 rounded">
          {s}
        </span>
      ))}
      {rest > 0 && (
        <span className="text-[10px] text-gray-600 font-mono">+{rest}</span>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AnaliseAta() {
  const { id }    = useParams()
  const navigate  = useNavigate()
  const { toast } = useToast()

  const [data,       setData]       = useState(null)
  const [loading,    setLoading]    = useState(true)
  const [notFound,   setNotFound]   = useState(false)
  const [analyzing,  setAnalyzing]  = useState(false)
  const [filterTipo, setFilterTipo] = useState('all')
  const [search,     setSearch]     = useState('')
  const [expanded,   setExpanded]   = useState(null)

  const load = () => {
    setLoading(true)
    setNotFound(false)
    llmApi.results(id)
      .then(r => setData(r.data))
      .catch(err => {
        if (err.response?.status === 404) setNotFound(true)
        else toast({ type: 'error', message: err.response?.data?.detail || 'Erro ao carregar análise.' })
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [id])

  const handleAnalyze = async () => {
    setAnalyzing(true)
    try {
      await llmApi.analyze(id)
      toast({ type: 'info', title: 'Análise iniciada', message: 'O pipeline LLM está processando a ata. Aguarde alguns instantes.' })
      setTimeout(load, 3000)
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Erro ao iniciar análise LLM.' })
    } finally {
      setAnalyzing(false)
    }
  }

  // Tipos únicos para filtros
  const tipos = data?.itens ? [...new Set(data.itens.map(i => i.tipo).filter(Boolean))].sort() : []

  // Itens filtrados
  const itens = (data?.itens || []).filter(item => {
    if (filterTipo !== 'all' && item.tipo !== filterTipo) return false
    if (search) {
      const s = search.toLowerCase()
      return (
        item.descricao?.toLowerCase().includes(s)  ||
        item.marca?.toLowerCase().includes(s)      ||
        item.modelo?.toLowerCase().includes(s)     ||
        item.fornecedor?.toLowerCase().includes(s) ||
        item.tipo?.toLowerCase().includes(s)       ||
        item.numero_item?.toLowerCase().includes(s)
      )
    }
    return true
  })

  const totalValor = itens.reduce((s, i) => s + (i.valor_total || 0), 0)

  const exportCsv = () => {
    const hdrs = ['Nº', 'Tipo', 'Marca', 'Modelo', 'Descrição', 'Qtd', 'Unidade',
                  'Vlr Unitário', 'Vlr Total', 'Fornecedor', 'CNPJ']
    const rows = itens.map(it => [
      it.numero_item || '',
      it.tipo        || '',
      it.marca       || '',
      it.modelo      || '',
      `"${(it.descricao   || '').replace(/"/g, '""')}"`,
      it.quantidade  ?? '',
      it.unidade     || '',
      it.valor_unitario ?? '',
      it.valor_total    ?? '',
      `"${(it.fornecedor  || '').replace(/"/g, '""')}"`,
      it.cnpj_fornecedor || '',
    ].join(','))
    const csv  = [hdrs.join(','), ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url; a.download = `analise_ata_edital${id}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  // ── Loading skeleton ──────────────────────────────────────────────────────
  if (loading) return (
    <div className="p-6 space-y-4">
      {[...Array(7)].map((_, i) => (
        <div key={i} className="h-12 rounded-xl bg-slate-card border border-slate-border animate-pulse" />
      ))}
    </div>
  )

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="p-6 space-y-6 min-h-screen">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <button
            onClick={() => navigate(`/editais/${id}`)}
            className="text-xs font-mono text-gray-500 hover:text-azure-glow transition-colors mb-2 flex items-center gap-1"
          >
            ← Edital #{id}
          </button>
          <h1 className="font-display font-black text-2xl text-white">Análise LLM da Ata</h1>
          <p className="text-sm text-gray-500 font-mono mt-1">
            Itens extraídos automaticamente pelo pipeline · edital #{id}
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {data?.itens?.length > 0 && (
            <button onClick={exportCsv} className="btn-ghost text-sm px-4 py-2 flex items-center gap-2">
              <span>↓</span> CSV
            </button>
          )}
          <button
            onClick={handleAnalyze}
            disabled={analyzing}
            className="btn-primary text-sm px-4 py-2 flex items-center gap-2 disabled:opacity-40"
          >
            {analyzing ? (
              <>
                <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Analisando…
              </>
            ) : (
              <><span className="font-mono">⟳</span> {data ? 'Re-analisar' : 'Analisar agora'}</>
            )}
          </button>
        </div>
      </div>

      {/* Análise não encontrada */}
      {notFound && (
        <div className="card border border-amber/20 bg-amber/5 text-center py-14">
          <div className="text-4xl mb-3">🔍</div>
          <p className="font-display font-bold text-white text-lg mb-1">Análise LLM não encontrada</p>
          <p className="text-sm text-gray-400 mb-5 max-w-sm mx-auto leading-relaxed">
            Este edital ainda não passou pelo pipeline LLM. Clique abaixo para extrair os itens da ata.
          </p>
          <button
            onClick={handleAnalyze}
            disabled={analyzing}
            className="btn-primary disabled:opacity-40"
          >
            {analyzing ? 'Analisando…' : 'Analisar agora'}
          </button>
        </div>
      )}

      {data && (
        <>
          {/* Metadados da ata */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'Nº da Ata',   value: data.numero_ata      || '—' },
              { label: 'Órgão',       value: data.orgao            || '—' },
              { label: 'Assinatura',  value: data.data_assinatura  || '—' },
              { label: 'Vigência',    value: data.vigencia         || '—' },
            ].map(({ label, value }) => (
              <div key={label} className="card p-4">
                <p className="text-[10px] text-gray-500 font-mono uppercase tracking-wider mb-1">{label}</p>
                <p className="text-sm text-white font-body font-medium truncate" title={value}>{value}</p>
              </div>
            ))}
          </div>

          {/* Objeto */}
          {data.objeto && (
            <div className="card p-4 border-azure/15">
              <p className="text-[10px] text-gray-500 font-mono uppercase tracking-wider mb-1.5">Objeto</p>
              <p className="text-sm text-gray-200 font-body leading-relaxed">{data.objeto}</p>
            </div>
          )}

          {/* Aviso */}
          {data.aviso && (
            <div className="flex items-start gap-2 px-4 py-3 rounded-lg bg-amber/5 border border-amber/20">
              <span className="text-amber font-mono text-xs mt-0.5">⚠</span>
              <p className="text-xs text-amber font-mono leading-relaxed">{data.aviso}</p>
            </div>
          )}

          {/* Stats */}
          <div className="grid grid-cols-3 gap-3">
            <div className="card p-4">
              <p className="text-xs text-gray-500 font-mono">Total de itens</p>
              <p className="text-3xl font-display font-black text-white mt-1">{data.itens?.length || 0}</p>
            </div>
            <div className="card p-4">
              <p className="text-xs text-gray-500 font-mono">Tipos únicos</p>
              <p className="text-3xl font-display font-black text-white mt-1">{tipos.length}</p>
            </div>
            <div className="card p-4">
              <p className="text-xs text-gray-500 font-mono">Valor total (filtrado)</p>
              <p className="text-xl font-display font-black text-white mt-1 truncate">
                {totalValor > 0
                  ? totalValor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
                  : '—'}
              </p>
            </div>
          </div>

          {/* Filtros */}
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              placeholder="Buscar por descrição, marca, modelo, fornecedor…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="input flex-1 text-sm py-2"
            />
            <div className="flex gap-1 flex-wrap">
              <button
                onClick={() => setFilterTipo('all')}
                className={`px-3 py-1.5 rounded-lg text-xs font-mono border transition-all ${
                  filterTipo === 'all'
                    ? 'bg-azure text-white border-azure'
                    : 'text-gray-400 border-slate-border hover:text-white hover:bg-slate-hover'
                }`}
              >
                Todos ({data.itens?.length || 0})
              </button>
              {tipos.map(tipo => (
                <button
                  key={tipo}
                  onClick={() => setFilterTipo(tipo)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-mono border transition-all ${
                    filterTipo === tipo
                      ? 'bg-azure text-white border-azure'
                      : 'text-gray-400 border-slate-border hover:text-white hover:bg-slate-hover'
                  }`}
                >
                  {tipo} ({data.itens.filter(i => i.tipo === tipo).length})
                </button>
              ))}
            </div>
          </div>

          {/* Tabela de itens */}
          <div className="card p-0 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-ink-100 border-b border-slate-border">
                  <tr>
                    {['#', 'Tipo', 'Marca / Modelo', 'Descrição / Specs', 'Qtd', 'Vlr Unit.', 'Vlr Total', 'Fornecedor'].map(h => (
                      <th key={h}
                          className="px-4 py-3 text-left text-xs font-mono text-gray-500 uppercase tracking-wider whitespace-nowrap">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-border/20">
                  {itens.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-14 text-center">
                        <div className="text-3xl mb-2">🔍</div>
                        <p className="text-sm text-gray-500 font-body">Nenhum item encontrado com este filtro.</p>
                      </td>
                    </tr>
                  ) : (
                    itens.map((item, i) => {
                      const isExpanded = expanded === i
                      return (
                        <tr
                          key={i}
                          className="hover:bg-slate-hover/20 transition-colors cursor-pointer align-top"
                          onClick={() => setExpanded(isExpanded ? null : i)}
                        >
                          {/* Nº */}
                          <td className="px-4 py-3 font-mono text-xs text-gray-500 whitespace-nowrap">
                            {item.numero_item || i + 1}
                          </td>

                          {/* Tipo */}
                          <td className="px-4 py-3 whitespace-nowrap">
                            <TipoTag text={item.tipo} />
                          </td>

                          {/* Marca / Modelo */}
                          <td className="px-4 py-3 whitespace-nowrap min-w-[120px]">
                            <p className="text-xs text-white font-medium">{item.marca || '—'}</p>
                            {item.modelo && (
                              <p className="text-[10px] text-gray-500 font-mono mt-0.5">{item.modelo}</p>
                            )}
                          </td>

                          {/* Descrição + Specs */}
                          <td className="px-4 py-3 max-w-[300px]">
                            <p className={`text-xs text-gray-200 leading-relaxed ${isExpanded ? '' : 'line-clamp-2'}`}>
                              {item.descricao || '—'}
                            </p>
                            <SpecList specs={item.especificacoes} />
                            {isExpanded && item.observacoes && (
                              <p className="text-[10px] text-amber font-mono mt-2 leading-relaxed">
                                ℹ {item.observacoes}
                              </p>
                            )}
                          </td>

                          {/* Qtd */}
                          <td className="px-4 py-3 whitespace-nowrap">
                            <p className="text-xs text-white">{item.quantidade ?? '—'}</p>
                            {item.unidade && (
                              <p className="text-[10px] text-gray-600 font-mono">{item.unidade}</p>
                            )}
                          </td>

                          {/* Vlr Unit */}
                          <td className="px-4 py-3 whitespace-nowrap">
                            <Currency value={item.valor_unitario} />
                          </td>

                          {/* Vlr Total */}
                          <td className="px-4 py-3 whitespace-nowrap">
                            <Currency value={item.valor_total} />
                          </td>

                          {/* Fornecedor */}
                          <td className="px-4 py-3 max-w-[180px]">
                            <p className="text-xs text-gray-200 truncate" title={item.fornecedor}>
                              {item.fornecedor || '—'}
                            </p>
                            {item.cnpj_fornecedor && (
                              <p className="text-[10px] text-gray-600 font-mono mt-0.5">{item.cnpj_fornecedor}</p>
                            )}
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>

            {itens.length > 0 && (
              <div className="px-4 py-2.5 border-t border-slate-border/30 bg-ink-100 flex items-center justify-between">
                <p className="text-xs text-gray-600 font-mono">
                  {itens.length} item{itens.length !== 1 ? 's' : ''}
                  {data.tokens_usados > 0 && ` · ${data.tokens_usados.toLocaleString('pt-BR')} tokens usados`}
                </p>
                {totalValor > 0 && (
                  <p className="text-xs text-gray-500 font-mono">
                    Total:{' '}
                    <span className="text-white">
                      {totalValor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                    </span>
                  </p>
                )}
              </div>
            )}
          </div>

          <p className="text-[10px] text-gray-600 font-mono text-center">
            Clique em uma linha para expandir a descrição completa
          </p>
        </>
      )}
    </div>
  )
}
