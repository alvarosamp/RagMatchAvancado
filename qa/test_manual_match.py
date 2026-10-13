"""Manual item flow with real HTTP and isolated synthetic catalogue rows."""
import copy
import io
import json
from datetime import datetime
from reportlab.pdfgen import canvas
import pytest


@pytest.fixture
def scenario(clients, unique):
    api = clients('empty', 'admin')
    def create(table, values):
        response = api.post(f'/crm/query/{table}/insert', json={'values': values})
        assert response.status_code == 200, response.text
        return response.json()['data'][0]
    notice = create('notices', {'number': 'MANUAL-'+unique, 'title': 'EXEMPLO SIMULADO – match manual'})
    item = create('notice_products', {'notice_id': notice['id'], 'item_number': '10', 'description': 'EXEMPLO SIMULADO: switch gerenciável com mínimo de 24 portas RJ45.',
        'category': 'switch', 'quantity': 3, 'unit_price': 1000, 'minimum_unit_price': 900, 'reference_price': 1200,
        'raw_payload': {'preservar': 'original', 'requisitos_atomicos': [
            {'id': 'R1', 'campo_normalizado': 'portas_rj45', 'operador': '>=', 'valor': 24, 'texto_original': 'Mínimo 24 portas RJ45'},
            {'id': 'R2', 'campo_normalizado': 'gerenciavel', 'operador': '==', 'valor': True, 'texto_original': 'Switch gerenciável'}]}})
    products = []
    for ports, category in [(8, 'switch'), (24, 'switch'), (48, 'switch'), (24, 'access_point')]:
        products.append(create('catalog_products', {'sku':f'MANUAL-{unique}-{category}-{ports}', 'brand':'EXEMPLO SIMULADO',
            'model':str(ports), 'name':f'EXEMPLO SIMULADO {ports}', 'category':category,
            'specification':json.dumps({'categoria':category,'atributos':{'portas_rj45':{'valor':ports},'gerenciavel':{'valor':True}}})}))
    base=f"/crm/notices/{notice['id']}/products/{item['id']}/manual-match"
    response=api.get(base)
    assert response.status_code==200,response.text
    return {'api':api,'base':base,'notice':notice,'item':item,'products':products,'loaded':response.json()}


def draft(scenario, **changes):
    payload={'state':copy.deepcopy(scenario['loaded']['state']), 'base_revision':scenario['loaded']['base_revision']}
    payload.update(changes)
    return payload


def test_export_single_item_and_reimport(scenario):
    s=scenario
    exported=s['api'].get(f"/crm/notices/{s['notice']['id']}/products/{s['item']['id']}/match-json")
    assert exported.status_code==200
    payload=exported.json()
    assert payload['item']['id_interno']==s['item']['id']
    response=s['api'].post(s['base']+'/import',json={'json_text':json.dumps(payload),'filename':'item.json'})
    assert response.status_code==200,response.text
    assert len(response.json()['state']['requisitos'])==2
    assert response.json()['state']['fonte_json']['arquivo']=='item.json'


def test_category_and_progressive_filtering_without_ai(scenario):
    s=scenario;body=draft(s)
    body['state']['filtros']=['R1']
    result=s['api'].post(s['base']+'/preview',json=body)
    assert result.status_code==200,result.text
    data=result.json();own={p['id'] for p in s['products']}
    remaining=[c for c in data['candidatos'] if c['id'] in own and c['status_filtro']=='ATENDE']
    assert len(remaining)==2
    assert s['products'][3]['id'] not in {c['id'] for c in data['candidatos']}
    body['state']['requisitos'][0]['operador']='=='
    result=s['api'].post(s['base']+'/preview',json=body).json()
    remaining=[c for c in result['candidatos'] if c['id'] in own and c['status_filtro']=='ATENDE']
    assert [c['id'] for c in remaining]==[s['products'][1]['id']]


def test_filtering_is_not_documentary_approval(scenario):
    s=scenario;body=draft(s,catalog_product_id=s['products'][1]['id'])
    body['state']['descricao_revisada']=True
    body['state']['filtros']=['R1','R2']
    data=s['api'].post(s['base']+'/preview',json=body).json()
    assert data['comparacao']['status']=='VERIFICAR'
    assert any('evidencia' in d['motivo'] for d in data['comparacao']['detalhes'])


def test_full_requirements_still_apply_when_filter_is_unchecked(scenario):
    s=scenario;body=draft(s,catalog_product_id=s['products'][0]['id'])
    body['state']['descricao_revisada']=True
    body['state']['filtros']=[]
    data=s['api'].post(s['base']+'/preview',json=body).json()
    assert data['comparacao']['status']=='NAO_ATENDE'


def test_save_pending_candidate_preserves_prices_and_original_json(scenario):
    s=scenario;body=draft(s,catalog_product_id=s['products'][1]['id'])
    data=s['api'].post(s['base']+'/preview',json=body).json()
    body['catalog_hash']=next(c['hash_catalogo'] for c in data['candidatos'] if c['id']==body['catalog_product_id'])
    response=s['api'].request('PUT',s['base'],json=body)
    assert response.status_code==200,response.text
    saved=s['api'].get(s['base']).json()
    assert saved['selecionado_status']=='para_revisao'
    item=s['api'].get('/crm/query/notice_products',params={'filters':json.dumps([{'column':'id','op':'eq','value':s['item']['id']}])}).json()['data'][0]
    assert item['raw_payload']['preservar']=='original'
    assert item['quantity']==3 and item['unit_price']==1000 and item['minimum_unit_price']==900
    assert item['catalog_product_id'] is None
    assert s['api'].request('PUT',s['base'],json=body).status_code==409


def test_unresolved_source_conflicts_cannot_be_dropped(scenario):
    s=scenario;body=draft(s)
    body['state']['fonte_json']['payload']['conflitos_documentais']=['Duas versões divergentes']
    body['state']['pendencias']=[]
    data=s['api'].post(s['base']+'/preview',json=body).json()
    assert data['state']['pendencias'][0]['campo']=='conflitos_documentais'


@pytest.mark.parametrize('text',['{"a":1,"a":2}','{"valor":NaN}','[]','{'])
def test_invalid_or_ambiguous_json_is_rejected(scenario,text):
    assert scenario['api'].post(scenario['base']+'/import',json={'json_text':text}).status_code==422


def test_foreign_item_json_is_rejected(scenario):
    assert scenario['api'].post(scenario['base']+'/import',json={'json_text':json.dumps({'item':{'id_interno':'other'},'requisitos':[]})}).status_code==422


def test_permissions_and_tenant_isolation(scenario,clients,anonymous):
    s=scenario
    assert anonymous.get(s['base']).status_code==401
    assert clients('alpha','admin').get(s['base']).status_code==404
    assert clients('empty','viewer').request('PUT',s['base'],json=draft(s)).status_code==403


def test_confirm_requires_current_catalogue_and_real_bound_evidence(scenario):
    s=scenario;product=s['products'][1]
    pdf=io.BytesIO();document=canvas.Canvas(pdf);document.drawString(30,780,'EXEMPLO SIMULADO: 24 portas RJ45; switch gerenciavel.');document.save()
    response=s['api'].post(f"/crm/catalog-products/{product['id']}/datasheets",files={'file':('EXEMPLO-SIMULADO.pdf',pdf.getvalue(),'application/pdf')})
    assert response.status_code==200,response.text
    sheet=response.json()
    evidence={'documento_id':sheet['id'],'pagina':1,'revisado':True}
    response=s['api'].request('PUT',f"/crm/catalog-products/{product['id']}/technical-sheet",json={'categoria':'switch','atributos':{
        'portas_rj45':{'valor':24,'evidencias':[evidence]},'gerenciavel':{'valor':True,'evidencias':[evidence]}}})
    assert response.status_code==200,response.text
    body=draft(s,catalog_product_id=product['id'],confirm=True)
    body['state']['descricao_revisada']=True
    data=s['api'].post(s['base']+'/preview',json=body).json()
    assert data['comparacao']['status']=='ATENDE'
    body['catalog_hash']='stale'
    assert s['api'].request('PUT',s['base'],json=body).status_code==409
    body['catalog_hash']=next(c['hash_catalogo'] for c in data['candidatos'] if c['id']==product['id'])
    response=s['api'].request('PUT',s['base'],json=body)
    assert response.status_code==200,response.text
    assert response.json()['state']['selected_status']=='confirmado'
    payload=s['api'].get(f"/crm/notices/{s['notice']['id']}/matches").json()
    match=next(m for entry in payload['items'] for m in entry['matches'] if m['catalog_product_id']==product['id'])
    assert match['status']=='confirmed'
    assert match['technical_result']['status']=='ATENDE'
    exported=s['api'].get(f"/crm/notices/{s['notice']['id']}/products/{s['item']['id']}/match-json").json()
    assert len(exported['match_manual']['requisitos'])==2
    assert '_manual_match' not in exported['raw']['payload_original']


def test_explicit_lpu_mixed_speed_signal_is_not_documentary_evidence():
    from types import SimpleNamespace
    from app.services.manual_match import catalog_payload
    row=SimpleNamespace(specification='24x10/100/1000M RJ45 + 4x100M/1000M/10G SFP+',
                        description='', sku='TEST', category='switch')
    offered=catalog_payload(row,signals=True)
    assert offered['atributos']['portas_rj45']['valor']==24
    assert offered['atributos']['portas_sfp_plus']['valor']==4
    assert offered['atributos']['portas_sfp_plus']['evidencias']==[]
    assert catalog_payload(row)['atributos']=={}


def test_selecting_a_product_requires_category(scenario):
    body=draft(scenario,catalog_product_id=scenario['products'][1]['id'])
    body['state']['categoria']=None
    assert scenario['api'].request('PUT',scenario['base'],json=body).status_code==422


def test_invalid_catalogue_numbers_do_not_escape_into_preview_json():
    from types import SimpleNamespace
    from app.services.manual_match import catalog_payload
    row=SimpleNamespace(specification='{"atributos":{"portas_rj45":{"valor":NaN}}}',
                        description='',sku='TEST',category='switch')
    assert catalog_payload(row)['atributos']=={}
