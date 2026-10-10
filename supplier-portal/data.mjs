export function filtered(rows, search='', category='', brand='') {
  return rows.filter(r => String(r.product ?? '').toLocaleLowerCase('pt-BR').includes(search.toLocaleLowerCase('pt-BR')) && (!category || r.category === category) && (!brand || r.brand === brand));
}
export function totals(rows) {
  const sample = rows.reduce((sum,r) => sum + Number(r.value_sample ?? 0),0);
  return {items:rows.reduce((sum,r) => sum + Number(r.items ?? 0),0),sample,value:sample ? rows.reduce((sum,r) => sum + Number(r.value ?? 0),0) : null};
}
export function format(value, money=false) {
  return value === null || value === undefined ? 'Não disponível' : new Intl.NumberFormat('pt-BR',money ? {style:'currency',currency:'BRL'} : {maximumFractionDigits:2}).format(value);
}
