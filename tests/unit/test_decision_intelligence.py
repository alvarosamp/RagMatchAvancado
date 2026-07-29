from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.decision_intelligence import generate_decision_intelligence


def _notice(title: str):
    return SimpleNamespace(
        id="notice-1",
        number="PNCP-1",
        title=title,
        auction_date=datetime.now() + timedelta(days=8),
        notice_documents=[],
    )


def _product(model: str, data: dict):
    return SimpleNamespace(
        model=model,
        category="switch",
        manufacturer="Intelbras",
        data=data,
        is_competitor=False,
    )


def test_generate_decision_intelligence_recommends_dispute_for_network_fit():
    text = """
    Pregao eletronico para aquisicao de switch gerenciavel com 24 portas,
    PoE, uplink SFP, garantia e atestado de capacidade tecnica. Exige CNPJ,
    FGTS, CNDT e proposta comercial.
    """

    payload = generate_decision_intelligence(
        notice=_notice("Switch gerenciavel PoE para rede corporativa"),
        full_text=text,
        products=[_product("SG 2404 PoE", {"portas": 24, "poe": True, "sfp": True})],
    )

    assert payload["recommendation"] in {"disputar", "analisar"}
    assert payload["score"] >= 50
    assert "switch" in payload["matched_terms"]
    assert any(item["required"] for item in payload["document_requirements"])
    assert payload["next_actions"]


def test_generate_decision_intelligence_rejects_clear_off_segment_notice():
    payload = generate_decision_intelligence(
        notice=_notice("Compra de merenda escolar e material odontologico"),
        full_text="Contratacao de merenda, medicamento e limpeza urbana.",
        products=[_product("SG 2404 PoE", {"portas": 24})],
    )

    assert payload["recommendation"] == "nao_disputar"
    assert payload["off_segment_terms"]
