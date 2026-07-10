/**
 * components/AnalysisItemCard.jsx
 * ────────────────────────────────
 * Cartão de item de edital extraído via JSON (schema v7.3).
 * Cabeçalho: o que dá para julgar relevância/valor batendo o olho.
 * Detalhe (ao expandir): tudo que justifica a decisão de participar
 * (conformidade, direcionamento de marca, narrativa de risco).
 */

import { useState } from 'react'

function Money({ value }) {
  if (value == null || value === '') return <span className="text-gray-600 font-mono text-xs">—</span>
  const num = Number(String(value).replace(',', '.'))
  if (Number.isNaN(num)) {
    return <span className="text-gray-400 font-mono text-xs">{value}</span>
  }
  return (
    <span className="text-white font-mono text-xs">
      {num.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
    </span>
  )
}

function caracteristicasBiToString(bi) {
  if (!bi || typeof bi !== 'object') return null
  const values = Object.values(bi).filter((v) => v && v !== 'N/C')
  if (!values.length) return null
  return values.join(' · ')
}

export default function AnalysisItemCard({ item }) {
  const [expanded, setExpanded] = useState(false)
  const direcionamento = item.direcionamento_marca || item.raw_payload?.direcionamento_marca
  const hasRisco = item.has_risco
  const hasMarca = item.has_direcionamento_marca ?? direcionamento?.existe
  const bi = item.caracteristicas_bi || item.raw_payload?.caracteristicas_bi
  const biSummary = caracteristicasBiToString(bi)
  const descricaoCompleta = item.description || item.raw_payload?.descricao_original || ''
  const descricaoResumida =
    descricaoCompleta.length > 100 ? `${descricaoCompleta.slice(0, 100)}…` : descricaoCompleta

  return (
    <div className="card p-0 overflow-hidden border-slate-border/40">
      {/* Cabeçalho — sempre visível */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left px-4 py-3 flex items-start gap-3 hover:bg-slate-hover/20 transition-colors"
      >
        <div className="flex flex-col items-center gap-1 shrink-0 w-10">
          <span className="text-[10px] font-mono text-gray-500">#{item.item_number ?? '—'}</span>
          {(hasRisco || hasMarca) && (
            <span
              className={`w-2 h-2 rounded-full ${hasRisco ? 'bg-red-500' : 'bg-amber'}`}
              title={hasRisco ? 'Risco associado identificado' : 'Direcionamento de marca/modelo'}
            />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {item.categoria && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono
                               bg-azure/10 border border-azure/20 text-azure-glow whitespace-nowrap">
                {item.categoria}
              </span>
            )}
            {item.uf && (
              <span className="text-[10px] font-mono text-gray-500">{item.uf}</span>
            )}
          </div>
          <p className="text-sm text-gray-200 font-body leading-relaxed mt-1">
            {descricaoResumida || '—'}
          </p>
          {biSummary && !expanded && (
            <p className="text-[10px] text-gray-600 font-mono mt-1">{biSummary}</p>
          )}
        </div>

        <div className="flex flex-col items-end gap-1 shrink-0 text-right">
          <p className="text-xs text-white font-medium">
            {item.quantity ?? '—'} {item.unit || ''}
          </p>
          <Money value={item.unit_value ?? item.raw_payload?.preco_unitario} />
          <span className={`text-gray-500 font-mono text-xs transition-transform ${expanded ? 'rotate-180' : ''}`}>
            ▾
          </span>
        </div>
      </button>

      {/* Detalhe — só ao expandir */}
      {expanded && (
        <div className="border-t border-slate-border/30 px-4 py-4 space-y-3 bg-ink-50/40">
          <div>
            <p className="text-[10px] text-gray-500 font-mono uppercase tracking-wider mb-1">Descrição completa</p>
            <p className="text-sm text-gray-200 leading-relaxed">{descricaoCompleta || '—'}</p>
          </div>

          {item.raw_payload?.garantia && (
            <div>
              <p className="text-[10px] text-gray-500 font-mono uppercase tracking-wider mb-1">Garantia</p>
              <p className="text-xs text-gray-300">{item.raw_payload.garantia}</p>
            </div>
          )}

          {hasMarca && direcionamento && (
            <div className="rounded-lg bg-amber/5 border border-amber/20 px-3 py-2">
              <p className="text-[10px] text-amber font-mono uppercase tracking-wider mb-1">
                Direcionamento de marca/modelo
              </p>
              <p className="text-xs text-white font-medium">{direcionamento.marca_modelo}</p>
              {direcionamento.tipo && (
                <p className="text-[10px] text-gray-400 mt-0.5">{direcionamento.tipo}</p>
              )}
              {direcionamento.justificativa && (
                <p className="text-[10px] text-gray-500 mt-1 leading-relaxed">{direcionamento.justificativa}</p>
              )}
            </div>
          )}

          {item.raw_payload?.risco_associado && (
            <div className="rounded-lg bg-red-500/5 border border-red-500/20 px-3 py-2">
              <p className="text-[10px] text-red-400 font-mono uppercase tracking-wider mb-1">Risco associado</p>
              <p className="text-xs text-gray-300 leading-relaxed">{item.raw_payload.risco_associado}</p>
            </div>
          )}

          {bi && Object.keys(bi).length > 0 && (
            <div>
              <p className="text-[10px] text-gray-500 font-mono uppercase tracking-wider mb-1.5">
                Características técnicas
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {Object.entries(bi).map(([key, value]) => (
                  <div key={key} className="text-[10px] font-mono bg-ink-50 border border-slate-border/40 px-2 py-1.5 rounded">
                    <p className="text-gray-600 uppercase">{key.replace(/_/g, ' ')}</p>
                    <p className="text-gray-200 mt-0.5">{value ?? '—'}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex gap-4 text-[10px] font-mono text-gray-600">
            {item.raw_payload?.lote_grupo && item.raw_payload.lote_grupo !== 'N/C' && (
              <span>Lote/grupo: {item.raw_payload.lote_grupo}</span>
            )}
            {item.raw_payload?.exclusividade_me_epp_item && (
              <span>ME/EPP: {item.raw_payload.exclusividade_me_epp_item}</span>
            )}
            {item.raw_payload?.valor_total_item && (
              <span>Valor total do item: {item.raw_payload.valor_total_item}</span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
