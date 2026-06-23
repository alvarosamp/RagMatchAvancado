from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.reports import build_executive_report


def obj(**kwargs):
    return SimpleNamespace(**kwargs)


def test_build_executive_report_uses_items_and_matches():
    notice = obj(
        id="notice-1",
        number="PE 10/2026",
        municipality_name="Aparecida",
        organ=obj(name="Prefeitura"),
        outcome="pending",
        stage="auction",
        auction_date=datetime(2026, 6, 10, 14, 0, tzinfo=timezone.utc),
        estimated_value=12000,
        notice_documents=[obj(status="pending")],
    )
    product = obj(
        id="item-1",
        notice_id="notice-1",
        item_number="1",
        lot="A",
        description="Switch 24 portas PoE gerenciavel",
        quantity=2,
        reference_price=1500,
        reference_total_price=3000,
        product_matches=[],
    )
    result = obj(winner_type="us", winning_price=1400, winning_quantity=2)
    match = obj(overall_score=0.82)

    report = build_executive_report(
        editais=[obj()],
        notices=[notice],
        products=[product],
        item_results=[result],
        matches=[match],
        generated_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
    )

    assert report["kpis"]["oportunidades_ativas"] == 1
    assert report["kpis"]["itens_em_editais"] == 1
    assert report["kpis"]["itens_ganhos"] == 1
    assert report["kpis"]["valor_ganho_por_item"] == 2800
    assert report["kpis"]["matches_fortes"] == 1
    assert report["kpis"]["documentos_pendentes"] == 1
    assert report["proximas_disputas"][0]["titulo"] == "Aparecida"
    assert report["itens_prioritarios"][0]["valor_total"] == 3000
    assert any("Rodar match" in text for text in report["recomendacoes"])
