from types import SimpleNamespace
import json
from app.services.catalog_identity import product_category
from app.services.item_requirement_suggestions import suggest_requirements
from app.services.catalog_technical_sheet import effective_sheet
from app.services.crm_intelligence_read import json_value


def test_sheet_name_brand_is_not_a_product_and_switch_accessory_is_not_switch():
    assert product_category('tp_link', 'Switch gerenciável 24 portas') == 'switch'
    assert product_category('tp_link', 'Access Point Wi-Fi 6') == 'access_point'
    assert product_category('switch', 'AC power supply for S3600 PoE switch') == 'fonte'
    assert product_category('tp_link', '') is None


def test_screenshot_description_becomes_individual_technical_points():
    text='Switch L2 tipo I, 24 portas 10/100/1000, VLAN IEEE 802.1Q, mínimo 4 portas de expansão 10 Gigabit Ethernet'
    rows=suggest_requirements(text,'switch',{},'2')
    def values(name): return [r['valor'] for r in rows if r['campo_normalizado']==name]
    assert values('camada') == ['L2']
    assert values('tipo_switch') == ['I']
    assert values('portas_acesso') == [24]
    assert values('vlan_802_1q') == [True]
    assert values('portas_expansao') == [4]
    assert values('velocidade_uplink_mbps') == [10000]
    assert all(row['revisado'] is False for row in rows)


def test_legacy_catalog_sheet_is_not_empty_and_does_not_inherit_notice_requirements():
    product=SimpleNamespace(specification='Descrição antiga',sku='SW24',category='tp_link',
        description='Switch L2 24x10/100/1000M RJ45',brand='TP-Link',model='SW24')
    sheet=effective_sheet(product)
    assert sheet['categoria']=='switch'
    assert sheet['atributos']['portas_rj45']['valor']==24
    assert sheet['descricao_anterior']=='Descrição antiga'
    assert sheet['atributos']['portas_rj45']['evidencias']==[]


def test_nonfinite_nested_values_do_not_break_demand_json_response():
    data=json_value({'raw': {'value':float('nan')},'infinite':float('inf')})
    assert data=={'raw':{'value':None},'infinite':None}
    json.dumps(data,allow_nan=False)


def test_legacy_transceiver_sheet_exposes_explicit_distance_rate_and_connector():
    product=SimpleNamespace(specification=None,sku='CFP2',category='transceiver',
        description='CFP2 ER4 40km SMF, 100GBase, DDM, LC',brand='PRECISION',model='CFP2')
    attrs=effective_sheet(product)['atributos']
    assert attrs['alcance_m']['valor']==40000
    assert attrs['taxa_nominal_gbps']['valor']==100
    assert attrs['conector']['valor']=='LC'
    assert attrs['tipo_fibra']['valor']=='SMF'


def test_manually_reviewed_alias_is_not_shadowed_by_legacy_description():
    product=SimpleNamespace(specification=json.dumps({'atributos':{'RJ45 ports':{'valor':48}}}),
        sku='SW',category='switch',description='Switch 24x10/100/1000M RJ45',brand='TOR',model='SW')
    attrs=effective_sheet(product)['atributos']
    assert attrs['RJ45 ports']['valor']==48
    assert 'portas_rj45' not in attrs


def test_legacy_port_count_handles_mbps_spelling_and_portas_keyword():
    for description in ['Switch 24x10/100/1000Mbps RJ45', 'Switch 24 portas 10/100/1000M RJ45']:
        product=SimpleNamespace(specification=None,sku='SW',category='switch',description=description,brand='TOR',model='SW')
        assert effective_sheet(product)['atributos']['portas_rj45']['valor']==24


def test_switch_with_accessories_keeps_its_product_kind():
    assert product_category('switch','Switch 48 portas acompanha 50m de cabo')=='switch'
    assert product_category('switch','Switch 24 portas power supply 220V')=='switch'
    assert product_category('switch','AC power supply module for switch')=='fonte'
