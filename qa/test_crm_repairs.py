"""Real HTTP regressions for operational demand, refresh and native JSON attachment."""
import json


def test_current_demand_and_commercial_refresh_without_analytics_worker(clients, unique):
    api = clients('empty', 'admin')
    def create(table, values):
        response=api.post(f'/crm/query/{table}/insert', json={'values':values})
        assert response.status_code==200,response.text
        return response.json()['data'][0]
    notice=create('notices',{'number':'REPAIR-'+unique, 'title':'DEMONSTRAÇÃO — regressão CRM'})
    product=create('catalog_products',{'sku':'REPAIR-'+unique,'brand':'TP-Link','category':'tp_link','model':'DEMO SW24',
        'description':'Switch L2 24x10/100/1000M RJ45'})
    assert product['category']=='switch'
    assert json.loads(product['specification'])['atributos']['portas_rj45']['valor']==24
    item=create('notice_products',{'notice_id':notice['id'],'item_number':'2', 'category':'switch','quantity':55,
        'reference_price':3875,'description':'Switch L2 tipo I, 24 portas 10/100/1000, VLAN IEEE 802.1Q, mínimo 4 portas de expansão 10 Gigabit Ethernet',
        'raw_payload':{'caracteristicas_bi':{'quantidade_portas':'24 Portas','camada':'L2'}}})
    demand=api.get('/crm/intelligence/notices')
    assert demand.status_code==200,demand.text
    own=next(n for n in demand.json()['data'] if n['id']==notice['id'])
    assert own['notice_products'][0]['reference_total_price']==213125
    foreign=clients('alpha','admin').get('/crm/intelligence/notices').json()['data']
    assert notice['id'] not in {n['id'] for n in foreign}
    download=api.get(f"/crm/notices/{notice['id']}/products/{item['id']}/match-json?download=true")
    assert download.status_code==200 and 'attachment;' in download.headers['Content-Disposition']
    assert download.json()['item']['id_interno']==item['id']
    match=api.get(f"/crm/notices/{notice['id']}/products/{item['id']}/manual-match")
    assert match.status_code==200,match.text
    assert 'tp_link' not in match.json()['categorias']
    assert 'marca' in match.json()['facetas']
    fields={row['atributo'] for row in match.json()['state']['requisitos']}
    assert {'camada','portas_acesso','vlan_802_1q','portas_expansao','velocidade_uplink_mbps'}<=fields
    report=api.session.get(__import__('os').environ['QA_API_URL']+'/crm/market-intelligence/report',timeout=90)
    assert report.status_code==200,report.text
    assert report.json()['summary']['internal_demand_items']>=1
    assert report.json()['crm_refresh']['status'] == 'operational'
    updated=api.patch('/crm/query/notice_products',json={'values':{'quantity':60},'filters':[{'column':'id','op':'eq','value':item['id']}]})
    assert updated.status_code==200,updated.text
    report=api.session.get(__import__('os').environ['QA_API_URL']+'/crm/market-intelligence/report',timeout=90)
    assert report.status_code==200,report.text
    assert report.json()['crm_refresh']['status']=='operational'
    details=api.get('/crm/market-intelligence/facts?kind=demand&limit=200')
    assert details.status_code==200,details.text
    current=next(row for row in details.json()['rows'] if row['item_id']==item['id'])
    assert current['quantity']==60 and current['total_value']==232500
    again=api.get('/crm/market-intelligence/report')
    assert again.status_code==200 and again.json()['crm_refresh']['status']=='operational'
