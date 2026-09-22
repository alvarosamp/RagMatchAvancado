from types import SimpleNamespace

from app.services import analysis_store
from app.services.analysis_contract_values import display_contract_term


def test_structured_v8_term_preserves_literal_text() -> None:
    value = {
        "operador": ">=", "valor": 12, "unidade": "meses",
        "condicao": "a partir da entrega",
        "texto_original": "Garantia mínima de 12 meses a partir da entrega.",
    }
    assert display_contract_term(value) == value["texto_original"]


def test_structured_v8_term_has_safe_fallback_and_legacy_text() -> None:
    assert display_contract_term({
        "operador": "<=", "valor": 10, "unidade": "dias",
        "condicao": "úteis", "texto_original": "N/C",
    }) == "<= 10 dias úteis"
    assert display_contract_term("12 meses") == "12 meses"
    assert display_contract_term("N/C") == "N/C"


def test_analysis_store_reads_v8_unit_and_structured_terms(monkeypatch) -> None:
    monkeypatch.setattr(analysis_store, "AnalysisItem", lambda **values: SimpleNamespace(**values))
    item = analysis_store._build_analysis_item({
        "categoria": "Switch", "numero_item_edital": "4",
        "descricao_original": "Switch PoE", "quantidade": 2,
        "unidade_fornecimento": "UN",
        "garantia": {
            "operador": ">=", "valor": 12, "unidade": "meses",
            "condicao": "N/C", "texto_original": "Garantia mínima de 12 meses",
        },
        "prazo_entrega": "N/C",
    })
    assert item.unit == "UN"
    assert item.quantity == 2
    assert item.garantia == "Garantia mínima de 12 meses"
    assert item.raw_payload["garantia"]["operador"] == ">="
