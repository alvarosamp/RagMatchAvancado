import { useEffect, useState } from 'react'
import api from '../api/client'

const labels = {categoria:'Categoria',portas_rj45:'Portas RJ45',portas_sfp:'Portas SFP',portas_sfp_plus:'Portas SFP+',poe_budget_w:'Orçamento de PoE',capacidade_comutacao_gbps:'Capacidade de comutação',alcance_m:'Alcance',gerenciavel:'Gerenciamento',poe:'Suporte a PoE',tipo_fibra:'Tipo de fibra',conector:'Conector',comprimento_onda_tx_nm:'Comprimento de onda Tx',comprimento_onda_rx_nm:'Comprimento de onda Rx'}
const value = row => `${typeof row.valor === 'object' ? JSON.stringify(row.valor) : row.valor}${row.unidade ? ' ' + row.unidade : ''}`
const displayValue = input => {
  if (input == null) return 'Não informado'
  if (typeof input === 'object' && 'valor' in input) return value(input)
  if (typeof input === 'boolean') return input ? 'Sim' : 'Não'
  return typeof input === 'object' ? JSON.stringify(input) : String(input)
}
const panel = 'rounded-2xl border border-slate-200 bg-white p-5 shadow-sm'
const button = 'rounded-lg bg-blue-700 px-4 py-2 text-white disabled:opacity-40'

export default function TechnicalExtraction() {
  const [catalog, setCatalog] = useState([]), [catalogId, setCatalogId] = useState(''), [hardware, setHardware] = useState('')
  const [notices, setNotices] = useState([]), [items, setItems] = useState([])
  const [noticeId, setNoticeId] = useState(''), [itemId, setItemId] = useState('')
  const [edital, setEdital] = useState(null), [sheet, setSheet] = useState(null)
  const [ranges, setRanges] = useState({edital_inicio:1, edital_fim:'', datasheet_inicio:1, datasheet_fim:''})
  const [data, setData] = useState(null), [review, setReview] = useState({requisitos:[], atributos:[], escolhas:{}, descartes:{}})
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [changed, setChanged] = useState(false)
  useEffect(() => { api.get('/crm/query/catalog_products').then(r=>setCatalog(r.data.data)).catch(()=>{}); api.get('/crm/query/notices').then(r => setNotices(r.data.data)).catch(() => setError('Não foi possível carregar a triagem.')) }, [])
  useEffect(() => { setItemId(''); setItems([]); if (noticeId) api.get('/crm/query/notice_products').then(r => setItems(r.data.data.filter(i => i.notice_id === noticeId))).catch(() => setError('Não foi possível carregar os itens.')) }, [noticeId])
  async function example(kind='produto') {
    setBusy(true); setError('')
    try {
      const [a,b]=await Promise.all([api.get('/technical-extraction/example/edital',{responseType:'blob'}),api.get('/technical-extraction/example/'+kind,{responseType:'blob'})])
      setEdital(new File([a.data],'EXEMPLO-SIMULADO-edital.pdf',{type:'application/pdf'}));setSheet(new File([b.data],'EXEMPLO-SIMULADO-produto.pdf',{type:'application/pdf'}));setNoticeId('');setCatalogId('');setHardware('');setRanges({edital_inicio:1,edital_fim:'',datasheet_inicio:1,datasheet_fim:''});reset()
    } catch(e) { setError(e.message) } finally {setBusy(false)}
  }
  function reset() { setData(null); setReview({requisitos:[],atributos:[],escolhas:{},descartes:{}}); setChanged(false) }
  function file(setter, file) { setter(file); reset() }
  async function analyze() {
    setBusy(true); setError('')
    const form = new FormData()
    form.append('datasheet', sheet)
    if (edital) form.append('edital', edital)
    if (itemId) form.append('item_id', itemId)
    if (catalogId) form.append('catalog_id',catalogId)
    form.append('categoria',catalog.find(c=>c.id===catalogId)?.category || items.find(i=>i.id===itemId)?.category || 'switch')
    form.append('hardware',hardware)
    Object.entries(ranges).forEach(([key,v]) => { if (v !== '') form.append(key,v) })
    form.append('revisao',JSON.stringify(review))
    try { setData((await api.post('/technical-extraction/preview',form,{headers:{'Content-Type':'multipart/form-data'}})).data); setChanged(false) }
    catch(e) { const detail=e.response?.data?.detail; setError(typeof detail==='string' ? detail : Array.isArray(detail) ? detail.map(d=>`${d.loc?.at(-1)}: ${d.msg}`).join('; ') : e.message) }
    finally { setBusy(false) }
  }
  function toggle(group,id) { setReview(r => ({...r,[group]:r[group].includes(id) ? r[group].filter(v=>v!==id) : [...r[group],id]})); setChanged(true) }
  function changeReview(key,id,v) { setReview(r=>({...r,[key]:{...r[key],[id]:v}})); setChanged(true) }
  function download() {
    const href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}))
    const a=document.createElement('a'); a.href=href;a.download='previa-comparacao-documental.json';a.click();setTimeout(()=>URL.revokeObjectURL(href),1000)
  }
  function records(title, doc, group) {
    return <section className={panel}><h2 className="mb-3 text-xl font-bold">{title}</h2>
      <p className="mb-3 text-sm text-slate-500">{doc.fonte.arquivo} · {doc.registros.length} valores explícitos encontrados</p>
      {doc.registros.length === 0 && <p>Nenhum atributo explícito encontrado. Confira o texto e as pendências abaixo.</p>}
      <div className="space-y-3">{doc.registros.map(row=><div key={row.id} className="rounded-lg border p-3">
        <label className="flex gap-2"><input type="checkbox" checked={review[group].includes(row.id)} onChange={()=>toggle(group,row.id)} /><span><strong>{labels[row.campo_normalizado] || row.campo_normalizado}</strong>: {group==='requisitos' && row.operador} {value(row)}</span></label>
        <p className="mt-1 text-xs text-slate-500">Página {row.evidencias[0].pagina ?? 'não informada'} · {row.texto_original}</p>
      </div>)}</div>
      <details className="mt-4"><summary className="cursor-pointer font-medium">Conferir texto extraído e origem</summary>{doc.fonte.paginas.map((p,i)=><div key={i} className="mt-3"><h3>Página {p.pagina ?? 'não informada'}</h3><pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-3 text-xs">{p.texto}</pre></div>)}<p className="break-all text-xs">SHA-256: {doc.fonte.hash}</p></details>
    </section>
  }
  return <div className="mx-auto max-w-7xl space-y-5 p-5 text-slate-800">
    <header><span className="text-xs font-semibold uppercase tracking-widest text-blue-700">Prévia local • revisão documental</span><h1 className="mt-2 text-3xl font-bold">Do edital à comparação técnica</h1><p className="mt-2 text-slate-600">Escolha um item, confira os valores extraídos e revise cada evidência antes de comparar. Esta prévia não modifica o CRM.</p></header>
    <section className={panel}><h2 className="mb-3 text-xl font-bold">1. Fontes da comparação</h2><div className="grid gap-4 md:grid-cols-2">
      <label>Edital da triagem<select aria-label="Edital da triagem" className="mt-1 w-full rounded border p-2" value={noticeId} onChange={e=>{setNoticeId(e.target.value);reset()}}><option value="">Usar somente o PDF enviado</option>{notices.map(n=><option value={n.id} key={n.id}>{n.number} — {n.title}</option>)}</select></label>
      <label>Item<select aria-label="Item da triagem" className="mt-1 w-full rounded border p-2" value={itemId} onChange={e=>{setItemId(e.target.value);reset()}}><option value="">Selecionar item</option>{items.map(i=><option key={i.id} value={i.id}>{i.item_number} — {i.description}</option>)}</select></label>
      <label>Produto da LPU<select aria-label="Produto da LPU" className="mt-1 w-full rounded border p-2" value={catalogId} onChange={e=>{setCatalogId(e.target.value);reset()}}><option value="">Comparar somente o datasheet</option>{catalog.map(c=><option key={c.id} value={c.id}>{c.manufacturer_part_number && !['-','N/C'].includes(c.manufacturer_part_number) ? c.manufacturer_part_number : c.sku} — {c.name}</option>)}</select></label>
      <label>Revisão física do hardware<input aria-label="Revisão do hardware" className="mt-1 w-full rounded border p-2" value={hardware} placeholder="Ex.: V6 (confira no produto)" onChange={e=>{setHardware(e.target.value);reset()}} /></label>
      <label>PDF do item ou termo de referência<input aria-label="PDF do edital" type="file" accept="application/pdf" className="mt-1 block w-full" onChange={e=>file(setEdital,e.target.files[0])} /><small className="text-slate-500">Sem PDF, a descrição da triagem fica com origem de página pendente.</small></label>
      <label>Datasheet do produto<input aria-label="PDF do datasheet" type="file" accept="application/pdf" className="mt-1 block w-full" onChange={e=>file(setSheet,e.target.files[0])} /><small className="text-slate-500">Use páginas do modelo e revisão de hardware corretos.</small></label>
      {['edital','datasheet'].map(kind=><fieldset key={kind} className="flex items-center gap-2"><legend className="text-sm">Páginas do {kind==='edital'?'item no edital':'datasheet'}</legend>{['inicio','fim'].map(part=><label key={part} className="text-sm">{part==='inicio'?'De':'Até'} <input aria-label={`${kind} ${part}`} type="number" min="1" className="w-20 rounded border p-2" value={ranges[`${kind}_${part}`]} onChange={e=>{setRanges(r=>({...r,[`${kind}_${part}`]:e.target.value}));reset()}} /></label>)}</fieldset>)}
    </div><div className="mt-4 flex flex-wrap gap-3"><button className="rounded-lg border px-4 py-2" disabled={busy} onClick={()=>example()}>Carregar exemplo simulado</button><button className="rounded-lg border px-4 py-2" disabled={busy} onClick={()=>example('insuficiente')}>Exemplo com PoE insuficiente</button><button className={button} disabled={busy || !sheet || (!edital&&!itemId)} onClick={analyze}>{busy?'Lendo documentos…':data?'Recalcular com a revisão':'Extrair e comparar'}</button>{data&&<button className="rounded-lg border px-4 py-2" disabled={changed} onClick={download}>Baixar análise completa</button>}</div>
    <p className="mt-3 text-sm">Fontes: {edital?.name || 'Descrição do item selecionado'} · {sheet?.name || 'Nenhum datasheet selecionado'}</p>{itemId && <p className="mt-2 rounded bg-slate-50 p-3 text-sm">Item da triagem: {items.find(i=>i.id===itemId)?.description}</p>}
    <p className="mt-3 text-xs text-slate-500">Extração explícita de portas, PoE, capacidade, alcance, gerenciamento, fibra e conectores. Alternativas, escopos, protocolos e trechos não reconhecidos exigem revisão. PDFs sem texto são sinalizados para OCR.</p></section>
    {error&&<p role="alert" className="rounded-lg bg-red-50 p-4 text-red-800">{error}</p>}
    {data&&<>
      {changed&&<p className="rounded-lg bg-amber-50 p-3">Revisão alterada. Recalcule para atualizar a decisão e o arquivo de análise.</p>}
      <div className="grid gap-5 lg:grid-cols-2">{records('2. Requisitos do edital',data.requisitos,'requisitos')}{records('3. Evidências do produto',data.produto,'atributos')}</div>
      <section className={panel}><h2 className="mb-3 text-xl font-bold">4. Trechos que precisam de análise</h2><p className="mb-3 text-sm">Cada trecho abaixo permanece pendente. Caso seja um título, rodapé ou informação fora da comparação, justifique sua exclusão. Requisitos reais não devem ser descartados para aprovar o produto.</p>
      {[...data.requisitos.pendencias,...data.produto.pendencias].map((p,i)=><div key={`${p.id}-${i}`} className="my-3 rounded-lg border border-amber-200 p-3"><p className="font-medium">Página {p.pagina ?? 'não informada'}: {p.trecho || 'Sem texto extraível'}</p><p className="text-sm text-slate-500">{p.motivo}</p>{!p.bloqueante && <input aria-label={`Justificativa ${i+1}`} placeholder="Justificativa para excluir este trecho (opcional)" className="mt-2 w-full rounded border p-2" value={review.descartes[p.id]||''} onChange={e=>changeReview('descartes',p.id,e.target.value)} />}</div>)}
      {data.comparacao.conflitos_datasheet.map(c=><div className="my-3 rounded border border-amber-300 p-3" key={c.atributo}><strong>Valores conflitantes: {c.atributo}</strong><select aria-label={`Resolver ${c.atributo}`} className="mt-2 block w-full border p-2" value={review.escolhas[c.atributo]||''} onChange={e=>changeReview('escolhas',c.atributo,e.target.value)}><option value="">Conferir modelo, página e revisão antes de escolher</option>{c.candidatos.map(r=><option key={r.id} value={r.id}>{value(r)} — página {r.evidencias[0].pagina}: {r.texto_original}</option>)}</select></div>)}
      </section>
      <section className={panel}><h2 className="text-xl font-bold">5. Matriz de comparação</h2><p className="my-3 text-lg font-semibold">{changed?'Recalcular revisão':data.comparacao.status} <span className="text-sm font-normal text-slate-500">· resultado preliminar</span></p><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr>{['Campo','Exigido','Encontrado','Resultado','Motivo'].map(t=><th className="p-2" key={t}>{t}</th>)}</tr></thead><tbody>{data.comparacao.detalhes.map((r,i)=><tr key={i} className="border-t"><td className="p-2">{labels[r.atributo] || r.atributo}</td><td className="p-2">{r.operador} {displayValue(r.exigido)}</td><td className="p-2">{displayValue(r.encontrado)}</td><td className="p-2">{r.status}</td><td className="p-2">{r.motivo}</td></tr>)}</tbody></table></div><ul className="mt-4 text-sm text-amber-800">{data.comparacao.pendencias_extracao.map((p,i)=><li key={i}>{p.motivo}</li>)}</ul><p className="mt-3 text-xs text-slate-500">{data.comparacao.aviso}</p></section>
    </>}
  </div>
}
