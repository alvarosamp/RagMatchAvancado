import {filtered,totals,format} from './data.mjs';
const byId=id=>document.getElementById(id);
const token=new URLSearchParams(location.hash.slice(1)).get('access');
let data=null, busy=false;
const el=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;};
function render() {
  if(!data)return;
  const rows=filtered(data.rows,byId('search').value,byId('category').value,byId('brand').value);
  const stats=totals(rows);
  byId('metrics').replaceChildren(...[['Itens demandados',format(stats.items)],['Produtos no recorte',format(rows.length)],['Referência observada',format(stats.value,true)],['Itens com valor conhecido',format(stats.sample)]].map(([label,value])=>{const card=el('div',undefined,'metric');card.append(el('p',label),el('strong',value));return card;}));
  const measure=byId('measure').value;
  const ranked=[...rows].sort((a,b)=>Number(b[measure]??0)-Number(a[measure]??0)).slice(0,12);
  const max=Math.max(1,...ranked.map(r=>Number(r[measure]??0)));
  byId('chart').replaceChildren(...ranked.map(r=>{const line=el('div',undefined,'chart-row');const meter=el('progress');meter.max=max;meter.value=Number(r[measure]??0);meter.setAttribute('aria-label',String(r.product));line.append(el('span',String(r.product)),meter,el('strong',format(r[measure],measure==='value')));return line;}));
  byId('rows').replaceChildren(...rows.slice(0,500).map(r=>{const tr=el('tr');for(const text of [String(r.product)+(r.brand?' · '+r.brand:''),format(r.items),format(r.quantity)+(r.unit?' '+r.unit:''),format(r.quantity_sample),format(r.value,true),format(r.value_sample)])tr.append(el('td',text));return tr;}));
  byId('empty').hidden=rows.length>0;
  byId('row-limit').textContent=rows.length>500?`Exibindo 500 de ${rows.length} produtos. Refine os filtros para consultar os demais.`:'';
  const growth=Number(byId('growth').value);
  byId('growth-label').textContent=growth+'%';
  byId('scenario').textContent='Referência no cenário: '+format(stats.value===null?null:stats.value*(1+growth/100),true);
}
async function load() {
  if(busy)return;
  if(!token){byId('status').textContent='Abra o link gerado pela empresa no portal para consultar os dados autorizados.';byId('refresh').disabled=true;return;}
  busy=true;byId('refresh').disabled=true;
  byId('status').textContent='Consultando os dados compartilhados…';
  try {
    const response=await fetch('/api/supplier-view',{headers:{Authorization:'Bearer '+token},cache:'no-store',credentials:'omit'});
    if(!response.ok)throw new Error(response.status===401?'Este link expirou, foi revogado ou é inválido. Solicite um novo link à empresa.':'Não foi possível atualizar os dados. Tente novamente ou fale com a empresa.');
    const payload=await response.json();
    if(!Array.isArray(payload.rows))throw new Error('Resposta indisponível. Tente novamente.');
    data=payload;
    byId('intro').textContent=`${data.company} · Apresentação para ${data.supplier}`;
    byId('status').textContent='Dados reais compartilhados pela empresa. Atualização automática a cada 5 minutos.';
    const date=v=>v?new Date(v).toLocaleString('pt-BR'):'Não disponível';
    byId('freshness').textContent=`Última sincronização do portal: ${date(data.last_sync)} · Consultado: ${date(data.generated_at)} · Link válido até: ${date(data.expires_at)}`;
    byId('scope').textContent=`Origem: ${data.scope.source} · Período: ${data.scope.date_from || 'Início da base'} a ${data.scope.date_to || 'Data atual'}`;
    for(const key of ['category','brand']){const select=byId(key), selected=select.value;select.replaceChildren(el('option','Todas'));select.firstChild.value='';for(const value of [...new Set(data.rows.map(r=>r[key]).filter(Boolean))].sort()){const option=el('option',value);option.value=value;select.append(option);}select.value=selected;}
    byId('dashboard').hidden=false;render();
  }catch(error){data=null;byId('dashboard').hidden=true;byId('freshness').textContent='';byId('status').textContent=error.message;}
  finally{busy=false;byId('refresh').disabled=false;}
}
for(const id of ['search','category','brand','measure','growth'])byId(id).addEventListener('input',render);
byId('refresh').addEventListener('click',load);byId('print').addEventListener('click',()=>window.print());
load();setInterval(()=>{if(!document.hidden)load();},300000);
