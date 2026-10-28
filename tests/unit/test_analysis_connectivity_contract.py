"""Regression checks for the expanded V7 connectivity input contract."""

import pytest

from app.services.analysis_intelligence import BREAKDOWN_FIELDS, aggregate_feature_breakdowns
from app.services.analysis_normalizer import normalize_analysis_result


@pytest.mark.parametrize("category,expected,features", [
    ("Cabo AOC", "Cabo óptico AOC", {"formato": "QSFP28", "comprimento": "3 m"}),
    ("Cabo DAC", "Cabo DAC", {"tipo_cabo": "Passivo", "bitola_awg": "30 AWG"}),
    ("Patch cord", "Patch cord", {"meio": "Optico", "conector_lado_a": "LC"}),
])
def test_expanded_categories_reach_demand_breakdowns_without_losing_evidence(category, expected, features):
    original = {"categoria": category, "caracteristicas_bi": features}
    source = {"schema_version": "7.4.4", "itens_elegiveis": [original]}
    item = normalize_analysis_result(source)["itens_elegiveis"][0]
    assert item["categoria"] == expected
    assert item["_raw_input"] == original
    assert source["itens_elegiveis"][0] == original
    breakdown = aggregate_feature_breakdowns([(1, 20, item["caracteristicas_bi"])], BREAKDOWN_FIELDS[expected])
    for field, value in features.items():
        assert breakdown[field] == [{"valor": value, "unidades": 20, "itens": 1, "editais": 1}]


def test_patch_demand_preserves_separate_item_lines_and_unknown_fiber():
    rows = [
        (1, 20, {"meio": "Optico", "tipo_fibra": "N/C", "comprimento": "2,5 m"}),
        (1, 15, {"meio": "Optico", "tipo_fibra": "SM nao especificado", "comprimento": "2,5 m"}),
    ]
    breakdown = aggregate_feature_breakdowns(rows, BREAKDOWN_FIELDS["Patch cord"])
    assert breakdown["comprimento"] == [{"valor": "2,5 m", "unidades": 35, "itens": 2, "editais": 1}]
    assert breakdown["tipo_fibra"] == [{"valor": "SM nao especificado", "unidades": 15, "itens": 1, "editais": 1}]


def test_new_flat_switch_and_ap_fields_are_available_for_ranking():
    switch = aggregate_feature_breakdowns([(1, 210, {"capacidade_comutacao": "≥16 Gbps"})], BREAKDOWN_FIELDS["Switch"])
    ap = aggregate_feature_breakdowns([(2, 74, {"faixas_frequencia": "2,4/5 GHz", "interface_lan": "Gigabit"})], BREAKDOWN_FIELDS["Access Point"])
    assert switch["capacidade_comutacao"][0]["unidades"] == 210
    assert ap["faixas_frequencia"][0]["valor"] == "2,4/5 GHz"
    assert ap["interface_lan"][0]["unidades"] == 74


def test_redundancy_arrays_preserve_combination_without_unknowns_or_duplicate_counts():
    result = aggregate_feature_breakdowns([
        (1, 10, {"recursos_redundancia": ["N/C", "Stacking", "Stacking", "MLAG"]}),
        (2, 5, {"recursos_redundancia": ["N/C"]}),
    ], BREAKDOWN_FIELDS["Switch"])
    assert result["recursos_redundancia"] == [
        {"valor": "Stacking / MLAG", "unidades": 10, "itens": 1, "editais": 1},
    ]
