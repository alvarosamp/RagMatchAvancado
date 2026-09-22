from app.services.analysis_intelligence import BREAKDOWN_FIELDS, aggregate_feature_breakdowns


def test_switch_rankings_count_notices_items_and_units_without_inference():
    rows = [
        (1, 35, {"switch": {"interfaces": {"portas_acesso_rj45_qtd": "24"}, "poe": {"poe_padroes": "N/C"}}}),
        (1, 10, {"switch": {"interfaces": {"portas_acesso_rj45_qtd": "24"}, "poe": {"poe_padroes": "802.3at"}}}),
        (2, 100, {"quantidade_portas": "8 Portas", "alimentacao_poe": "Não PoE"}),
        (3, None, {"switch": {"interfaces": {"portas_acesso_rj45_qtd": "N/C"}}}),
    ]

    result = aggregate_feature_breakdowns(rows, BREAKDOWN_FIELDS["Switch"])

    assert result["quantidade_portas"] == [
        {"valor": "8", "unidades": 100, "itens": 1, "editais": 1},
        {"valor": "24", "unidades": 45, "itens": 2, "editais": 1},
    ]
    assert result["alimentacao_poe"] == [
        {"valor": "Não PoE", "unidades": 100, "itens": 1, "editais": 1},
        {"valor": "802.3at", "unidades": 10, "itens": 1, "editais": 1},
    ]
