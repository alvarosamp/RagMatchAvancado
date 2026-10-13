"""Exercise the preview through the real frontend/API; persists only test fixtures."""
import json,os
from pathlib import Path
import requests

base='http://localhost:13089/api'
s=requests.Session()
def call(method,path,**kwargs):
 r=s.request(method,base+path,timeout=120,**kwargs)
 if not r.ok:raise RuntimeError(f'{path} {r.status_code}: {r.text[:250]}')
 return r
call('POST','/auth/login',json={'email':'alpha-admin@example.com','password':'Quality-Test-Only-2026!'})
out=Path('output/technical-preview');out.mkdir(parents=True,exist_ok=True)
files={kind:call('GET','/technical-extraction/example/'+kind).content for kind in ['edital','produto','insuficiente']}
for kind,data in files.items(): (out/('EXEMPLO-SIMULADO-'+kind+'.pdf')).write_bytes(data)
def compare(kind='produto',review=None,session=None,extra=None):
 return (session or s).post(base+'/technical-extraction/preview',files={'edital':('simulado-edital.pdf',files['edital'],'application/pdf'),'datasheet':('simulado-datasheet.pdf',files[kind],'application/pdf')},data={'revisao':json.dumps(review or {}),**(extra or {})},timeout=120)
r=compare();r.raise_for_status();draft=r.json();assert draft['comparacao']['status']=='VERIFICAR'
review={'requisitos':[r['id'] for r in draft['requisitos']['registros']], 'atributos':[r['id'] for r in draft['produto']['registros']],
        'descartes':{p['id']:'Cabeçalho do exemplo simulado' for d in ['requisitos','produto'] for p in draft[d]['pendencias']}}
r=compare(review=review);r.raise_for_status();approved=r.json();assert approved['comparacao']['status']=='ATENDE'
assert approved['comparacao']['preliminar'] is True
r=compare('insuficiente');r.raise_for_status();insufficient=r.json();review['atributos']=[r['id'] for r in insufficient['produto']['registros']];review['descartes'].update({p['id']:'Cabeçalho do exemplo simulado' for p in insufficient['produto']['pendencias']})
r=compare('insuficiente',review);r.raise_for_status();assert r.json()['comparacao']['status']=='NAO_ATENDE'
catalog=call('GET','/crm/query/catalog_products').json()['data']
if catalog:
 target=next((c for c in catalog if c['sku']=='TLSG3428MP'),catalog[0])
 r=compare(review=approved['comparacao']['revisao'],extra={'catalog_id':target['id'],'hardware':'V6'})
 r.raise_for_status();assert r.json()['comparacao']['status']=='VERIFICAR'
 assert any(p['id']=='modelo-nao-identificado' for p in r.json()['comparacao']['pendencias_extracao'])
assert compare(session=requests.Session()).status_code==401
viewer=requests.Session();r=viewer.post(base+'/auth/login',json={'email':'alpha-viewer@example.com','password':'Quality-Test-Only-2026!'},timeout=30);r.raise_for_status();assert compare(session=viewer).status_code==403
beta=requests.Session();r=beta.post(base+'/auth/login',json={'email':'beta-admin@example.com','password':'Quality-Test-Only-2026!'},timeout=30);r.raise_for_status()
items=call('GET','/crm/query/notice_products').json()['data'];assert compare(session=beta,extra={'item_id':items[0]['id']}).status_code==404
assert s.post(base+'/technical-extraction/preview',files={'datasheet':('bad.pdf',b'%PDF-1.4 broken','application/pdf'),'edital':('edital.pdf',files['edital'],'application/pdf')},timeout=30).status_code==422
(out/'comparacao-exemplo-revisado.json').write_text(json.dumps(approved,ensure_ascii=False,indent=2))
result={'unreviewed':'VERIFICAR','reviewed':'ATENDE','insufficient_power':'NAO_ATENDE','anonymous':401,'viewer':403,'cross_tenant':404,'corrupt_pdf':422}
(out/'resultado-smoke.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if os.getenv('IMPORT_PREVIEW_LPU')=='1':
 lpu=next(Path.home().joinpath('Downloads').glob('LPU - REV-09_10_26*.xlsx'))
 with lpu.open('rb') as f: report=call('POST','/crm/imports/lpu',files={'file':(lpu.name,f,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},data={'drive_url':'https://drive.google.com/file/d/preview-local-only'}).json()
 print('LPU na prévia isolada:',report['summary'])
