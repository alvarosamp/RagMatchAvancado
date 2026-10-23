import json
import pytest
from app.services.catalog_json_import import validate_product, merge_specification


def sample():
    return {'codigos_tor': ['TOR-123'], 'datasheets': [], 'especificacoes_tecnicas': [
        {'nome': 'portas_rj45', 'valor': 24, 'validacao': 'informado_na_lpu'},
        {'nome': 'capacidade', 'valor': 120, 'validacao': 'revisar_aplicabilidade'}]}


def test_generated_format_and_only_explicit_lpu_facts():
    data = sample()
    assert validate_product(data) == ['TOR-123']
    result = json.loads(merge_specification(None, data))
    assert result['atributos']['portas_rj45']['valor'] == 24
    assert 'capacidade' not in result['atributos']
    assert result['importacao_json_produto'] == data
    assert result['atributos']['portas_rj45']['evidencias'] == []


def test_preserve_reviewed_values_and_replace_owned_unreviewed():
    old = json.loads(merge_specification(None, sample()))
    old['atributos']['portas_rj45']['revisado'] = True
    incoming = sample()
    incoming['especificacoes_tecnicas'][0]['valor'] = 48
    result = json.loads(merge_specification(json.dumps(old), incoming))
    assert result['atributos']['portas_rj45']['valor'] == 24
    old['atributos']['portas_rj45']['revisado'] = False
    result = json.loads(merge_specification(json.dumps(old), incoming))
    assert result['atributos']['portas_rj45']['valor'] == 48


def test_reject_inventory_and_invalid_identifiers():
    for value in [[], {}, {'codigos_tor': [''], 'especificacoes_tecnicas': []}]:
        with pytest.raises(ValueError):
            validate_product(value)


def test_reject_nonfinite_and_wrong_metadata_before_database_changes():
    for data in [dict(sample(), marca={}), dict(sample(), descricoes_lpu='incorrect'),
                 dict(sample(), extra=float('inf'))]:
        with pytest.raises(ValueError):
            validate_product(data)


def test_preserve_legacy_description_and_drop_stale_owned_fact():
    original = json.loads(merge_specification('Descrição antiga', sample()))
    empty = dict(sample(), especificacoes_tecnicas=[])
    result = json.loads(merge_specification(json.dumps(original), empty))
    assert result['descricao_anterior'] == 'Descrição antiga'
    assert result['atributos'] == {}
