"""Create one clearly simulated example in the localhost preview only."""
import json
from pathlib import Path
import requests

BASE = 'http://localhost:13089/api'
api = requests.Session()
response = api.post(BASE+'/auth/login', json={'email':'alpha-admin@example.com','password':'Quality-Test-Only-2026!'}, timeout=15)
response.raise_for_status()


def request(method,path,**kwargs):
    response=api.request(method,BASE+path,timeout=30,**kwargs)
    response.raise_for_status()
    return response.json()


def ensure(table,column,value,values):
    found=request('GET',f'/crm/query/{table}',params={'filters':json.dumps([{'column':column,'op':'eq','value':value}])})['data']
    if found:return found[0]
    return request('POST',f'/crm/query/{table}/insert',json={'values':{column:value,**values}})['data'][0]


notice=ensure('notices','number','EXEMPLO-MATCH-MANUAL',{'title':'EXEMPLO SIMULADO – fluxo de match manual'})
item=ensure('notice_products','notice_id',notice['id'],{'item_number':'10','category':'switch','quantity':3,
    'description':'EXEMPLO SIMULADO: Switch com mínimo de 24 portas RJ45 e mínimo de 4 portas SFP.',
    'reference_price':1200,'unit_price':1000,'raw_payload':{'requisitos_atomicos':[
        {'id':'R1','campo_normalizado':'portas_rj45','operador':'>=','valor':24,'texto_original':'Mínimo 24 portas RJ45'},
        {'id':'R2','campo_normalizado':'portas_sfp','operador':'>=','valor':4,'texto_original':'Mínimo 4 portas SFP'}]}})
products=[]
for count in (8,24,48):
    products.append(ensure('catalog_products','sku',f'EXEMPLO-MANUAL-{count}',{'name':f'EXEMPLO SIMULADO {count} portas',
        'brand':'EXEMPLO SIMULADO','model':f'{count} portas','category':'switch',
        'description':'Produto fictício, criado exclusivamente para demonstrar os filtros.',
        'specification':json.dumps({'categoria':'switch','atributos':{'portas_rj45':{'valor':count},'portas_sfp':{'valor':4}}})}))
product=products[1]
documents=request('GET',f"/crm/catalog-products/{product['id']}/datasheets")
if documents:
    document=documents[0]
else:
    pdf=api.get(BASE+'/technical-extraction/example/produto',timeout=15)
    pdf.raise_for_status()
    document=request('POST',f"/crm/catalog-products/{product['id']}/datasheets",files={'file':('EXEMPLO-SIMULADO-24-PORTAS.pdf',pdf.content,'application/pdf')})
evidence={'documento_id':document['id'],'pagina':1,'revisado':True}
request('PUT',f"/crm/catalog-products/{product['id']}/technical-sheet",json={'categoria':'switch','atributos':{
    'portas_rj45':{'valor':24,'evidencias':[evidence]},'portas_sfp':{'valor':4,'evidencias':[evidence]}}})
exported=request('GET',f"/crm/notices/{notice['id']}/products/{item['id']}/match-json")
folder=Path('output/technical-preview');folder.mkdir(parents=True,exist_ok=True)
(folder/'item-match-manual-exemplo.json').write_text(json.dumps(exported,ensure_ascii=False,indent=2)+'\n')
result={'notice_id':notice['id'],'item_id':item['id'],'product_id':product['id'],
        'url':f"http://localhost:13089/crm/editais/{notice['id']}"}
(folder/'manual-match-demo.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
