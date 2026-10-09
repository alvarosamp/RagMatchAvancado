import os
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, inspect, text

from .metrics import build_report
from .models import Entity, Fact, ProductSupplier, SyncRun
from .repository import scoped


def as_dict(row):
    return {
        attr.key: getattr(row, attr.key) for attr in inspect(row).mapper.column_attrs
    }


def local_boundary(value, next_day=False):
    day = value + timedelta(days=1) if next_day else value
    return datetime.combine(day, time.min, ZoneInfo("America/Sao_Paulo")).astimezone(
        timezone.utc
    )


def fact_query(
    db,
    tenant_id,
    date_from=None,
    date_to=None,
    category=None,
    state=None,
    brand=None,
    supplier_id=None,
    product_id=None,
    price_type=None,
    unresolved_product=False,
    source=None,
    search=None,
):
    if date_from and date_to and date_from > date_to:
        raise ValueError("Período invertido.")
    query = scoped(db, Fact, tenant_id).filter(Fact.active.is_(True))
    if date_from:
        query = query.filter(Fact.event_at >= local_boundary(date_from))
    if date_to:
        query = query.filter(Fact.event_at < local_boundary(date_to, next_day=True))
    for field, value in [
        (Fact.category, category),
        (Fact.state, state),
        (Fact.brand, brand),
        (Fact.supplier_id, supplier_id),
        (Fact.product_id, product_id),
        (Fact.price_type, price_type),
        (Fact.source, source),
    ]:
        if value:
            query = query.filter(field == value)
    if search:
        # Escaped contains: search is not a user supplied SQL wildcard.
        query = query.filter(Fact.description.contains(search, autoescape=True))
    if unresolved_product:
        query = query.filter(Fact.product_id.is_(None))
    return query


def report(db, tenant_id, **filters):
    limit = int(os.getenv("MARKET_REPORT_MAX_FACTS", "50000"))
    rows = (
        fact_query(db, tenant_id, **filters)
        .order_by(Fact.event_at, Fact.id)
        .limit(limit + 1)
        .all()
    )
    if len(rows) > limit:
        raise OverflowError(
            "Recorte excede o limite de análise. Reduza o período ou selecione uma categoria."
        )
    entities = [as_dict(row) for row in scoped(db, Entity, tenant_id).all()]
    relations = [
        as_dict(row)
        for row in scoped(db, ProductSupplier, tenant_id).filter_by(active=True).all()
    ]
    ranked = (
        scoped(db, SyncRun, tenant_id)
        .filter_by(status="completed")
        .with_entities(
            SyncRun.id,
            func.row_number()
            .over(
                partition_by=SyncRun.source,
                order_by=(SyncRun.finished_at.desc(), SyncRun.id.desc()),
            )
            .label("rank"),
        )
        .subquery()
    )
    runs = (
        scoped(db, SyncRun, tenant_id)
        .join(ranked, SyncRun.id == ranked.c.id)
        .filter(ranked.c.rank == 1)
        .order_by(SyncRun.finished_at.desc())
        .all()
    )
    latest = {}
    for run in runs:
        latest.setdefault(
            run.source,
            {
                "source": run.source,
                "finished_at": run.finished_at.isoformat(),
                "counts": run.counts,
            },
        )
    output = build_report(
        [as_dict(row) for row in rows], entities, relations, list(latest.values())
    )
    from .relationships import relationship_report

    related = relationship_report([as_dict(row) for row in rows], entities, relations)
    # Catalog relationships have no event timestamp: their scope is explicitly current.
    for key in ("product_demand", "supplier_products"):
        related[key] = [
            row
            for row in related[key]
            if (
                not filters.get("category")
                or row.get("category") == filters["category"]
                or (key == "product_demand" and row["items"] > 0)
            )
            and (
                not filters.get("brand")
                or row.get("brand") == filters["brand"]
                or (key == "product_demand" and row["items"] > 0)
            )
            and (
                not filters.get("product_id")
                or row.get("product_id") == filters["product_id"]
            )
            and (
                not filters.get("supplier_id")
                or key == "product_demand"
                or row.get("supplier_id") == filters["supplier_id"]
            )
        ]
    output.update(related)
    output["generated_at"] = datetime.now(timezone.utc).isoformat()
    output["filters"] = {
        k: v.isoformat() if isinstance(v, date) else v for k, v in filters.items()
    }
    output["facts_sample"] = len(rows)
    if filters.get("supplier_id"):
        output["suppliers"] = [
            row for row in output["suppliers"] if row["id"] == filters["supplier_id"]
        ]
    series = os.getenv("MARKET_DEFLATOR_SERIES")
    if series:
        from .deflation import deflated_benchmarks

        indices = [
            as_dict(row)
            for row in scoped(db, Fact, tenant_id).filter_by(
                kind="index", source="ibge", active=True
            )
        ]
        output["real_prices"] = deflated_benchmarks(
            [as_dict(row) for row in rows if row.kind == "price"],
            indices,
            series,
            os.getenv("MARKET_DEFLATOR_BASE_MONTH"),
        )
    else:
        output["real_prices"] = {
            "status": "not_configured",
            "rows": [],
            "reason": "Selecione um índice adequado à categoria antes de deflacionar.",
        }
    names = {row["id"]: row.get("name") for row in entities}
    output["real_price_benchmarks"] = [
        {
            **row,
            "product_name": names.get(row["product_id"]),
            "base_month": output["real_prices"].get("base_month"),
            "index_series": series,
        }
        for row in output["real_prices"]["rows"]
    ]
    output["catalog_scope"] = "tenant-wide; demand/results follow selected filters"
    return output


def diagnostic(db, tenant_id):
    from app.crm.models import CrmCatalogProduct, CrmNotice, CrmNoticeProduct

    product = (
        db.query(
            func.count(CrmCatalogProduct.id),
            func.count(CrmCatalogProduct.sku),
            func.count(CrmCatalogProduct.brand),
            func.count(CrmCatalogProduct.manufacturer_part_number),
        )
        .filter(CrmCatalogProduct.tenant_id == tenant_id)
        .one()
    )
    item = (
        db.query(
            func.count(CrmNoticeProduct.id),
            func.count(CrmNoticeProduct.catalog_product_id),
            func.count(CrmNoticeProduct.match_review_verdict),
            func.count(CrmNoticeProduct.reference_price),
            func.count(CrmNoticeProduct.unit),
        )
        .filter(CrmNoticeProduct.tenant_id == tenant_id)
        .one()
    )
    dates = (
        db.query(func.min(CrmNotice.created_at), func.max(CrmNotice.created_at))
        .filter(CrmNotice.tenant_id == tenant_id)
        .one()
    )
    ready = db.execute(text("SELECT to_regclass('core.facts') IS NOT NULL")).scalar()
    return {
        "warehouse_ready": bool(ready),
        "environment": "connected database; production not assumed",
        "products": {
            "total": product[0],
            "sku": product[1],
            "brand": product[2],
            "mpn": product[3],
        },
        "items": {
            "total": item[0],
            "linked": item[1],
            "technical_labels": item[2],
            "reference_price": item[3],
            "unit": item[4],
        },
        "first_notice": dates[0].isoformat() if dates[0] else None,
        "last_notice": dates[1].isoformat() if dates[1] else None,
        "next_action": "sync_crm" if ready else "apply_20261009_01_migration",
    }
