"""Explicit spelling aliases without merging different technical meanings."""
import pytest

from app.services.technical_matching.normalizer import (
    canonical_name, canonical_category, normalize_value, build_alias_index,
)
from app.services.technical_matching.engine import compare_item_product
from app.services.manual_match import display_attributes


@pytest.mark.parametrize('label', [
    'Portas RJ45', 'PORTAS RJ-45', 'Quantidade de portas RJ45', 'Qtd portas RJ45',
    'RJ-45 ports', 'PortasRJ45', 'interfaces.portas_acesso_rj45_qtd', ' Portas  RJ45 ',
])
def test_explicit_rj45_spellings(label):
    assert canonical_name(label) == 'portas_rj45'


@pytest.mark.parametrize('label', ['Portas SFP+', 'Portas SFP +', 'SFP+ ports', 'Slots SFP+', 'PortasSFPPlus'])
def test_sfp_plus_spellings(label):
    assert canonical_name(label) == 'portas_sfp_plus'


@pytest.mark.parametrize('first,second', [
    ('Portas SFP', 'Portas SFP+'), ('Portas SFP+', 'Portas QSFP+'),
    ('Portas SFP+', 'Portas SFP28'), ('PoE', 'PoE+'), ('PoE+', 'PoE++'),
    ('Comprimento onda Tx nm', 'Comprimento onda Rx nm'),
    ('velocidade_uplink_mbps', 'velocidade_wifi_mbps'),
    ('poe_budget_w', 'poe_budget_kw'),
])
def test_different_technical_fields_do_not_merge(first,second):
    assert canonical_name(first) != canonical_name(second)


@pytest.mark.parametrize('label,expected', [
    ('ACCESS-POINT', 'access_point'), ('Pontos de acesso', 'access_point'),
    ('Transceptores', 'transceiver'), ('Módulo transceptor', 'transceiver'),
    ('Switches', 'switch'),
])
def test_explicit_category_aliases(label,expected):
    assert canonical_category(label)==expected


def test_unknown_category_is_not_fuzzily_approved():
    assert canonical_category('swicth') != 'switch'
    result=compare_item_product({'categoria':'swicth','requisitos':{'portas_rj45':{'valor':24}}},
                                {'categoria':'switch','atributos':{'portas_rj45':24}})
    assert result['status'] != 'ATENDE'


def test_alias_collisions_fail_instead_of_last_definition_winning():
    with pytest.raises(ValueError,match='ambíguo'):
        build_alias_index({'portas_sfp': ['SFP +'], 'portas_sfp_plus': ['SFP+']})
    assert build_alias_index({'portas_sfp_plus':['SFP+','SFP +']})['sfp_plus']=='portas_sfp_plus'


@pytest.mark.parametrize('first,second', [
    ('TL-SG3428MP V1','TL-SG3428MP V2'), ('ISCOM S2600-24T4X-AC/S','ISCOM S2600-24T4X-AC-S'),
    ('KSFP10-0031SL10C','KSFP10-0031SL20C'), ('ABC+','ABC'), ('ABC-10','ABC10'),
    ('L2+','L2'), ('Wi-Fi 5','Wi-Fi 6'),
])
def test_product_identifiers_and_technical_values_keep_discriminators(first,second):
    assert normalize_value(first,kind='string') != normalize_value(second,kind='string')


def test_conflicting_alias_values_remain_pending():
    result=compare_item_product({'requisitos':{'Portas RJ-45':{'valor':24}}},
                                {'atributos':{'PortasRJ45':24,'Qtd portas RJ45':48}})
    assert result['status']=='VERIFICAR'
    assert 'conflitantes' in result['detalhes'][0]['motivo']


def test_cards_use_engine_alias_keys_without_losing_multiple_sources():
    single=display_attributes({'RJ-45 ports':{'valor':24}})
    assert single['portas_rj45']['valor']==24
    multiple=display_attributes({'RJ-45 ports':{'valor':24},'PortasRJ45':{'valor':48}})
    assert len(multiple['portas_rj45']['campos_originais'])==2
    assert 'matriz' in multiple['portas_rj45']['valor']


def test_poe_base_support_does_not_prove_poe_plus():
    result=compare_item_product({'requisitos':{'PoE+':{'valor':True}}},{'atributos':{'PoE':True}})
    assert result['status']=='VERIFICAR'
