"""Tenant-wide negotiation counts and actionable filters, independent of demand."""

from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, or_

from .models import Entity, ProcurementRequest, SupplierQuote
from .repository import now, scoped


def conditions(today):
    return {
        "expired": SupplierQuote.valid_until < today,
        "expiring": SupplierQuote.valid_until.between(today, today + timedelta(days=7)),
        "incomplete": or_(
            SupplierQuote.shipping.is_(None),
            SupplierQuote.taxes.is_(None),
            SupplierQuote.available_quantity.is_(None),
            SupplierQuote.minimum_quantity.is_(None),
            SupplierQuote.lead_time_days.is_(None),
        ),
    }


def filter_requests(db, tenant, query, state="all", supplier=None, search=None):
    quotes = scoped(db, SupplierQuote, tenant).filter(
        SupplierQuote.request_id == ProcurementRequest.id
    )
    if supplier:
        quotes = quotes.filter(SupplierQuote.supplier_id == supplier)
        query = query.filter(quotes.exists())
    if state in {"open", "selected"}:
        query = query.filter(ProcurementRequest.status == state)
    elif state == "awaiting_quotes":
        query = query.filter(~quotes.exists(), ProcurementRequest.status == "open")
    elif state in {"expired", "expiring", "incomplete"}:
        today = now().astimezone(ZoneInfo("America/Sao_Paulo")).date()
        query = query.filter(quotes.filter(conditions(today)[state]).exists())
    elif state != "all":
        raise ValueError("Filtro de negociação inválido.")
    if search:
        escaped = (
            search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        query = query.filter(
            or_(
                ProcurementRequest.id.ilike(f"%{escaped}%", escape="\\"),
                ProcurementRequest.snapshot["product"]
                .as_string()
                .ilike(f"%{escaped}%", escape="\\"),
            )
        )
    return query


def overview(db, tenant):
    today = now().astimezone(ZoneInfo("America/Sao_Paulo")).date()
    flags = conditions(today)
    quote_query = scoped(db, SupplierQuote, tenant)
    counts = quote_query.with_entities(
        func.count(SupplierQuote.id),
        *(
            func.coalesce(func.sum(case((condition, 1), else_=0)), 0)
            for condition in flags.values()
        ),
    ).one()
    requests = scoped(db, ProcurementRequest, tenant)
    waiting = filter_requests(db, tenant, requests, "awaiting_quotes").count()
    grouped = (
        quote_query.join(
            Entity,
            (Entity.id == SupplierQuote.supplier_id) & (Entity.tenant_id == tenant),
        )
        .with_entities(
            Entity.id,
            Entity.name,
            func.count(SupplierQuote.id).label("quotes"),
            func.count(func.distinct(SupplierQuote.request_id)).label("requests"),
            *(
                func.coalesce(func.sum(case((condition, 1), else_=0)), 0).label(key)
                for key, condition in flags.items()
            ),
        )
        .group_by(Entity.id, Entity.name)
        .order_by(func.count(SupplierQuote.id).desc(), Entity.name, Entity.id)
    )
    rows = grouped.limit(201).all()
    return {
        "requests": requests.count(),
        "open": requests.filter_by(status="open").count(),
        "selected": requests.filter_by(status="selected").count(),
        "awaiting_quotes": waiting,
        "quotes": counts[0],
        **dict(zip(flags, counts[1:])),
        "suppliers": [dict(row._mapping) for row in rows[:200]],
        "suppliers_truncated": len(rows) > 200,
        "as_of": today.isoformat(),
    }
