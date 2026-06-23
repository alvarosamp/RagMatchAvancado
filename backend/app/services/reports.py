from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return getattr(value, "value", str(value))


def _money(value: float | None) -> float:
    return round(float(value or 0), 2)


def _notice_label(notice: Any) -> str:
    return (
        getattr(notice, "municipality_name", None)
        or getattr(getattr(notice, "organ", None), "name", None)
        or getattr(notice, "number", None)
        or "Edital sem identificacao"
    )


def build_executive_report(
    *,
    editais: list[Any],
    notices: list[Any],
    products: list[Any],
    item_results: list[Any],
    matches: list[Any],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    now = generated_at or datetime.now(timezone.utc)
    active_notices = [
        notice
        for notice in notices
        if _enum_value(getattr(notice, "outcome", None)) in (None, "pending")
        and _enum_value(getattr(notice, "stage", None)) != "result"
    ]
    upcoming = sorted(
        [notice for notice in active_notices if getattr(notice, "auction_date", None)],
        key=lambda notice: notice.auction_date,
    )[:8]
    stage_counts = Counter(_enum_value(getattr(notice, "stage", None)) for notice in notices)
    outcome_counts = Counter(_enum_value(getattr(notice, "outcome", None)) for notice in notices)
    match_scores = [float(match.overall_score or 0) for match in matches]
    strong_matches = sum(1 for score in match_scores if score >= 0.75)
    won_results = [
        result
        for result in item_results
        if _enum_value(getattr(result, "winner_type", None)) == "us"
    ]
    won_value = sum(
        (result.winning_price or 0) * (result.winning_quantity or 1)
        for result in won_results
    )

    valuable_items = sorted(
        products,
        key=lambda product: product.reference_total_price
        or ((product.reference_price or 0) * (product.quantity or 1)),
        reverse=True,
    )[:8]
    pending_docs = sum(
        1
        for notice in notices
        for doc in getattr(notice, "notice_documents", []) or []
        if _enum_value(getattr(doc, "status", None)) in ("pending", "expired")
    )
    missing_match_items = sum(
        1
        for product in products
        if not getattr(product, "product_matches", None)
    )

    recommendations: list[str] = []
    if pending_docs:
        recommendations.append(
            f"Regularizar {pending_docs} documentos pendentes ou vencidos antes dos proximos pregoes."
        )
    if missing_match_items:
        recommendations.append(
            f"Rodar match em {missing_match_items} itens sem comparacao com o catalogo."
        )
    if upcoming:
        recommendations.append(
            "Priorizar os editais com disputa mais proxima e valor de referencia mais alto."
        )
    if not recommendations:
        recommendations.append(
            "Operacao sem alertas criticos; manter rotina semanal de revisao comercial."
        )

    return {
        "generated_at": now.isoformat(),
        "title": "Relatorio executivo de licitacoes",
        "summary": (
            f"{len(active_notices)} oportunidades ativas, "
            f"{len(products)} itens mapeados e {strong_matches} matches fortes no CRM."
        ),
        "kpis": {
            "editais_processados": len(editais),
            "oportunidades_crm": len(notices),
            "oportunidades_ativas": len(active_notices),
            "itens_em_editais": len(products),
            "itens_ganhos": len(won_results),
            "valor_estimado_ativo": _money(
                sum(notice.estimated_value or 0 for notice in active_notices)
            ),
            "valor_ganho_por_item": _money(won_value),
            "matches_fortes": strong_matches,
            "documentos_pendentes": pending_docs,
        },
        "pipeline": {
            "por_fase": dict(stage_counts),
            "por_resultado": dict(outcome_counts),
        },
        "proximas_disputas": [
            {
                "id": notice.id,
                "titulo": _notice_label(notice),
                "numero": notice.number,
                "fase": _enum_value(notice.stage),
                "data": notice.auction_date.isoformat()
                if notice.auction_date
                else None,
                "valor_estimado": _money(notice.estimated_value),
            }
            for notice in upcoming
        ],
        "itens_prioritarios": [
            {
                "id": product.id,
                "notice_id": product.notice_id,
                "item": product.item_number,
                "lote": product.lot,
                "descricao": product.description,
                "quantidade": product.quantity,
                "valor_referencia": _money(product.reference_price),
                "valor_total": _money(
                    product.reference_total_price
                    or ((product.reference_price or 0) * (product.quantity or 1))
                ),
            }
            for product in valuable_items
        ],
        "recomendacoes": recommendations,
    }
