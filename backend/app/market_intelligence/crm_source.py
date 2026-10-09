"""Complete CRM reconciliation, including edits and removed records."""

from sqlalchemy.inspection import inspect

import app.auth.models
import app.jobs.models  # noqa: F401 -- Tenant/User reference Job without HTTP startup
from app.crm.models import (
    CrmCatalogProduct,
    CrmNotice,
    CrmNoticeItemResult,
    CrmNoticeProduct,
    CrmNoticeProductMatch,
)

from .domain import coverage, normalize, number, technical_attributes, timestamp, unit
from .models import Entity, Fact, Feedback, Identity, ProductSupplier
from .repository import canonical_brand, fact, now, resolve, scoped, store_raw, upsert


def serialize(row):
    return {
        column.key: getattr(row, column.key)
        for column in inspect(row).mapper.column_attrs
        if column.key != "embedding"
    }


def reconcile_crm(db, tenant_id, run_id):
    started = now()
    counts = {"products": 0, "items": 0, "raw_versions": 0, "matches": 0}
    # One transaction: if extraction fails, prior current facts remain available.
    scoped(db, Fact, tenant_id).filter_by(source="crm").update(
        {Fact.active: False}, synchronize_session=False
    )
    scoped(db, ProductSupplier, tenant_id).filter_by(source="crm").update(
        {ProductSupplier.active: False}, synchronize_session=False
    )
    for product in (
        db.query(CrmCatalogProduct).filter_by(tenant_id=tenant_id).yield_per(500)
    ):
        raw = serialize(product)
        counts["raw_versions"] += store_raw(
            db,
            tenant_id,
            run_id,
            "crm",
            "product",
            product.id,
            raw,
            timestamp(product.updated_at),
        )
        canonical = resolve(
            db,
            tenant_id,
            "crm",
            "product",
            product.id,
            {
                "name": product.name,
                "brand": product.brand,
                "mpn": product.manufacturer_part_number,
                "sku": product.sku,
                "gtin": product.gtin,
                "category": product.category,
                "crm_product_id": product.id,
                "active": product.is_active,
                "embedding_present": product.embedding is not None,
                "unit": product.unit,
                "specification": product.specification,
                "technical_attributes": technical_attributes(
                    product.specification or product.description
                ),
            },
        )
        if product.brand:
            resolve(
                db,
                tenant_id,
                "crm",
                "brand",
                normalize(product.brand),
                {"name": canonical_brand(db, tenant_id, product.brand)},
            )
        if product.category:
            resolve(
                db,
                tenant_id,
                "crm",
                "category",
                normalize(product.category),
                {"name": product.category},
            )
        if product.supplier_name and canonical:
            supplier = resolve(
                db,
                tenant_id,
                "crm",
                "supplier",
                normalize(product.supplier_name),
                {"name": product.supplier_name, "tax_id": product.supplier_tax_id},
            )
            if supplier:
                upsert(
                    db,
                    ProductSupplier,
                    tenant_id,
                    {
                        "product_id": canonical.id,
                        "supplier_id": supplier.id,
                        "source": "crm",
                    },
                    {
                        "cost": number(product.cost, positive=True),
                        "active": product.is_active,
                    },
                )
        counts["products"] += 1
    existing = {
        link.source_id: link.entity_id
        for link in scoped(db, Identity, tenant_id)
        .filter_by(source="crm", kind="product")
        .all()
    }
    product_brands = {
        row.id: row.brand
        for row in scoped(db, Entity, tenant_id).filter_by(kind="product")
    }
    candidate_items = {
        row[0]
        for row in db.query(CrmNoticeProductMatch.notice_product_id)
        .filter_by(tenant_id=tenant_id)
        .distinct()
    }
    suppliers_by_product = {}
    for relation in scoped(db, ProductSupplier, tenant_id).filter_by(
        source="crm", active=True
    ):
        suppliers_by_product.setdefault(relation.product_id, []).append(
            relation.supplier_id
        )
    # Explicit tenant predicates on every joined table, in addition to RLS.
    items = (
        db.query(CrmNoticeProduct, CrmNotice, CrmNoticeItemResult)
        .join(
            CrmNotice,
            (CrmNotice.id == CrmNoticeProduct.notice_id)
            & (CrmNotice.tenant_id == tenant_id),
        )
        .outerjoin(
            CrmNoticeItemResult,
            (CrmNoticeItemResult.notice_product_id == CrmNoticeProduct.id)
            & (CrmNoticeItemResult.tenant_id == tenant_id),
        )
        .filter(CrmNoticeProduct.tenant_id == tenant_id)
        .yield_per(500)
    )
    item_contexts = {}
    for item, notice, result in items:
        raw = {
            "item": serialize(item),
            "notice": serialize(notice),
            "result": serialize(result) if result else None,
        }
        counts["raw_versions"] += store_raw(
            db, tenant_id, run_id, "crm", "demand", item.id, raw
        )
        quantity, reference = (
            number(item.quantity),
            number(item.reference_price, positive=True),
        )
        total = number(item.reference_total_price, positive=True)
        if total is None and quantity is not None and reference is not None:
            total = quantity * reference
        if reference is None and total is not None and quantity and quantity > 0:
            reference = total / quantity
        event_at = timestamp(notice.created_at, started)
        outcome = (
            notice.outcome.value if hasattr(notice.outcome, "value") else notice.outcome
        )
        candidate_exists = item.id in candidate_items
        item_coverage = coverage(
            item.match_review_verdict, bool(item.catalog_product_id), candidate_exists
        )
        payload = item.raw_payload if isinstance(item.raw_payload, dict) else {}
        # Requested brand must come from request evidence, never selected catalogue.
        demand_brand = payload.get("marca") or payload.get("brand")
        if isinstance(demand_brand, (dict, list)):
            demand_brand = None
        common = {
            "notice_id": notice.id,
            "item_id": item.id,
            "product_id": existing.get(item.catalog_product_id),
            "category": item.category,
            "state": notice.state,
            "unit": unit(item.unit),
            "quantity": quantity,
            "event_at": event_at,
            "available_at": started,
            "active": outcome != "not_pursued",
        }
        attrs = {
            "technical_verdict": item.match_review_verdict,
            "selected_for_dispute": item.selected_for_dispute,
            "source_product_id": item.catalog_product_id,
            "technical_attributes": technical_attributes(
                item.technical_characteristics or item.description
            ),
            "split_group": notice.id,
            "event_date_basis": "notice_created_at",
            "reviewed_at": timestamp(item.match_reviewed_at).isoformat()
            if item.match_reviewed_at
            else None,
        }
        item_contexts[item.id] = {**common, "description": item.description}
        supplier_options = suppliers_by_product.get(common["product_id"], [])
        offer_supplier_id = supplier_options[0] if len(supplier_options) == 1 else None
        fact(
            db,
            tenant_id,
            "crm",
            "demand",
            item.id,
            **common,
            description=item.description,
            brand=canonical_brand(db, tenant_id, demand_brand),
            reference_price=reference,
            total_value=total,
            coverage=item_coverage,
            outcome=outcome,
            attributes=attrs,
        )
        fact(
            db,
            tenant_id,
            "crm",
            "offer",
            item.id,
            **common,
            supplier_id=offer_supplier_id,
            brand=product_brands.get(common["product_id"]),
            description=item.description,
            reference_price=reference,
            cost=number(item.cost, positive=True),
            offered_price=number(item.unit_price, positive=True),
            outcome=outcome,
            attributes=attrs,
        )
        for price_type, value in [
            ("reference_price", reference),
            ("supplier_cost", number(item.cost, positive=True)),
            ("minimum_viable_price", number(item.minimum_unit_price, positive=True)),
            ("offered_price", number(item.unit_price, positive=True)),
        ]:
            if value is not None:
                fact(
                    db,
                    tenant_id,
                    "crm",
                    "price",
                    f"{item.id}:{price_type}",
                    **common,
                    unit_price=value,
                    price_type=price_type,
                    description=item.description,
                    attributes=attrs,
                )
        if result:
            winner_type = (
                result.winner_type.value
                if hasattr(result.winner_type, "value")
                else result.winner_type
            )
            winning_outcome = {"us": "won", "competitor": "lost"}.get(
                winner_type, winner_type
            )
            award_common = {
                **common,
                "event_at": timestamp(result.updated_at, started),
                "quantity": number(result.winning_quantity),
            }
            winning = number(result.winning_price, positive=True)
            supplier = (
                resolve(
                    db,
                    tenant_id,
                    "crm",
                    "supplier",
                    f"competitor:{normalize(result.competitor_name)}",
                    {
                        "name": result.competitor_name,
                        "tax_id": result.competitor_tax_id,
                    },
                )
                if result.competitor_name
                else None
            )
            fact(
                db,
                tenant_id,
                "crm",
                "award",
                result.id,
                **award_common,
                supplier_id=supplier.id if supplier else None,
                winning_price=winning,
                total_value=winning * award_common["quantity"]
                if winning is not None and award_common["quantity"] is not None
                else None,
                outcome=winning_outcome,
                brand=canonical_brand(db, tenant_id, result.winner_brand),
                attributes={
                    **attrs,
                    "source_supplier_id": f"competitor:{normalize(result.competitor_name)}",
                    "winner_type": winner_type,
                },
            )
            if winning is not None and winner_type in {"us", "competitor"}:
                fact(
                    db,
                    tenant_id,
                    "crm",
                    "price",
                    f"{item.id}:winning_price",
                    **award_common,
                    unit_price=winning,
                    price_type="winning_price",
                    brand=canonical_brand(db, tenant_id, result.winner_brand),
                    attributes=attrs,
                )
        counts["items"] += 1
    for match in (
        db.query(CrmNoticeProductMatch).filter_by(tenant_id=tenant_id).yield_per(500)
    ):
        context = item_contexts.get(match.notice_product_id)
        if not context:
            continue
        counts["raw_versions"] += store_raw(
            db,
            tenant_id,
            run_id,
            "crm",
            "match",
            match.id,
            serialize(match),
            timestamp(match.updated_at),
        )
        fact(
            db,
            tenant_id,
            "crm",
            "match",
            match.id,
            notice_id=match.notice_id,
            item_id=match.notice_product_id,
            product_id=existing.get(match.catalog_product_id),
            event_at=context["event_at"],
            category=context["category"],
            state=context["state"],
            description=context["description"],
            active=context["active"],
            attributes={
                "rank": match.match_rank,
                "lexical_score": match.lexical_score,
                "semantic_score": match.semantic_score,
                "score": match.overall_score,
                "status": getattr(match.status, "value", match.status),
                "conflicts": match.conflicts,
                "source_product_id": match.catalog_product_id,
            },
        )
        counts["matches"] += 1
    # Commercial feedback is append-only and reapplied after reconciliation.
    # Operators can change their decision later; latest event wins per action.
    for feedback in scoped(db, Feedback, tenant_id).order_by(
        Feedback.available_at, Feedback.id
    ):
        demand = (
            scoped(db, Fact, tenant_id)
            .filter_by(
                source="crm", kind="demand", item_id=feedback.item_id, active=True
            )
            .first()
        )
        if not demand:
            continue
        offer = (
            scoped(db, Fact, tenant_id)
            .filter_by(
                source="crm", kind="offer", item_id=feedback.item_id, active=True
            )
            .first()
        )
        if feedback.action == "confirmed_gap":
            demand.coverage = "no_suitable_product"
        elif feedback.action == "technical_review":
            verdict = feedback.payload.get("verdict")
            demand.attributes = {**demand.attributes, "technical_verdict": verdict}
            demand.coverage = coverage(verdict, bool(demand.product_id))
        elif feedback.action == "supplier_selected" and offer:
            from .suppliers import canonical_id

            offer.supplier_id = canonical_id(
                db, tenant_id, feedback.payload.get("supplier_id")
            )
        elif feedback.action == "price_adjusted" and offer:
            offer.offered_price = number(feedback.payload.get("price"), positive=True)
    # Missing catalogue identities are deactivated; history is retained.
    seen = db.query(CrmCatalogProduct.id).filter_by(tenant_id=tenant_id)
    scoped(db, Entity, tenant_id).filter(
        Entity.kind == "product",
        Entity.crm_product_id.isnot(None),
        Entity.crm_product_id.notin_(seen),
    ).update({Entity.active: False}, synchronize_session=False)
    from .suppliers import normalize_suppliers

    counts["supplier_normalization"] = normalize_suppliers(db, tenant_id)
    return counts
