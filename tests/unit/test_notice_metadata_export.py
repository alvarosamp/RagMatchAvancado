from types import SimpleNamespace as Obj

from app.services.notice_metadata_export import build_notice_metadata_export


def notice(**kwargs):
    return Obj(id='n', tenant_id=1, organ=None, portal=None, **kwargs)


def test_original_payload_and_analysis_preserved_without_inferred_criteria():
    raw = {'descricao': 'Switch 24 portas', 'extra': {'x': True}}
    product = Obj(id='i', raw_payload=raw)
    analysis = Obj(result={'itens': [raw]}, full_text='Texto do TR')
    result = build_notice_metadata_export(notice(), [product], [], analysis)
    assert result['itens'][0]['raw_payload'] == raw
    assert result['itens'][0]['criterios_originais'] == {}
    assert result['analise_original']['result'] == analysis.result
    assert result['diagnostico']['itens_com_criterios'] == 0
    assert 'texto_extraido' not in result['analise_original']
    result['itens'][0]['raw_payload']['extra']['x'] = False
    assert raw['extra']['x'] is True


def test_text_is_opt_in_and_explicit_empty_criteria_preserved():
    product = Obj(id='i', raw_payload={'_raw_input': {'criterios_comparacao': []}})
    analysis = Obj(result={}, full_text='Original')
    result = build_notice_metadata_export(notice(), [product], [], analysis, include_text=True)
    assert result['analise_original']['texto_extraido'] == 'Original'
    assert result['itens'][0]['criterios_originais'] == {'criterios_comparacao': []}
    assert result['diagnostico']['itens_com_criterios'] == 0


def test_export_works_without_items_or_linked_analysis():
    result = build_notice_metadata_export(notice(), [], [])
    assert result['itens'] == []
    assert result['analise_original'] is None
    assert result['diagnostico']['avisos'][0]['codigo'] == 'SEM_ANALISE_VINCULADA'


def test_linked_organ_from_other_tenant_not_exported():
    n = notice()
    n.organ = Obj(id='o', name='Other tenant', tenant_id=2)
    assert build_notice_metadata_export(n, [], [])['edital']['organ'] is None


def test_criteria_duplicates_and_unknown_fields_preserved():
    criteria = [{'id': 'a', 'campo': 'x', 'valor': 24}, {'id': 'b', 'campo': 'x', 'valor': 48}]
    product = Obj(id='i', raw_payload={'criterios_comparacao': criteria, 'new_field': [1, 2]})
    result = build_notice_metadata_export(notice(), [product], [])
    assert result['itens'][0]['criterios_originais']['criterios_comparacao'] == criteria
    assert result['itens'][0]['raw_payload']['new_field'] == [1, 2]
    assert result['diagnostico']['itens_com_criterios'] == 1
