from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AnalysisItem, Product
from app.services.attribute_parsers import compare_product_specs
from app.services.opportunity_radar import product_search_text


@dataclass(frozen=True)
class OwnCounter:
    product_id: int
    model: str
    manufacturer: str | None
    category: str | None
    score: int
    advantages: int
    disadvantages: int
    ties: int
    key_edges: list[str]
    vulnerabilities: list[str]


def build_competitive_intelligence(db: Session, *, category: str | None = None, limit: int = 50) -> dict[str, Any]:
    own_query = db.query(Product).filter(Product.is_competitor.is_(False))
    competitor_query = db.query(Product).filter(Product.is_competitor.is_(True))
    if category:
        own_query = own_query.filter(Product.category == category)
        competitor_query = competitor_query.filter(Product.category == category)

    own_products = own_query.order_by(Product.model).all()
    competitor_products = competitor_query.order_by(Product.manufacturer, Product.model).limit(limit).all()
    history = _build_history(db)

    rows: list[dict[str, Any]] = []
    manufacturer_stats: dict[str, dict[str, Any]] = {}
    global_gaps: dict[str, int] = defaultdict(int)

    for competitor in competitor_products:
        counters = [_counter_for(own, competitor) for own in own_products]
        counters.sort(key=lambda item: item.score, reverse=True)
        for counter in counters[:3]:
            for field in counter.vulnerabilities:
                global_gaps[field] += 1

        manufacturer = competitor.manufacturer or "Fabricante nao informado"
        stats = manufacturer_stats.setdefault(
            manufacturer,
            {"manufacturer": manufacturer, "products": 0, "history_hits": 0, "estimated_value": 0.0, "avg_price": None},
        )
        stats["products"] += 1

        row_history = _history_for_product(competitor, history)
        if row_history["occurrences"]:
            stats["history_hits"] += row_history["occurrences"]
            stats["estimated_value"] += row_history["estimated_total_value"] or 0.0

        rows.append({
            "competitor": _serialize_product(competitor),
            "history": row_history,
            "best_own_counters": [_serialize_counter(counter) for counter in counters[:3]],
            "risk_summary": _risk_summary(counters[:3]),
        })

    for stats in manufacturer_stats.values():
        prices = [
            row["history"]["avg_unit_price"]
            for row in rows
            if row["competitor"]["manufacturer"] == stats["manufacturer"] and row["history"]["avg_unit_price"] is not None
        ]
        if prices:
            stats["avg_price"] = round(sum(prices) / len(prices), 2)

    return {
        "summary": {
            "own_products": len(own_products),
            "competitor_products": len(competitor_products),
            "manufacturers": len(manufacturer_stats),
            "history_items_indexed": len(history),
        },
        "manufacturers": sorted(manufacturer_stats.values(), key=lambda item: (item["history_hits"], item["products"]), reverse=True),
        "competitors": rows,
        "global_gaps": [
            {"field": field, "count": count}
            for field, count in sorted(global_gaps.items(), key=lambda item: item[1], reverse=True)[:12]
        ],
    }


def _counter_for(own: Product, competitor: Product) -> OwnCounter:
    comparisons = compare_product_specs(own.data or {}, competitor.data or {})
    advantages = sum(1 for item in comparisons if item.winner == "a")
    disadvantages = sum(1 for item in comparisons if item.winner == "b")
    ties = sum(1 for item in comparisons if item.winner == "tie")
    comparable = max(1, advantages + disadvantages + ties)
    score = int(round(((advantages * 1.0) + (ties * 0.45)) / comparable * 100))
    key_edges = [item.field for item in comparisons if item.winner == "a"][:5]
    vulnerabilities = [item.field for item in comparisons if item.winner == "b"][:5]
    return OwnCounter(
        product_id=own.id,
        model=own.model,
        manufacturer=own.manufacturer,
        category=own.category,
        score=score,
        advantages=advantages,
        disadvantages=disadvantages,
        ties=ties,
        key_edges=key_edges,
        vulnerabilities=vulnerabilities,
    )


def _build_history(db: Session) -> list[AnalysisItem]:
    return (
        db.query(AnalysisItem)
        .filter(
            (AnalysisItem.model.isnot(None))
            | (AnalysisItem.brand.isnot(None))
            | (AnalysisItem.supplier.isnot(None))
            | (AnalysisItem.description.isnot(None))
        )
        .limit(5000)
        .all()
    )


def _history_for_product(product: Product, rows: list[AnalysisItem]) -> dict[str, Any]:
    product_text = product_search_text(product).lower()
    model = (product.model or "").lower()
    manufacturer = (product.manufacturer or "").lower()
    hits: list[AnalysisItem] = []
    for row in rows:
        text = " ".join(str(value or "") for value in [
            row.model,
            row.brand,
            row.supplier,
            row.description,
            row.caracteristicas_tecnicas,
        ]).lower()
        if model and model in text:
            hits.append(row)
            continue
        if manufacturer and manufacturer in text and any(term in text for term in product_text.split()[:8]):
            hits.append(row)

    unit_prices = [float(row.unit_value) for row in hits if row.unit_value is not None and float(row.unit_value) > 0]
    total_value = sum(float(row.total_value or 0) for row in hits)
    suppliers = sorted({row.supplier for row in hits if row.supplier})
    return {
        "occurrences": len(hits),
        "avg_unit_price": round(sum(unit_prices) / len(unit_prices), 2) if unit_prices else None,
        "min_unit_price": round(min(unit_prices), 2) if unit_prices else None,
        "max_unit_price": round(max(unit_prices), 2) if unit_prices else None,
        "estimated_total_value": round(total_value, 2) if total_value else None,
        "suppliers": suppliers[:5],
    }


def _risk_summary(counters: list[OwnCounter]) -> str:
    if not counters:
        return "Sem produto proprio para contrapor."
    best = counters[0]
    if best.score >= 70:
        return f"Boa resposta com {best.model}; revisar preco e documentacao."
    if best.score >= 45:
        return f"Resposta parcial com {best.model}; observar lacunas tecnicas."
    return "Risco alto: concorrente tem vantagem tecnica relevante."


def _serialize_product(product: Product) -> dict[str, Any]:
    return {
        "id": product.id,
        "model": product.model,
        "manufacturer": product.manufacturer,
        "category": product.category,
        "data": product.data or {},
    }


def _serialize_counter(counter: OwnCounter) -> dict[str, Any]:
    return {
        "product_id": counter.product_id,
        "model": counter.model,
        "manufacturer": counter.manufacturer,
        "category": counter.category,
        "score": counter.score,
        "advantages": counter.advantages,
        "disadvantages": counter.disadvantages,
        "ties": counter.ties,
        "key_edges": counter.key_edges,
        "vulnerabilities": counter.vulnerabilities,
    }
