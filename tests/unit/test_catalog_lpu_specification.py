import json
from app.services.catalog_lpu_specification import refresh_lpu_specification


def refresh(old=None, description='24x10/100/1000M RJ45 + 4x10G SFP+, L2 manageable PoE', version='v1'):
    return json.loads(refresh_lpu_specification(old, {'description': description, 'sku': 'S1',
        'category': 'switch', 'lpu_drive_url': 'https://drive.google.com/lpu', 'lpu_version': version},
        values={'description': description, 'distance': '20km'}, sheet='Switches', row=2))


def test_import_generates_traceable_json_and_no_document_evidence():
    p = refresh()
    assert p['atributos']['portas_rj45']['valor'] == 24
    assert p['atributos']['portas_sfp_plus']['valor'] == 4
    assert 'portas_sfp' not in p['atributos']
    assert p['atributos']['alcance_m']['valor'] == 20000
    assert p['atributos']['poe']['evidencias'] == []
    assert p['dados_lpu']['linha'] == 2


def test_reimport_refreshes_and_removes_obsolete_commercial_facts():
    p = refresh(json.dumps(refresh()), description='48x10/100/1000M RJ45', version='v2')
    assert p['atributos']['portas_rj45']['valor'] == 48
    assert 'poe' not in p['atributos']
    assert 'portas_sfp_plus' not in p['atributos']
    assert p['dados_lpu']['versao'] == 'v2'


def test_reviewed_attribute_and_revision_survive_commercial_conflict():
    old = {'atributos': {'portas_rj45': {'valor': 48, 'evidencias': [{'documento_id': 'D'}]}}, 'revisao': 7}
    p = refresh(json.dumps(old))
    assert p['atributos']['portas_rj45'] == old['atributos']['portas_rj45']
    assert p['dados_lpu']['atributos_extraidos']['portas_rj45']['valor'] == 24
    assert p['revisao'] == 7


def test_missing_support_is_not_false():
    p = refresh(description='Produto genérico')
    assert 'poe' not in p['atributos']
    assert 'gerenciavel' not in p['atributos']


def test_reviewed_alias_does_not_gain_a_conflicting_generated_attribute():
    p = refresh(json.dumps({'atributos': {'Portas RJ45': {'valor': 48}}}))
    assert p['atributos']['Portas RJ45']['valor'] == 48
    assert 'portas_rj45' not in p['atributos']
