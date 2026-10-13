from app.services.technical_matching.adapter import adapt_item
from app.services.technical_matching import compare_item_product


def criterion(value=370):
    return {'id': 'poe-min', 'campo_normalizado': 'poe.poe_budget_w', 'operador': '>=', 'valor': value, 'unidade': 'W'}


def product(value=410, documented=True):
    return {'categoria': 'switch', 'atributos': {'poe_budget_w': {'valor': value, 'evidencias': [{'documento_id': 'sheet', 'hash_documento': 'abc', 'pagina': 1, 'revisado': documented}]}}}


def test_documented_v8_flow_and_mandatory_failure():
    item = adapt_item({'categoria': 'switch', 'criterios_comparacao': [criterion()]})
    assert compare_item_product(item, product())['status'] == 'ATENDE'
    assert compare_item_product(item, product(180))['status'] == 'NAO_ATENDE'
    assert compare_item_product(item, product(documented=False))['status'] == 'VERIFICAR'


def test_empty_criteria_do_not_fall_back_and_unknown_scope_stays_pending():
    assert compare_item_product(adapt_item({'criterios_comparacao': []}), product())['status'] == 'VERIFICAR'
    rule = {**criterion(), 'escopo': 'OM3'}
    assert compare_item_product(adapt_item({'criterios_comparacao': [rule]}), product())['status'] == 'VERIFICAR'


def test_duplicate_criteria_preserve_ids_and_bounds():
    maximum = {**criterion(400), 'id': 'poe-max', 'operador': '<='}
    result = compare_item_product(adapt_item({'criterios_comparacao': [criterion(), maximum]}), product())
    assert [r['id'] for r in result['detalhes']] == ['poe-min', 'poe-max']
    assert result['status'] == 'NAO_ATENDE'


def test_fractional_port_count_is_pending_and_snapshot_changes():
    item = {'requisitos': {'portas_rj45': {'operador': '>=', 'valor': 24}}}
    result = compare_item_product(item, {'atributos': {'portas_rj45': 24.5}})
    assert result['status'] == 'VERIFICAR'
    assert result['hash_produto'] != compare_item_product(item, {'atributos': {'portas_rj45': 24}})['hash_produto']


def test_ranges_sets_scoped_fiber_and_or_groups():
    def compare(rule, value):
        return compare_item_product({'requisitos': {'capacidade': rule}}, {'atributos': {'capacidade': value}})
    assert compare({'operador':'cobre_faixa', 'valor':{'min':-10, 'max':50}}, {'min':-20, 'max':60})['status'] == 'ATENDE'
    assert compare({'operador':'cobre_faixa', 'valor':{'min':-10, 'max':50}}, {'min':0, 'max':60})['status'] == 'NAO_ATENDE'
    assert compare({'operador':'contem_todos', 'valor':['L2','L3']}, ['L2'])['status'] == 'NAO_ATENDE'
    assert compare({'operador':'em', 'valor':['OM3','OM4']}, 'OM3')['status'] == 'ATENDE'
    item = {'requisitos': {'alcance_m': {'valor':100, 'operador':'>=', 'escopo':{'tipo_fibra':'OM3'}}}}
    optical = {'atributos':{'alcance_m': {'variantes':[{'valor':100, 'escopo':{'tipo_fibra':'OM4'}}, {'valor':70, 'escopo':{'tipo_fibra':'OM3'}}]}}}
    assert compare_item_product(item, optical)['status'] == 'NAO_ATENDE'
    grouped = {'requisitos':[{'id':'a','atributo':'x','valor':1,'grupo_logico':'G','operador_logico':'OU'}, {'id':'b','atributo':'y','valor':2,'grupo_logico':'G','operador_logico':'OU'}]}
    assert compare_item_product(grouped, {'atributos':{'x':0,'y':2}})['status'] == 'ATENDE'
    assert compare_item_product(grouped, {'atributos':{'x':0}})['status'] == 'VERIFICAR'


def test_facets_use_item_category_and_recalculate_other_filters():
    from app.services.technical_matching.facets import build_facets
    catalog = [{'id':'a','categoria':'switch','atributos':{'portas_rj45':24,'poe':True}}, {'id':'b','categoria':'switch','atributos':{'portas_rj45':48,'poe':False}}, {'id':'c','categoria':'transceiver','atributos':{'poe':True}}]
    result = build_facets({'categoria':'switch'}, catalog, {'poe':[True]})
    assert result['catalog_product_ids'] == ['a']
    assert result['total'] == 2
    assert result['facets']['portas_rj45'] == [{'value':24,'count':1}]
    assert len(result['facets']['poe']) == 2


def test_datasheet_suggestions_preserve_pages_and_never_mark_reviewed():
    from app.services.technical_matching.datasheet_draft import draft_from_pages
    draft = draft_from_pages(['RJ45 ports: 24\nPoE budget: 410 W', 'PoE budget: 180 W'], document_id='doc', document_hash='hash', document_version=2)
    assert 'poe_budget_w' not in draft['atributos']
    assert draft['conflitos'][0]['atributo'] == 'poe_budget_w'
    ports = draft['atributos']['portas_rj45']
    assert ports['valor'] == 24
    assert ports['evidencias'][0]['pagina'] == 1
    assert ports['evidencias'][0]['revisado'] is False
    result = compare_item_product(adapt_item({'criterios_comparacao':[{'campo':'portas_rj45','valor':24}]}), {'atributos':draft['atributos']})
    assert result['status'] == 'VERIFICAR'


def test_changed_requirements_or_sheet_make_saved_matrix_stale():
    from types import SimpleNamespace
    from app.services import crm_item_matcher as crm
    notice = SimpleNamespace(raw_payload={'requisitos':{'poe_budget_w':{'valor':370,'operador':'>='}}})
    catalog = SimpleNamespace(sku='s', category='switch', specification='{"atributos":{"poe_budget_w":410}}')
    saved = crm._rank_structured_candidates(crm._structured_item(notice), [catalog])[0]['technical_match']
    match = SimpleNamespace(technical_result=saved, notice_product=notice, catalog_product=catalog)
    assert crm._technical_stale(match) is False
    catalog.specification='{"atributos":{"poe_budget_w":180}}'
    assert crm._technical_stale(match) is True
    catalog.specification='{"atributos":{"poe_budget_w":410}}'
    notice.raw_payload['requisitos']['poe_budget_w']['valor']=420
    assert crm._technical_stale(match) is True


def test_malformed_group_data_stays_pending():
    item={'requisitos':[{'atributo':'x','valor':1,'grupo_logico':{},'operador_logico':[]}]}
    assert compare_item_product(item, {'atributos':{'x':1}})['status'] == 'VERIFICAR'


def test_temperature_range_and_wavelength_units():
    item = {'requisitos':{'temperatura_operacao_c':{'operador':'cobre_faixa','valor':{'min':-10,'max':60},'unidade':'C'}, 'comprimento_onda_tx_nm':{'valor':850,'unidade':'nm'}}}
    attributes={'temperatura_operacao_c':{'valor':{'min':-40,'max':70},'unidade':'C'},'comprimento_onda_tx_nm':{'valor':850,'unidade':'nm'}}
    assert compare_item_product(item, {'atributos':attributes})['status'] == 'ATENDE'


def test_speed_sets_convert_units():
    item={'requisitos':{'velocidades_porta_mbps':{'operador':'contem_todos','valor':['100 Mbps','1 Gbps']}}}
    assert compare_item_product(item, {'atributos':{'interfaces.velocidades_porta':[100,1000,10000]}})['status'] == 'ATENDE'


def test_rules_execution_filters_catalog_before_comparison(monkeypatch):
    import json
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from app.services import crm_item_matcher as crm
    item=SimpleNamespace(id='item', category='switch', raw_payload={'categoria':'switch','requisitos':{'portas_rj45':{'valor':24}}}, product_matches=[], catalog_product_id=None, reference_total_price=100)
    catalog=[SimpleNamespace(id=str(n),sku=str(n),category='switch',specification=json.dumps({'atributos':{'portas_rj45':n}})) for n in (24,48)]
    db=MagicMock();db.query.return_value.filter.return_value.all.return_value=catalog
    model=MagicMock(side_effect=lambda **kwargs:SimpleNamespace(**kwargs))
    monkeypatch.setattr(crm,'CrmCatalogProduct',MagicMock())
    monkeypatch.setattr(crm,'CrmNoticeProductMatch',model)
    monkeypatch.setattr(crm,'CrmNoticeHistory',MagicMock(side_effect=lambda **kwargs:SimpleNamespace(**kwargs)))
    monkeypatch.setattr(crm,'_load_notice',lambda *args:SimpleNamespace(id='notice',notice_products=[item]))
    monkeypatch.setattr(crm,'_build_reusable_match_index',lambda *args:{})
    monkeypatch.setattr(crm,'get_notice_item_match_payload',lambda *args:{})
    monkeypatch.setattr(crm,'ensure_catalog_embeddings',lambda *args:(_ for _ in ()).throw(AssertionError('No AI')))
    crm.run_notice_item_match(db,SimpleNamespace(id=1,tenant_id=2),'notice',mode='rules',notice_product_id='item',attribute_filters={'portas_rj45':[24]})
    assert model.call_count==1
    assert model.call_args.kwargs['catalog_product_id']=='24'
