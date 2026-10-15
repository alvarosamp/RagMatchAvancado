"""Documented stock, purchasing inquiries and comparable quotes; never orders."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from zoneinfo import ZoneInfo

from .domain import number, timestamp, unit
from .models import (
    Entity,
    Fact,
    ProcurementRequest,
    ProductSupplier,
    SupplierQuote,
    new_id,
)
from .repository import acquire_source_lock, fact, now, scoped, store_raw
from .service import as_dict, report
from .suppliers import canonical_id


def stock_timestamp(value):
    # Warehouse observations are UTC; SQLite drops the timezone on round-trip.
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return timestamp(value)


def entity(db, tenant, identity, kind):
    row = (
        scoped(db, Entity, tenant)
        .filter_by(id=identity, kind=kind, active=True)
        .one_or_none()
    )
    if not row:
        raise LookupError("Produto ou fornecedor ativo não encontrado nesta empresa.")
    return row


def valid_unit(value):
    normalized = unit(value)
    if not normalized or normalized in {"-", "N/A", "NC", "N/C", "UNKNOWN"}:
        raise ValueError("Informe uma unidade documentada.")
    return normalized


def stock_report(demand, stocks, as_of):
    latest = {}
    for stock in stocks:
        if not (stock.get("attributes") or {}).get("procurement_stock"):
            continue
        observed = stock_timestamp(stock["event_at"])
        if observed > as_of:
            continue
        key = (stock["product_id"], stock["unit"])
        if key not in latest or observed > stock_timestamp(latest[key]["event_at"]):
            latest[key] = stock
    output = []
    for row in demand:
        if not row["items"]:
            continue
        stock = latest.get((row["product_id"], row["unit"]))
        quantity_known = (
            row["quantity"] is not None
            and row["quantity_sample"] == row["items"]
            and bool(row["unit"])
        )
        available = None
        status = "missing_stock"
        if not row["product_id"]:
            status = "unresolved_product"
        elif not quantity_known:
            status = "incomplete_quantity_or_unit"
        elif stock:
            if as_of - stock_timestamp(stock["event_at"]) > timedelta(days=7):
                status = "stale_stock"
            else:
                physical = number(stock.get("quantity"))
                reserved = number(stock["attributes"].get("reserved"))
                if physical is None or reserved is None or reserved > physical:
                    status = "invalid_stock"
                else:
                    available = float(physical - reserved)
                    status = (
                        "needs_quote"
                        if row["quantity"] > available
                        else "stock_covers_observed"
                    )
        needed = (
            max(0, row["quantity"] - available)
            if quantity_known and available is not None
            else None
        )
        output.append(
            {
                **row,
                "stock_available": available,
                "stock_observed_at": stock["event_at"].isoformat() if stock else None,
                "quantity_to_quote": needed,
                "planning_status": status,
            }
        )
    return sorted(
        output,
        key=lambda row: (
            row["planning_status"] != "needs_quote",
            -(row["value"] or 0),
            row["product"],
        ),
    )


def save_stock(db, tenant, user_id, payload):
    product = entity(db, tenant, payload.product_id, "product")
    measurement = valid_unit(payload.unit)
    if payload.observed_at > now():
        raise ValueError("Saldo não pode ter data futura.")
    source_id = f"planning-stock:{product.id}:{measurement}"
    if not acquire_source_lock(db, tenant, source_id):
        raise RuntimeError("Outro saldo deste produto está sendo registrado.")
    previous = (
        scoped(db, Fact, tenant)
        .filter_by(source="manual", kind="inventory", source_id=source_id)
        .first()
    )
    if previous and stock_timestamp(previous.event_at) > payload.observed_at:
        raise ValueError(
            "Existe uma conferência de estoque mais recente; registre a correção com a data correspondente."
        )
    data = payload.model_dump(mode="json")
    store_raw(db, tenant, new_id(), "manual", "inventory", source_id, data)
    row = fact(
        db,
        tenant,
        "manual",
        "inventory",
        source_id,
        product_id=product.id,
        quantity=payload.quantity,
        unit=measurement,
        event_at=payload.observed_at,
        available_at=now(),
        category=product.category,
        brand=product.brand,
        description=product.name,
        attributes={
            "procurement_stock": True,
            "reserved": str(payload.reserved),
            "notes": payload.notes,
            "recorded_by": user_id,
        },
    )
    return row


def create_inquiry(db, tenant, user_id, payload):
    product = entity(db, tenant, payload.product_id, "product")
    measurement = valid_unit(payload.unit)
    today = now().astimezone(ZoneInfo("America/Sao_Paulo")).date()
    if payload.needed_by and payload.needed_by < today:
        raise ValueError("O prazo desejado não pode estar no passado.")
    data = report(db, tenant, **payload.filters.model_dump(exclude_none=True))
    origin = next(
        (
            row
            for row in data["product_demand"]
            if row["product_id"] == product.id
            and row["source"] == payload.filters.source
            and row["items"] > 0
        ),
        None,
    )
    if not origin:
        raise ValueError("Produto sem demanda registrada neste recorte.")
    if origin["unit"] and origin["unit"] != measurement:
        raise ValueError("A unidade deve corresponder à demanda documentada.")
    stocks = [
        as_dict(row)
        for row in scoped(db, Fact, tenant).filter_by(
            kind="inventory", source="manual", product_id=product.id, active=True
        )
    ]
    planning = stock_report([origin], stocks, now())[0]
    row = ProcurementRequest(
        tenant_id=tenant,
        product_id=product.id,
        quantity=payload.quantity,
        unit=measurement,
        needed_by=payload.needed_by,
        notes=payload.notes,
        user_id=user_id,
        status="open",
        snapshot={
            "product": product.name,
            "filters": payload.filters.model_dump(mode="json"),
            "observed": planning,
            "manual_quantity_confirmed": True,
            "generated_at": now().isoformat(),
        },
        selection_history=[],
    )
    db.add(row)
    db.flush()
    return row


def inquiry(db, tenant, identity):
    row = (
        scoped(db, ProcurementRequest, tenant)
        .filter_by(id=identity)
        .with_for_update()
        .one_or_none()
    )
    if row is None:
        raise LookupError("Solicitação de cotação não encontrada nesta empresa.")
    return row


def add_quote(db, tenant, user_id, identity, payload):
    request = inquiry(db, tenant, identity)
    entity(db, tenant, request.product_id, "product")
    supplier_id = canonical_id(db, tenant, payload.supplier_id)
    supplier = entity(db, tenant, supplier_id, "supplier")
    link = (
        scoped(db, ProductSupplier, tenant)
        .filter_by(product_id=request.product_id, supplier_id=supplier.id, active=True)
        .first()
    )
    if link is None:
        raise ValueError("Fornecedor sem vínculo documentado com este produto.")
    if payload.valid_until < now().astimezone(ZoneInfo("America/Sao_Paulo")).date():
        raise ValueError("Registre uma cotação ainda válida.")
    row = SupplierQuote(
        tenant_id=tenant,
        request_id=request.id,
        user_id=user_id,
        **payload.model_dump(exclude={"supplier_id"}),
        supplier_id=supplier.id,
        evidence={
            "supplier_name_at_quote": supplier.name,
            "currency": "BRL",
            "quantity": str(request.quantity),
            "unit": request.unit,
        },
    )
    db.add(row)
    db.flush()
    return row


def compare_quote(request, quote, as_of):
    qty = Decimal(str(request["quantity"]))
    price = Decimal(str(quote["unit_price"]))
    with localcontext() as context:
        context.prec = 64
        subtotal = qty * price
        total = (
            subtotal + Decimal(str(quote["shipping"])) + Decimal(str(quote["taxes"]))
            if quote["shipping"] is not None and quote["taxes"] is not None
            else None
        )
    flags = []
    today = as_of.astimezone(ZoneInfo("America/Sao_Paulo")).date()
    if quote["valid_until"] < today:
        flags.append("expired")
    if total is None:
        flags.append("incomplete_total")
    if quote["available_quantity"] is None:
        flags.append("unknown_availability")
    elif quote["available_quantity"] < qty:
        flags.append("insufficient_availability")
    if quote["minimum_quantity"] is None:
        flags.append("unknown_minimum")
    elif quote["minimum_quantity"] > qty:
        flags.append("below_minimum")
    arrival = None
    if quote["lead_time_days"] is None:
        flags.append("unknown_lead_time")
    else:
        arrival = today + timedelta(days=quote["lead_time_days"])
        if request["needed_by"] and arrival > request["needed_by"]:
            flags.append("after_deadline")
    return {
        **quote,
        "subtotal": str(subtotal),
        "total": str(total) if total is not None else None,
        "currency": "BRL",
        "flags": flags,
        "comparable": not flags,
        "arrival_if_ordered_today": arrival.isoformat() if arrival else None,
    }


def compare_proposals(proposals):
    candidates = [quote for quote in proposals if quote["comparable"]]
    cheapest = min((Decimal(quote["total"]) for quote in candidates), default=None)
    result = []
    for quote in proposals:
        with localcontext() as context:
            context.prec = 64
            difference = (
                Decimal(quote["total"]) - cheapest if quote["comparable"] else None
            )
        result.append(
            {
                **quote,
                "lowest_complete_total": quote["comparable"]
                and Decimal(quote["total"]) == cheapest,
                "difference_to_lowest_complete": str(difference)
                if difference is not None
                else None,
            }
        )
    return result


def select_quote(db, tenant, user_id, identity, payload):
    request = inquiry(db, tenant, identity)
    quote = (
        scoped(db, SupplierQuote, tenant)
        .filter_by(id=payload.quote_id, request_id=request.id)
        .one_or_none()
    )
    if quote is None:
        raise LookupError("Cotação não encontrada nesta solicitação.")
    comparison = compare_quote(as_dict(request), as_dict(quote), now())
    if "expired" in comparison["flags"]:
        raise ValueError("Cotação vencida: registre uma nova proposta.")
    request.selection_history = [
        *(request.selection_history or []),
        {
            "quote_id": quote.id,
            "reason": payload.reason,
            "user_id": user_id,
            "selected_at": now().isoformat(),
            "conditions_at_selection": comparison["flags"],
            "total_at_selection": comparison["total"],
        },
    ]
    request.status = "selected"
    return request


def workspace(db, tenant, filters, offset=0, state="all", supplier=None, search=None):
    from .negotiations import filter_requests, overview

    selected_filters = {**filters, "source": filters.get("source") or "crm"}
    data = report(db, tenant, **selected_filters)
    stocks = [
        as_dict(row)
        for row in scoped(db, Fact, tenant).filter_by(
            kind="inventory", source="manual", active=True
        )
    ]
    planning = stock_report(data["product_demand"], stocks, now())
    query = filter_requests(
        db, tenant, scoped(db, ProcurementRequest, tenant), state, supplier, search
    )
    requests = (
        query.order_by(
            ProcurementRequest.created_at.desc(), ProcurementRequest.id.desc()
        )
        .offset(offset)
        .limit(25)
        .all()
    )
    quotes = defaultdict(list)
    ids = [row.id for row in requests]
    quote_rows = (
        scoped(db, SupplierQuote, tenant)
        .filter(SupplierQuote.request_id.in_(ids))
        .order_by(SupplierQuote.created_at.desc(), SupplierQuote.id.desc())
        .limit(2001)
        .all()
        if ids
        else []
    )
    if len(quote_rows) > 2000:
        raise OverflowError("Histórico de cotações excede o limite deste recorte.")
    names = {
        row.id: row.name
        for row in scoped(db, Entity, tenant).filter_by(kind="supplier")
    }
    for quote in quote_rows:
        quotes[quote.request_id].append(
            {**as_dict(quote), "supplier": names.get(quote.supplier_id)}
        )
    output = []
    for request in requests:
        row = as_dict(request)
        proposals = [compare_quote(row, quote, now()) for quote in quotes[request.id]]
        row["quotes"] = compare_proposals(proposals)
        row["product"] = request.snapshot.get("product")
        output.append(row)
    quote_links = []
    for link in scoped(db, ProductSupplier, tenant).filter(
        ProductSupplier.product_id.in_([row.product_id for row in requests]),
        ProductSupplier.active.is_(True),
    ):
        if link.supplier_id in names:
            quote_links.append(
                {
                    "product_id": link.product_id,
                    "supplier_id": link.supplier_id,
                    "supplier": names[link.supplier_id],
                }
            )
    return {
        "planning": planning,
        "negotiations": overview(db, tenant),
        "requests": output,
        "request_total": query.count(),
        "offset": offset,
        "supplier_products": quote_links,
        "source": selected_filters["source"],
        "generated_at": now().isoformat(),
        "semantics": "Saldo físico manual menos reserva; atualização de até sete dias. Cotação não é compra. Demanda observada não é compromisso.",
    }
