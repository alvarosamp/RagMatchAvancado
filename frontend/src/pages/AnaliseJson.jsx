/**
 * pages/AnaliseJson.jsx
 * ───────────────────────
 * Exibe um AnalysisDocument (source_kind="edital") ingerido via JSON
 * estruturado (schema v7.3): itens elegíveis + riscos + documentação +
 * declarações do edital.
 */

import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { analysisApi } from '../api/client'
import { useToast } from '../contexts/ToastContext'
import AnalysisItemCard from '../components/AnalysisItemCard'

const TABS = [
  { key: 'itens', label: 'Itens' },
  { key: 'riscos', label: 'Riscos' },
  { key: 'documentacao', label: 'Documentação' },
  { key: 'declaracoes', label: 'Declarações' },
]

export default function AnaliseJson() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { toast } = useToast()

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [tab, setTab] = useState('itens')

  useEffect(() => {
    setLoading(true)
    setNotFound(false)
    analysisApi.get(id)
      .then((r) => setData(r.data))
      .catch((err) => {
        if (err.response?.status === 404) setNotFound(true)
        else toast({ type: 'error', message: err.response?.data?.detail || 'Erro ao carregar análise.' })
      })
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="p-6 space-y-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-14 rounded-xl bg-slate-card border border-slate-border animate-pulse" />
        ))}
      </div>
    )
  }

  if (notFound || !data) {
    return (
      <div className="p-6">
        <div className="card border border-amber/20 bg-amber/5 text-center py-14">
          <div className="text-4xl mb-3">🔍</div>
          <p className="font-display font-bold text-white text-lg mb-1">Análise não encontrada</p>
          <p className="text-sm text-gray-400">Este edital ainda não tem um JSON importado.</p>
        </div>
      </div>
    )
  }

  const edital = data.edital || {}
  const riscos = data.riscos || {}
  const documentacao = data.documentacao || []
  const declaracoes = data.declaracoes || []
  const items = data.items || []

  return (
    <div className="p-6 space-y-6 min-h-screen">
      <div>
        <button
          onClick={() => navigate(-1)}
          className="text-xs font-mono text-gray-500 hover:text-azure-glow transition-colors mb-2 flex items-center gap-1"
        >
          ← Voltar
        </button>
        <h1 className="font-display font-black text-2xl text-white">{edital.orgao || data.source_name || `Edital #${id}`}</h1>
        <p className="text-sm text-gray-500 font-mono mt-1">
          {edital.numero_pregao} {edital.uf ? `· ${edital.uf}` : ''} {edital.cidade ? `· ${edital.cidade}` : ''}
        </p>
      </div>

      {/* Metadados do edital */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Data da disputa', value: edital.data_disputa || '—' },
          { label: 'Critério', value: edital.criterio || '—' },
          { label: 'ME/EPP', value: edital.exclusividade_me_epp || '—' },
          { label: 'Valor total', value: edital.valor_total_edital || '—' },
        ].map(({ label, value }) => (
          <div key={label} className="card p-4">
            <p className="text-[10px] text-gray-500 font-mono uppercase tracking-wider mb-1">{label}</p>
            <p className="text-sm text-white font-body font-medium truncate" title={value}>{value}</p>
          </div>
        ))}
      </div>

      {/* Abas */}
      <div className="flex gap-1 flex-wrap border-b border-slate-border/40 pb-px">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-xs font-mono rounded-t-lg border-b-2 transition-all ${
              tab === t.key
                ? 'text-azure-glow border-azure'
                : 'text-gray-500 border-transparent hover:text-white'
            }`}
          >
            {t.label} {t.key === 'itens' ? `(${items.length})` : ''}
          </button>
        ))}
      </div>

      {tab === 'itens' && (
        <div className="space-y-2">
          {items.length === 0 ? (
            <p className="text-sm text-gray-500 font-body text-center py-10">Nenhum item elegível neste edital.</p>
          ) : (
            items.map((item) => <AnalysisItemCard key={item.id} item={item} />)
          )}
        </div>
      )}

      {tab === 'riscos' && (
        <div className="space-y-3">
          <div className="card p-4">
            <p className="text-[10px] text-gray-500 font-mono uppercase tracking-wider mb-1">Risco identificado</p>
            <p className="text-sm text-white">{riscos.risco_identificado || '—'}</p>
          </div>
          {['risco_operacional', 'risco_documental'].map((key) => {
            const r = riscos[key]
            if (!r) return null
            return (
              <div key={key} className="card p-4">
                <p className="text-[10px] text-gray-500 font-mono uppercase tracking-wider mb-1">
                  {key.replace('_', ' ')}
                </p>
                <p className="text-sm text-white">{r.existe ? 'Existe' : 'Não existe'}</p>
                {r.motivos?.length > 0 && (
                  <ul className="mt-2 list-disc list-inside text-xs text-gray-300 space-y-1">
                    {r.motivos.map((m, i) => <li key={i}>{m}</li>)}
                  </ul>
                )}
              </div>
            )
          })}
        </div>
      )}

      {tab === 'documentacao' && (
        <div className="card p-0 overflow-hidden">
          <table className="w-full">
            <thead className="bg-ink-100 border-b border-slate-border">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-mono text-gray-500 uppercase tracking-wider">Categoria</th>
                <th className="px-4 py-3 text-left text-xs font-mono text-gray-500 uppercase tracking-wider">Documento</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-border/20">
              {documentacao.length === 0 ? (
                <tr><td colSpan={2} className="px-4 py-10 text-center text-sm text-gray-500">Nenhum documento listado.</td></tr>
              ) : (
                documentacao.map((doc, i) => (
                  <tr key={i}>
                    <td className="px-4 py-2 text-xs text-gray-400 font-mono whitespace-nowrap">{doc.categoria}</td>
                    <td className="px-4 py-2 text-sm text-gray-200">{doc.documento}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'declaracoes' && (
        <div className="card p-4">
          {declaracoes.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-10">Nenhuma declaração listada.</p>
          ) : (
            <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {declaracoes.map((d, i) => (
                <li key={i} className="text-sm text-gray-200 flex items-center gap-2">
                  <span className="text-azure-glow">✓</span> {d.declaracao}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
