import { useState } from 'react'
import api from '../api/client'

export default function TechnicalMatch() {
  const [noticeId, setNoticeId] = useState('')
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [catalogId, setCatalogId] = useState('')
  const [sheet, setSheet] = useState('{"categoria":"switch","atributos":{}}')
  async function action(fn) {
    setBusy(true); setError('')
    try { await fn() } catch (e) { setError(e.response?.data?.detail || e.message) }
    finally { setBusy(false) }
  }
  async function load() { setData((await api.get(`/crm/notices/${encodeURIComponent(noticeId)}/matches`)).data) }
  return <div className="space-y-6 p-6">
    <h1 className="text-2xl font-bold">Comparação técnica por requisito</h1>
    <p>Cadastre os valores revisados do datasheet e compare os itens estruturados do edital.</p>
    <label className="block">ID do edital <input className="border rounded p-2 text-black" value={noticeId} onChange={e => setNoticeId(e.target.value)} /></label>
    <button disabled={busy || !noticeId} onClick={() => action(load)}>Carregar avaliações</button>{' · '}
    <button disabled={busy || !noticeId} onClick={() => action(async () => {
      setData((await api.post(`/crm/notices/${encodeURIComponent(noticeId)}/matches/run`, {mode:'rules'})).data)
    })}>Comparar por regras</button>
    {busy && <p role="status">Processando…</p>}
    {error && <p role="alert" className="text-red-600">{error}</p>}
    {(data?.items || []).map(item => <section key={item.notice_product.id} className="border rounded p-4 space-y-3">
      <h2 className="font-bold">{item.notice_product.description}</h2>
      {item.matches.map(match => <article key={match.id} className="border rounded p-3">
        <h3>{match.catalog_product?.name} — {match.technical_status || 'Avaliação legada'}</h3>
        {match.technical_result && <>
          <p>Seleção humana: {match.status}</p>
          <button disabled={busy} onClick={() => action(async () => { setData((await api.post(`/crm/matches/${match.id}/reevaluate`)).data) })}>Reavaliar com ficha atual</button>
          <p>Cobertura: {Math.round(match.technical_result.cobertura * 100)}%</p>
          <div className="overflow-x-auto"><table className="w-full text-left"><thead><tr>{['Requisito','Exigido','Produto','Decisão','Motivo / fontes'].map(t => <th key={t} className="p-2">{t}</th>)}</tr></thead>
          <tbody>{match.technical_result.detalhes.map((row, i) => <tr key={i}>
            <td className="p-2">{row.id} {row.atributo}</td><td className="p-2">{row.operador} {JSON.stringify(row.exigido)}</td>
            <td className="p-2">{JSON.stringify(row.encontrado)}</td><td className="p-2">{row.status}</td>
            <td className="p-2">{row.motivo}<pre className="whitespace-pre-wrap text-xs">{JSON.stringify(row.fontes, null, 2)}</pre></td>
          </tr>)}</tbody></table></div>
          <button disabled={busy || match.technical_status !== 'ATENDE' || match.status === 'confirmed'} onClick={() => action(async () => {
            await api.post(`/crm/matches/${match.id}/confirm`); await load()
          })}>Confirmar seleção</button>
        </>}
      </article>)}
    </section>)}
    <section className="border rounded p-4 space-y-3">
      <h2 className="font-bold">Ficha técnica revisada</h2>
      <p>Use atributos com valor e evidencias. Cada evidência informa documento_id, pagina e revisado. O documento deve estar anexado ao produto.</p>
      <label className="block">ID do produto <input className="border rounded p-2 text-black" value={catalogId} onChange={e => setCatalogId(e.target.value)} /></label>
      <textarea aria-label="Ficha técnica JSON" className="w-full border rounded p-2 font-mono text-black" rows={10} value={sheet} onChange={e => setSheet(e.target.value)} />
      <button disabled={busy || !catalogId} onClick={() => action(async () => {
        await api.put(`/crm/catalog-products/${encodeURIComponent(catalogId)}/technical-sheet`, JSON.parse(sheet))
      })}>Salvar ficha técnica</button>
    </section>
  </div>
}
