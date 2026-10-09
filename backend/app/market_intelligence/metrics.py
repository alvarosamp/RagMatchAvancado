"""Deterministic analytics; missing measures always remain unknown."""

from collections import defaultdict
from decimal import Decimal
from zoneinfo import ZoneInfo

from .domain import OUTCOMES, number, ratio, timestamp


def percentile(values, q):
    values = sorted(float(v) for v in values if v is not None)
    if not values:
        return None
    index = (len(values) - 1) * q
    lower = int(index)
    return values[lower] + (values[min(lower + 1, len(values) - 1)] - values[lower]) * (
        index - lower
    )


def summed(rows, key):
    values = [row.get(key) for row in rows if row.get(key) is not None]
    return float(sum(values)) if values else None


def group(rows, key):
    output = defaultdict(list)
    for row in rows:
        output[row.get(key) or "Não informado"].append(row)
    return output


def _brand_health(demand, matches, awards, entities, offers=None):
    demand_total = summed(demand, "total_value")
    awards_total = summed(awards, "total_value")
    product_brand = {
        e["id"]: e.get("brand") for e in entities if e["kind"] == "product"
    }
    considered = defaultdict(int)
    for match in matches:
        name = product_brand.get(match.get("product_id")) or "Não informado"
        if (match.get("attributes") or {}).get("rank", 999) <= 5:
            considered[name] += 1
    grouped, won = group(demand, "brand"), group(awards, "brand")
    offered = group(
        [
            {
                **row,
                "brand": row.get("brand") or product_brand.get(row.get("product_id")),
            }
            for row in offers or []
            if row.get("offered_price") is not None
        ],
        "brand",
    )
    offered_total = sum(len(rows) for rows in offered.values())
    all_names = set(grouped) | set(won) | set(considered) | set(offered)
    return [
        {
            "brand": name,
            "demanded_items": len(grouped.get(name, [])),
            "demanded_value": summed(grouped.get(name, []), "total_value"),
            "demand_share": ratio(
                number(summed(grouped.get(name, []), "total_value")),
                number(demand_total),
            ),
            "considered_candidates": considered.get(name, 0),
            "consideration_share": ratio(
                Decimal(considered.get(name, 0)), Decimal(sum(considered.values()))
            ),
            "offered_items": len(offered.get(name, [])),
            "offer_share": len(offered.get(name, [])) / offered_total
            if offered_total
            else None,
            "award_value": summed(won.get(name, []), "total_value"),
            "award_share": ratio(
                number(summed(won.get(name, []), "total_value")), number(awards_total)
            ),
        }
        for name in sorted(all_names)
    ]


def brand_health(demand, matches, awards, entities, offers=None):
    sources = {r["source"] for r in demand + matches + awards + (offers or [])}
    return [
        {**row, "source": source}
        for source in sorted(sources)
        for row in _brand_health(
            [r for r in demand if r["source"] == source],
            [r for r in matches if r["source"] == source],
            [r for r in awards if r["source"] == source],
            entities,
            [r for r in offers or [] if r["source"] == source],
        )
    ]


def supplier_metrics(purchases, awards, suppliers, relations, offers=None):
    # Our source supplier is on our offer, not the competitor's winning award.
    result_by_item = {
        (r.get("source"), r.get("item_id")): r
        for r in awards
        if r.get("outcome") in OUTCOMES
    }
    eligible_by_supplier = defaultdict(list)
    for offer in offers or []:
        result = result_by_item.get((offer.get("source"), offer.get("item_id")))
        if result and offer.get("supplier_id"):
            eligible_by_supplier[offer["supplier_id"]].append(result)
    purchase_groups = group(purchases, "supplier_id")
    total_spend = summed(purchases, "total_value")
    result = []
    for supplier in suppliers:
        rows = purchase_groups.get(supplier["id"], [])
        delivery_rows, leads, fill = [], [], []
        for row in rows:
            attrs = row.get("attributes") or {}
            received = timestamp(attrs.get("received_at"))
            promised = timestamp(attrs.get("promised_at"))
            qty_received = number(attrs.get("quantity_received"))
            qty = row.get("quantity")
            if received and promised and qty_received is not None and qty and qty > 0:
                delivery_rows.append(int(received <= promised and qty_received >= qty))
                fill.append(min(1, float(qty_received / qty)))
            if received and row.get("event_at") and received >= row["event_at"]:
                leads.append((received - row["event_at"]).total_seconds() / 86400)
        eligible = eligible_by_supplier.get(supplier["id"], [])
        spend = summed(rows, "total_value")
        result.append(
            {
                "id": supplier["id"],
                "supplier": supplier["name"],
                "tax_id": supplier.get("tax_id"),
                "purchase_lines": len(rows),
                "committed_purchase_value": spend,
                "spend_share": ratio(number(spend), number(total_spend)),
                "otif": sum(delivery_rows) / len(delivery_rows)
                if delivery_rows
                else None,
                "delivery_sample": len(delivery_rows),
                "fill_rate": sum(fill) / len(fill) if fill else None,
                "lead_time_p50": percentile(leads, 0.5),
                "lead_time_p90": percentile(leads, 0.9),
                "win_rate": sum(r["outcome"] == "won" for r in eligible) / len(eligible)
                if eligible
                else None,
                "results_sample": len(eligible),
                "products": len(
                    {
                        r["product_id"]
                        for r in relations
                        if r["supplier_id"] == supplier["id"] and r.get("active", True)
                    }
                ),
            }
        )
    return sorted(
        result, key=lambda row: row["committed_purchase_value"] or 0, reverse=True
    )


def benchmarks(prices, min_sample=5):
    # Product + unit + currency + region + price type. Category alone is unsafe.
    groups = defaultdict(list)
    excluded = 0
    for row in prices:
        if (
            not row.get("product_id")
            or not row.get("unit")
            or not row.get("unit_price")
        ):
            excluded += 1
            continue
        key = tuple(
            row.get(field)
            for field in ("product_id", "unit", "currency", "state", "price_type")
        )
        groups[key].append(row)
    output = []
    for key, rows in groups.items():
        values = [row["unit_price"] for row in rows]
        output.append(
            {
                "product_id": key[0],
                "unit": key[1],
                "currency": key[2],
                "state": key[3],
                "price_type": key[4],
                "sample": len(values),
                "sufficient": len(values) >= min_sample,
                "p25": percentile(values, 0.25),
                "median": percentile(values, 0.5),
                "p75": percentile(values, 0.75),
                "p90": percentile(values, 0.9),
            }
        )
    return output, excluded


def build_report(facts, entities, relations, freshness=None):
    kinds = group(facts, "kind")
    demand = kinds.get("demand", [])
    internal_demand = [r for r in demand if r["source"] == "crm"]
    awards = kinds.get("award", [])
    internal_results = [
        r for r in awards if r["source"] == "crm" and r.get("outcome") in OUTCOMES
    ]
    confirmed = [r for r in internal_demand if r.get("coverage") == "covered"]
    rejected = [r for r in internal_demand if r.get("coverage") == "rejected_selection"]
    unassessed = [r for r in internal_demand if r.get("coverage") == "unassessed"]
    gap_confirmed = [
        r for r in internal_demand if r.get("coverage") == "no_suitable_product"
    ]
    total_value = summed(internal_demand, "total_value")
    gaps = []
    for category, rows in group(internal_demand, "category").items():
        known = [r for r in rows if r.get("total_value") is not None]
        covered_rows = [r for r in rows if r.get("coverage") == "covered"]
        gaps.append(
            {
                "category": category,
                "items": len(rows),
                "value": summed(rows, "total_value"),
                "covered_items": len(covered_rows),
                "item_coverage": len(covered_rows) / len(rows),
                "demand_weighted_coverage": ratio(
                    number(summed(covered_rows, "total_value") or 0),
                    number(summed(rows, "total_value")),
                ),
                "confirmed_gap_value": summed(
                    [r for r in rows if r.get("coverage") == "no_suitable_product"],
                    "total_value",
                ),
                "rejected_selections": sum(
                    r.get("coverage") == "rejected_selection" for r in rows
                ),
                "pending_items": sum(
                    r.get("coverage") in {"unassessed", "pending_review"} for r in rows
                ),
                "value_sample": len(known),
            }
        )
    pricing = []
    for offer in kinds.get("offer", []):
        cost, offered, reference = (
            offer.get("cost"),
            offer.get("offered_price"),
            offer.get("reference_price"),
        )
        pricing.append(
            {
                "id": offer["id"],
                "item_id": offer.get("item_id"),
                "description": offer.get("description"),
                "product_id": offer.get("product_id"),
                "cost": float(cost) if cost is not None else None,
                "offered_price": float(offered) if offered is not None else None,
                "reference_price": float(reference) if reference is not None else None,
                "cost_to_reference": ratio(cost, reference),
                "bid_to_reference": ratio(offered, reference),
                "gross_margin": ratio(offered - cost, offered)
                if offered is not None and cost is not None
                else None,
                "alerts": [
                    name
                    for name, condition in [
                        (
                            "cost_above_reference",
                            cost is not None
                            and reference is not None
                            and cost > reference,
                        ),
                        (
                            "negative_gross_margin",
                            cost is not None and offered is not None and cost > offered,
                        ),
                    ]
                    if condition
                ],
            }
        )
    price_benchmarks, excluded = benchmarks(kinds.get("price", []))
    product_names = {e["id"]: e.get("name") for e in entities if e["kind"] == "product"}
    for row in price_benchmarks:
        row["product_name"] = product_names.get(row["product_id"])
    market = []
    pncp_awards = [r for r in awards if r["source"] == "pncp"]
    for category, rows in group(pncp_awards, "category").items():
        total = summed(rows, "total_value")
        supplier_values = [
            summed(group_rows, "total_value")
            for group_rows in group(rows, "supplier_id").values()
        ]
        market.append(
            {
                "category": category,
                "observed_award_value": total,
                "awarded_items": len(rows),
                "buyers": len(
                    {
                        (r.get("attributes") or {}).get("buyer_cnpj")
                        for r in rows
                        if (r.get("attributes") or {}).get("buyer_cnpj")
                    }
                ),
                "concentration": sum(
                    (v / total) ** 2 for v in supplier_values if v is not None
                )
                if total and total > 0
                else None,
            }
        )
    products = [e for e in entities if e["kind"] == "product" and e.get("active", True)]
    observed_suppliers = {
        row.get("supplier_id") for row in kinds.get("purchase", []) + relations
    }
    suppliers = [
        e
        for e in entities
        if e["kind"] == "supplier"
        and e.get("active", True)
        and (
            (e.get("attributes") or {}).get("supplier_role_verified") is not False
            or e["id"] in observed_suppliers
        )
    ]

    def completeness(rows, key):
        return {
            "present": sum(bool(r.get(key)) for r in rows),
            "total": len(rows),
            "rate": sum(bool(r.get(key)) for r in rows) / len(rows) if rows else None,
        }

    monthly = defaultdict(list)
    monthly_brands = defaultdict(list)
    for row in demand:
        month = (
            timestamp(row["event_at"])
            .astimezone(ZoneInfo("America/Sao_Paulo"))
            .strftime("%Y-%m")
        )
        monthly[(row["source"], month)].append(row)
    for row in demand + awards + kinds.get("match", []) + kinds.get("offer", []):
        month = (
            timestamp(row["event_at"])
            .astimezone(ZoneInfo("America/Sao_Paulo"))
            .strftime("%Y-%m")
        )
        monthly_brands[(row["source"], month)].append(row)
    timeline = [
        {
            "source": source,
            "month": month,
            "items": len(rows),
            "observed_value": summed(rows, "total_value"),
        }
        for (source, month), rows in sorted(monthly.items())
    ]
    brand_trends = []
    for (source, month), rows in sorted(monthly_brands.items()):
        bucket = group(rows, "kind")
        brand_trends.extend(
            {**row, "month": month}
            for row in brand_health(
                bucket.get("demand", []),
                bucket.get("match", []),
                bucket.get("award", []),
                entities,
                bucket.get("offer", []),
            )
        )
    return {
        "summary": {
            "internal_demand_items": len(internal_demand),
            "internal_notices": len({r.get("notice_id") for r in internal_demand}),
            "reference_value": total_value,
            "covered_items": len(confirmed),
            "rejected_selections": len(rejected),
            "unassessed_items": len(unassessed),
            "confirmed_gap_items": len(gap_confirmed),
            "demand_weighted_coverage": ratio(
                number(summed(confirmed, "total_value") or 0), number(total_value)
            ),
            "win_rate": sum(r.get("outcome") == "won" for r in internal_results)
            / len(internal_results)
            if internal_results
            else None,
            "win_rate_sample": len(internal_results),
            "won_value": summed(
                [r for r in internal_results if r.get("outcome") == "won"],
                "total_value",
            ),
        },
        "quality": {
            "products": len(products),
            "suppliers": len(suppliers),
            "product_brand": completeness(products, "brand"),
            "product_mpn": completeness(products, "mpn"),
            "product_gtin": completeness(products, "gtin"),
            "supplier_tax_id": completeness(suppliers, "tax_id"),
            "reference_price": completeness(internal_demand, "reference_price"),
            "unit": completeness(internal_demand, "unit"),
            "technical_labels": sum(
                bool((r.get("attributes") or {}).get("technical_verdict"))
                for r in internal_demand
            ),
            "excluded_benchmark_observations": excluded,
            "freshness": freshness or [],
        },
        "assortment": sorted(gaps, key=lambda r: r["value"] or 0, reverse=True),
        "pricing": pricing,
        "price_benchmarks": price_benchmarks,
        "brands": brand_health(
            demand, kinds.get("match", []), awards, entities, kinds.get("offer", [])
        ),
        "brand_trends": brand_trends,
        "suppliers": supplier_metrics(
            kinds.get("purchase", []),
            awards,
            suppliers,
            relations,
            kinds.get("offer", []),
        ),
        "market": market,
        "inventory": [
            {
                "product_id": r.get("product_id"),
                "quantity": float(r["quantity"])
                if r.get("quantity") is not None
                else None,
                "event_at": r["event_at"].isoformat(),
            }
            for r in kinds.get("inventory", [])
        ],
        "timeline": sorted(timeline, key=lambda r: r["month"]),
        "semantics": {
            "date_basis": "source_event_at; CRM=notice_created_at",
            "money": "BRL nominal; gross margin is estimated",
            "market": "observed PNCP only",
            "missing": "null",
            "price_benchmark": "same canonical product/unit/currency/region/type within selected period",
            "purchase_value": "committed order value; delivery KPIs require actual receipt evidence",
        },
    }
