/**
 * pages/PncpSearch.jsx
 * ─────────────────────
 * Busca e importa editais diretamente do Portal Nacional de Contratações Públicas.
 * Integração com o módulo Pncp/apiPncp do backend.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { pncpApi } from '../api/client'
import { useToast } from '../contexts/ToastContext'

const MODALIDADES = [
  '', 'Pregão Eletrônico', 'Concorrência Eletrônica', 'Concorrência',
  'Tomada de Preços', 'Convite', 'Concurso', 'Leilão',
  'Dispensa de Licitação', 'Inexigibilidade',
]

// ── Componente de resultado ───────────────────────────────────────────────────

function ResultCard({ item, onImport, importing }) {
  const [expanded, setExpanded] = useState(false)
  const isImporting = importing === item.id_pncp

  return (
    <div className="card hover:border-red-600/30 transition-all space-y-3">
      {/* Cabeçalho */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="text-xs font-mono text-red-400 font-semibold">
              {item.id_pncp || item.numero_controle}
            </span>
            {item.modalidade && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded border border-slate-700 text-gray-400">
                {item.modalidade}
              </span>
            )}
            {item.situacao && (
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                item.situacao === 'Publicado'
                  ? 'border-green-match/30 bg-green-match/10 text-green-match'
                  : 'border-slate-700 text-gray-500'
              }`}>
                {item.situacao}
              </span>
            )}
          </div>

          <p className="text-sm text-white font-body font-medium leading-snug">
            {item.objeto || item.titulo || item.descricao_objeto || '—'}
          </p>

          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
            {item.orgao_entidade?.nome_razao_social && (
              <p className="text-xs text-gray-500 font-mono">
                🏛 {item.orgao_entidade.nome_razao_social}
              </p>
            )}
            {item.data_publicacao_pncp && (
              <p className="text-xs text-gray-500 font-mono">
                📅 {new Date(item.data_publicacao_pncp).toLocaleDateString('pt-BR')}
              </p>
            )}
            {item.valor_total_estimado != null && item.valor_total_estimado > 0 && (
              <p className="text-xs text-gray-500 font-mono">
                💰 {Number(item.valor_total_estimado).toLocaleString('pt-BR', {
                  style: 'currency', currency: 'BRL'
                })}
              </p>
            )}
            {item.numero_itens != null && (
              <p className="text-xs text-gray-500 font-mono">
                📦 {item.numero_itens} item{item.numero_itens !== 1 ? 's' : ''}
              </p>
            )}
          </div>
        </div>

        <button
          onClick={() => onImport(item)}
          disabled={!!importing}
          className="btn-primary text-sm px-4 py-2 flex-shrink-0 disabled:opacity-40 flex items-center gap-2"
        >
          {isImporting ? (
            <>
              <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Importando
            </>
          ) : (
            <><span className="font-mono">↓</span> Importar</>
          )}
        </button>
      </div>

      {/* Expandir detalhes */}
      {item.link_sistema_origem && (
        <button
          onClick={() => setExpanded(v => !v)}
          className="text-[10px] font-mono text-gray-600 hover:text-red-400 transition-colors flex items-center gap-1"
        >
          {expanded ? '▼' : '▶'} Ver mais detalhes
        </button>
      )}

      {expanded && (
        <div className="pt-2 border-t border-slate-700/40 space-y-1">
          {item.link_sistema_origem && (
            <p className="text-[10px] font-mono text-gray-500">
              Link:{' '}
              <span className="text-red-400 break-all">{item.link_sistema_origem}</span>
            </p>
          )}
          {item.informacao_complementar && (
            <p className="text-[10px] text-gray-500 font-body leading-relaxed">
              {item.informacao_complementar}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function PncpSearch() {
  const navigate       = useNavigate()
  const { toast }      = useToast()

  const [query, setQuery] = useState({
    texto: '', cnpj: '', modalidade: '', dataInicio: '', dataFim: '', pagina: 1
  })
  const [results,   setResults]   = useState([])
  const [total,     setTotal]     = useState(0)
  const [loading,   setLoading]   = useState(false)
  const [importing, setImporting] = useState(null)
  const [searched,  setSearched]  = useState(false)

  const handleSearch = async (e, page = 1) => {
    if (e) e.preventDefault()
    setLoading(true)
    setSearched(true)
    try {
      const res = await pncpApi.search({ ...query, pagina: page })
      const data = res.data
      setResults(data.items || data.data || data || [])
      setTotal(data.total || data.count || 0)
      setQuery(q => ({ ...q, pagina: page }))
    } catch (err) {
      toast({ type: 'error', title: 'Erro na busca', message: err.response?.data?.detail || 'Não foi possível conectar ao PNCP.' })
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const handleImport = async (item) => {
    const idPncp = item.id_pncp || item.numero_controle
    setImporting(idPncp)
    try {
      const res = await pncpApi.importEdital(idPncp)
      const editalId = res.data?.edital_id || res.data?.id
      toast({
        type: 'success',
        title: 'Importação iniciada',
        message: `Edital ${idPncp} adicionado à fila. Acompanhe em Jobs.`,
        duration: 6000,
      })
      if (editalId) {
        setTimeout(() => navigate(`/jobs`), 1500)
      }
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || `Falha ao importar ${idPncp}.` })
    } finally {
      setImporting(null)
    }
  }

  const setField = (field) => (e) => setQuery(q => ({ ...q, [field]: e.target.value }))

  return (
    <div className="p-6 space-y-6 min-h-screen">

      {/* Header */}
      <div>
        <h1 className="font-display font-black text-2xl text-white">Busca PNCP</h1>
        <p className="text-sm text-gray-500 font-mono mt-1">
          Pesquise e importe editais diretamente do Portal Nacional de Contratações Públicas
        </p>
      </div>

      {/* Formulário */}
      <form onSubmit={handleSearch} className="card space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Texto */}
          <div className="sm:col-span-2 lg:col-span-2">
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wider mb-1.5">
              Objeto / Descrição
            </label>
            <input
              type="text"
              placeholder="Ex: Switch gerenciável, roteador, firewall, notebook…"
              value={query.texto}
              onChange={setField('texto')}
              className="input text-sm py-2"
            />
          </div>

          {/* CNPJ */}
          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wider mb-1.5">
              CNPJ do Órgão
            </label>
            <input
              type="text"
              placeholder="00.000.000/0001-00"
              value={query.cnpj}
              onChange={setField('cnpj')}
              className="input text-sm py-2"
            />
          </div>

          {/* Modalidade */}
          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wider mb-1.5">
              Modalidade
            </label>
            <select
              value={query.modalidade}
              onChange={setField('modalidade')}
              className="input text-sm py-2 bg-ink-50"
            >
              {MODALIDADES.map(m => (
                <option key={m} value={m} className="bg-ink-100">{m || 'Todas as modalidades'}</option>
              ))}
            </select>
          </div>

          {/* Datas */}
          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wider mb-1.5">
              Publicação — De
            </label>
            <input
              type="date"
              value={query.dataInicio}
              onChange={setField('dataInicio')}
              className="input text-sm py-2"
            />
          </div>

          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wider mb-1.5">
              Publicação — Até
            </label>
            <input
              type="date"
              value={query.dataFim}
              onChange={setField('dataFim')}
              className="input text-sm py-2"
            />
          </div>
        </div>

        <div className="flex items-center justify-between pt-1">
          <p className="text-xs text-gray-600 font-mono">
            Pelo menos um campo deve ser preenchido
          </p>
          <button
            type="submit"
            disabled={loading || (!query.texto && !query.cnpj && !query.modalidade && !query.dataInicio)}
            className="btn-primary flex items-center gap-2 disabled:opacity-40"
          >
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Buscando…
              </>
            ) : (
              <><span className="font-mono text-base">⌕</span> Buscar no PNCP</>
            )}
          </button>
        </div>
      </form>

      {/* Resultados */}
      {!loading && searched && (
        <>
          {results.length > 0 ? (
            <>
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-400 font-mono">
                  {total > 0 ? `${total.toLocaleString('pt-BR')} resultado${total !== 1 ? 's' : ''} encontrado${total !== 1 ? 's' : ''}` : `${results.length} resultado${results.length !== 1 ? 's' : ''}`}
                  {importing && <span className="text-red-400 ml-2">· importando…</span>}
                </p>
              </div>

              <div className="space-y-3">
                {results.map((item, i) => (
                  <ResultCard
                    key={item.id_pncp || item.numero_controle || i}
                    item={item}
                    onImport={handleImport}
                    importing={importing}
                  />
                ))}
              </div>
            </>
          ) : (
            <div className="card text-center py-16">
              <div className="text-4xl mb-3">🔍</div>
              <p className="text-white font-display font-bold mb-1">Nenhum resultado encontrado</p>
              <p className="text-sm text-gray-500 font-body">
                Tente ampliar os critérios de busca ou verificar os filtros.
              </p>
            </div>
          )}
        </>
      )}

      {/* Estado inicial */}
      {!searched && !loading && (
        <div className="card text-center py-20 border-dashed">
          <div className="text-5xl mb-4">🏛</div>
          <p className="font-display font-bold text-white text-lg mb-1">Portal Nacional de Contratações</p>
          <p className="text-sm text-gray-500 max-w-md mx-auto leading-relaxed">
            Preencha o formulário acima para buscar editais no PNCP e importá-los diretamente para o seu ambiente.
          </p>
        </div>
      )}
    </div>
  )
}
