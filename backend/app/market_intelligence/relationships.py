"""Recorded product/demand and supplier/product relationships, never inferred fits."""

from collections import defaultdict


def relationship_report(facts, entities, relations):
    products = {row["id"]: row for row in entities if row["kind"] == "product"}
    suppliers = {row["id"]: row for row in entities if row["kind"] == "supplier"}
    groups = defaultdict(list)
    for row in facts:
        if row["kind"] == "demand":
            groups[(row["source"], row.get("product_id"))].append(row)
    # Current catalog items remain visible even if there is no recorded demand.
    for identity, product in products.items():
        if product.get("active", True):
            groups.setdefault(("crm", identity), [])
    demand_rows = []
    for (source, identity), rows in sorted(
        groups.items(), key=lambda pair: (pair[0][0], pair[0][1] or "")
    ):
        product = products.get(identity, {})
        known = [row for row in rows if row.get("total_value") is not None]
        covered = [row for row in known if row.get("coverage") == "covered"]
        units = {row.get("unit") for row in rows if row.get("quantity") is not None}
        quantities = [
            row["quantity"] for row in rows if row.get("quantity") is not None
        ]
        demand_rows.append(
            {
                "id": f"{source}:{identity or 'unresolved'}",
                "product_id": identity,
                "source": source,
                "product": product.get("name") or "Demanda sem produto identificado",
                "brand": product.get("brand"),
                "category": product.get("category"),
                "catalog_active": product.get("active", False),
                "items": len(rows),
                "covered_items": sum(row.get("coverage") == "covered" for row in rows),
                "value": float(sum(row["total_value"] for row in known))
                if known
                else None,
                "covered_value": float(sum(row["total_value"] for row in covered))
                if known
                else None,
                "value_sample": len(known),
                "quantity": float(sum(quantities))
                if quantities and len(units) == 1 and None not in units
                else None,
                "quantity_sample": len(quantities),
                "unit": next(iter(units)) if len(units) == 1 else None,
            }
        )
    links = []
    for row in relations:
        if not row.get("active", True):
            continue
        product, supplier = (
            products.get(row["product_id"]),
            suppliers.get(row["supplier_id"]),
        )
        if not product or not supplier:
            continue
        links.append(
            {
                "id": row.get("id")
                or f"{row['source']}:{product['id']}:{supplier['id']}",
                "source": row["source"],
                "product_id": product["id"],
                "product": product.get("name"),
                "supplier_id": supplier["id"],
                "supplier": supplier.get("name"),
                "brand": product.get("brand"),
                "category": product.get("category"),
                "cost": float(row["cost"]) if row.get("cost") is not None else None,
                "lead_time_days": row.get("lead_time_days"),
                "minimum_quantity": row.get("minimum_quantity"),
                "supplier_sku": row.get("supplier_sku"),
            }
        )
    return {"product_demand": demand_rows, "supplier_products": links}
