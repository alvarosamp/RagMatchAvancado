import csv
import io
import json
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.db.session import get_db, set_tenant_context
from app.market_intelligence.adapters import normalized_record
from app.market_intelligence.connectors import verify_bling_signature
from app.market_intelligence.domain import normalize
from app.market_intelligence.models import (
    BrandAlias,
    Entity,
    Fact,
    Feedback,
    ModelRun,
    Review,
    SupplierPresentationLink,
    SyncRun,
)
from app.market_intelligence.procurement_schemas import (
    InquiryInput,
    QuoteInput,
    SelectionInput,
    StockInput,
)
from app.market_intelligence.repository import (
    acquire_source_lock,
    now,
    review_identity,
    scoped,
    store_raw,
)
from app.market_intelligence.schemas import (
    AliasRequest,
    FeedbackRequest,
    ImportRequest,
    ReviewRequest,
    SyncRequest,
)
from app.market_intelligence.service import as_dict, diagnostic, fact_query, report
from app.market_intelligence.sharing import ShareInput


def require_market_enabled():
    from app.market_intelligence.config import enabled

    if not enabled():
        raise HTTPException(
            503,
            "Inteligência comercial desativada neste ambiente. O histórico foi preservado.",
        )


router = APIRouter(
    prefix="/crm/market-intelligence",
    tags=["CRM intelligence"],
    dependencies=[Depends(require_market_enabled)],
)
Reader = Annotated[User, Depends(get_current_user)]
Writer = Annotated[User, Depends(require_role("admin", "editor"))]
Admin = Annotated[User, Depends(require_role("admin"))]
Database = Annotated[Session, Depends(get_db)]


def filters(
    date_from: date | None = None,
    date_to: date | None = None,
    category: str | None = Query(None, max_length=160),
    state: str | None = Query(None, max_length=2),
    brand: str | None = Query(None, max_length=160),
    supplier_id: str | None = Query(None, max_length=36),
    product_id: str | None = Query(None, max_length=36),
    price_type: str | None = Query(None, max_length=30),
    unresolved_product: bool = False,
    source: str | None = Query(None, pattern="^(crm|bling|pncp|manual|ibge)$"),
    search: str | None = Query(None, max_length=200),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "Período invertido.")
    return {
        "date_from": date_from,
        "date_to": date_to,
        "category": category,
        "state": state.upper() if state else None,
        "brand": brand,
        "supplier_id": supplier_id,
        "product_id": product_id,
        "price_type": price_type,
        "unresolved_product": unresolved_product,
        "source": source,
        "search": search,
    }


Filters = Annotated[dict, Depends(filters)]


@router.post("/supplier-presentations", status_code=201)
def create_supplier_presentation(payload: "ShareInput", user: Writer, db: Database):
    from app.market_intelligence.sharing import create_share

    return create_share(db, user, payload)


@router.get("/supplier-presentations")
def list_supplier_presentations(user: Writer, db: Database):
    rows = (
        scoped(db, SupplierPresentationLink, user.tenant_id)
        .order_by(SupplierPresentationLink.created_at.desc())
        .limit(100)
        .all()
    )
    suppliers = {
        row.id: row.name
        for row in scoped(db, Entity, user.tenant_id).filter_by(kind="supplier").all()
    }
    return [
        {
            "id": row.id,
            "supplier": suppliers.get(row.supplier_id, "Fornecedor indisponível"),
            "expires_at": row.expires_at,
            "revoked_at": row.revoked_at,
        }
        for row in rows
    ]


@router.delete("/supplier-presentations/{link_id}", status_code=204)
def revoke_supplier_presentation(link_id: str, user: Writer, db: Database):
    row = (
        scoped(db, SupplierPresentationLink, user.tenant_id)
        .filter_by(id=link_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "Link não encontrado nesta empresa.")
    row.revoked_at = now()
    db.commit()
    return Response(status_code=204)


@router.get("/shared-presentation")
def get_shared_presentation(
    db: Database,
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
):
    from app.market_intelligence.sharing import shared_payload

    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Link de apresentação necessário.")
    return shared_payload(db, authorization[7:])


@router.get("/diagnostic")
def get_diagnostic(user: Reader, db: Database):
    return diagnostic(db, user.tenant_id)


@router.get("/capabilities")
def get_capabilities(user: Reader):
    from app.market_intelligence.config import bling_enabled

    return {
        "sources": {
            "crm": "available",
            "manual": "available",
            "pncp": "available",
            "ibge": "available",
            "bling": "configured" if bling_enabled() else "planned",
        }
    }


@router.get("/report")
def get_report(user: Reader, db: Database, slice: Filters):
    try:
        return report(db, user.tenant_id, **slice)
    except OverflowError as error:
        raise HTTPException(413, str(error)) from error


@router.get("/export")
def export_report(
    user: Reader,
    db: Database,
    slice: Filters,
    section: str = Query(
        "assortment",
        pattern="^(assortment|pricing|price_benchmarks|real_price_benchmarks|brands|brand_trends|suppliers|supplier_products|product_demand|market|timeline)$",
    ),
):
    payload = get_report(user, db, slice)
    rows = payload[section]
    output = io.StringIO()

    def cell(value):
        value = (
            json.dumps(value, ensure_ascii=False)
            if isinstance(value, (dict, list))
            else ""
            if value is None
            else str(value)
        )
        # Prevent executable spreadsheet formulas from untrusted source names.
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value

    writer = csv.writer(output)
    keys = list(rows[0]) if rows else ["no_data"]
    writer.writerow(keys)
    for row in rows:
        writer.writerow([cell(row.get(key)) for key in keys])
    return Response(
        "\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="market-{section}.csv"'},
    )


def procurement_call(function, *args):
    try:
        return function(*args)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(409, str(error)) from error
    except OverflowError as error:
        raise HTTPException(413, str(error)) from error


@router.get("/procurement")
def get_procurement(
    user: Reader,
    db: Database,
    slice: Filters,
    offset: int = Query(0, ge=0, le=100000),
    negotiation_state: str = Query(
        "all",
        pattern="^(all|open|selected|awaiting_quotes|expired|expiring|incomplete)$",
    ),
    negotiation_supplier: str | None = Query(None, min_length=1, max_length=36),
    negotiation_search: str | None = Query(None, max_length=200),
):
    from app.market_intelligence.procurement import workspace

    return procurement_call(
        workspace,
        db,
        user.tenant_id,
        slice,
        offset,
        negotiation_state,
        negotiation_supplier,
        negotiation_search,
    )


@router.post("/procurement/stock")
def record_procurement_stock(payload: StockInput, user: Writer, db: Database):
    from app.market_intelligence.procurement import save_stock

    row = procurement_call(save_stock, db, user.tenant_id, user.id, payload)
    db.commit()
    return as_dict(row)


@router.post("/procurement/requests", status_code=201)
def create_procurement_request(payload: InquiryInput, user: Writer, db: Database):
    from app.market_intelligence.procurement import create_inquiry

    row = procurement_call(create_inquiry, db, user.tenant_id, user.id, payload)
    db.commit()
    return as_dict(row)


@router.post("/procurement/requests/{request_id}/quotes", status_code=201)
def record_supplier_quote(
    request_id: str, payload: QuoteInput, user: Writer, db: Database
):
    from app.market_intelligence.procurement import add_quote

    row = procurement_call(add_quote, db, user.tenant_id, user.id, request_id, payload)
    db.commit()
    return as_dict(row)


@router.post("/procurement/requests/{request_id}/selection")
def select_procurement_quote(
    request_id: str, payload: SelectionInput, user: Writer, db: Database
):
    from app.market_intelligence.procurement import select_quote

    row = procurement_call(
        select_quote, db, user.tenant_id, user.id, request_id, payload
    )
    db.commit()
    return as_dict(row)


@router.get("/facts")
def get_facts(
    user: Reader,
    db: Database,
    slice: Filters,
    kind: str = Query(
        "demand",
        pattern="^(demand|match|offer|purchase|sale|award|price|inventory|index)$",
    ),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    query = fact_query(db, user.tenant_id, **slice).filter(Fact.kind == kind)
    return {
        "total": query.count(),
        "rows": [
            as_dict(r)
            for r in query.order_by(Fact.event_at.desc(), Fact.id)
            .offset(offset)
            .limit(limit)
        ],
    }


@router.get("/entities")
def get_entities(
    user: Reader,
    db: Database,
    kind: str = Query("supplier", pattern="^(supplier|product|brand|category)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: str | None = Query(None, max_length=200),
):
    query = scoped(db, Entity, user.tenant_id).filter_by(kind=kind, active=True)
    if search:
        query = query.filter(Entity.name.contains(search, autoescape=True))
    return {
        "total": query.count(),
        "rows": [
            as_dict(r)
            for r in query.order_by(Entity.name, Entity.id).offset(offset).limit(limit)
        ],
    }


@router.post("/sync", status_code=202)
def start_sync(payload: SyncRequest, user: Admin, db: Database):
    # Persisted outbox is polled by worker-data. Broker failure cannot lose a job.
    from app.market_intelligence.queue import enqueue_run

    try:
        run = enqueue_run(db, user.tenant_id, payload.model_dump(mode="json"))
    except RuntimeError as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    db.commit()
    return {"id": run.id, "status": run.status}


@router.get("/sync-runs")
def sync_runs(user: Reader, db: Database):
    return [
        as_dict(r)
        for r in scoped(db, SyncRun, user.tenant_id)
        .order_by(SyncRun.created_at.desc())
        .limit(50)
    ]


@router.get("/operations")
def get_operations(user: Reader, db: Database, days: int = Query(30, ge=1, le=90)):
    from app.market_intelligence.operations import operations_report

    return operations_report(db, user.tenant_id, days=days)


@router.post("/records", status_code=201)
def import_records(payload: ImportRequest, user: Admin, db: Database):
    if not acquire_source_lock(db, user.tenant_id, payload.source):
        raise HTTPException(409, "Já existe uma carga desta fonte.")
    run = SyncRun(
        tenant_id=user.tenant_id,
        source=payload.source,
        status="running",
        started_at=now(),
    )
    db.add(run)
    db.flush()
    try:
        for record in payload.records:
            store_raw(
                db,
                user.tenant_id,
                run.id,
                payload.source,
                record.kind,
                record.data["id"],
                record.data,
            )
            normalized_record(
                db, user.tenant_id, payload.source, record.kind, record.data
            )
    except (ValueError, TypeError, KeyError) as error:
        db.rollback()
        raise HTTPException(422, str(error)) from error
    run.status, run.finished_at, run.counts = (
        "completed",
        now(),
        {"records": len(payload.records)},
    )
    db.commit()
    return {"id": run.id, "records": len(payload.records)}


@router.get("/identity-reviews")
def get_reviews(
    user: Reader,
    db: Database,
    status: str = Query("pending", pattern="^(pending|accepted|rejected)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    query = scoped(db, Review, user.tenant_id).filter_by(status=status)
    return {
        "total": query.count(),
        "rows": [
            as_dict(r)
            for r in query.order_by(Review.created_at, Review.id)
            .offset(offset)
            .limit(limit)
        ],
    }


@router.post("/identity-reviews/{review_id}")
def decide_review(review_id: str, payload: ReviewRequest, user: Writer, db: Database):
    try:
        row = review_identity(db, user.tenant_id, review_id, payload.decision, user.id)
        db.commit()
        return as_dict(row)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        db.rollback()
        raise HTTPException(409, str(error)) from error


@router.get("/aliases")
def aliases(user: Reader, db: Database):
    return [
        as_dict(r)
        for r in scoped(db, BrandAlias, user.tenant_id)
        .order_by(BrandAlias.alias)
        .limit(1000)
    ]


@router.post("/suppliers/normalize")
def normalize_supplier_names(user: Admin, db: Database):
    from app.market_intelligence.suppliers import normalize_suppliers

    if not acquire_source_lock(db, user.tenant_id, "supplier-normalization"):
        raise HTTPException(409, "Normalização de fornecedores em andamento.")
    result = normalize_suppliers(db, user.tenant_id, user.id)
    db.commit()
    return result


@router.put("/aliases")
def set_alias(payload: AliasRequest, user: Admin, db: Database):
    alias = normalize(payload.alias)
    if not alias or not normalize(payload.canonical):
        raise HTTPException(422, "Alias vazio após normalização.")
    row = scoped(db, BrandAlias, user.tenant_id).filter_by(alias=alias).one_or_none()
    if not row:
        row = BrandAlias(
            tenant_id=user.tenant_id,
            alias=alias,
            canonical=payload.canonical.strip(),
            reviewed_by=user.id,
            version=1,
        )
        db.add(row)
    else:
        db.add(
            Feedback(
                tenant_id=user.tenant_id,
                item_id=f"brand_alias:{alias}",
                action="alias_changed",
                user_id=user.id,
                payload={
                    "old": row.canonical,
                    "new": payload.canonical,
                    "version": row.version,
                },
            )
        )
        row.canonical, row.version, row.reviewed_by = (
            payload.canonical.strip(),
            row.version + 1,
            user.id,
        )
    db.commit()
    return as_dict(row)


@router.post("/feedback", status_code=201)
def feedback(payload: FeedbackRequest, user: Writer, db: Database):
    item = (
        scoped(db, Fact, user.tenant_id)
        .filter_by(kind="demand", item_id=payload.item_id, active=True)
        .first()
    )
    if not item:
        raise HTTPException(404, "Item não encontrado neste tenant.")
    if payload.action == "supplier_selected":
        supplier = (
            scoped(db, Entity, user.tenant_id)
            .filter_by(id=payload.payload["supplier_id"], kind="supplier", active=True)
            .first()
        )
        if not supplier:
            raise HTTPException(404, "Fornecedor não encontrado.")
    from app.market_intelligence.training import feature_snapshot

    offer = (
        scoped(db, Fact, user.tenant_id)
        .filter_by(
            kind="offer", item_id=payload.item_id, source=item.source, active=True
        )
        .first()
    )
    from app.market_intelligence.review_models import technical_snapshot

    selected_match = (
        scoped(db, Fact, user.tenant_id)
        .filter_by(
            kind="match",
            item_id=payload.item_id,
            product_id=item.product_id,
            active=True,
        )
        .order_by(Fact.event_at.desc())
        .first()
        if item.product_id
        else None
    )
    recorded_payload = {
        **payload.payload,
        "_snapshot": {
            "technical": technical_snapshot(selected_match) if selected_match else None,
            "features": feature_snapshot(item, offer),
            "split_group": item.notice_id or item.item_id,
            "captured_at": now().isoformat(),
            "result_known": scoped(db, Fact, user.tenant_id)
            .filter(
                Fact.kind == "award",
                Fact.item_id == payload.item_id,
                Fact.source == item.source,
                Fact.active.is_(True),
                Fact.outcome.in_(["won", "lost", "disqualified"]),
            )
            .first()
            is not None,
        },
    }
    if payload.action in {"supplier_selected", "price_adjusted"} and not offer:
        raise HTTPException(
            409, "Este item não possui uma oferta registrada para ajustar."
        )
    row = Feedback(
        tenant_id=user.tenant_id,
        item_id=payload.item_id,
        action=payload.action,
        payload=recorded_payload,
        user_id=user.id,
    )
    if payload.action == "confirmed_gap":
        item.coverage = "no_suitable_product"
    elif payload.action == "technical_review":
        from app.market_intelligence.domain import coverage

        item.attributes = {
            **item.attributes,
            "technical_verdict": payload.payload["verdict"],
        }
        item.coverage = coverage(payload.payload["verdict"], bool(item.product_id))
    elif payload.action == "price_adjusted" and offer:
        from app.market_intelligence.domain import number

        offer.offered_price = number(payload.payload["price"], positive=True)
    elif payload.action == "supplier_selected" and offer:
        offer.supplier_id = payload.payload["supplier_id"]
    db.add(row)
    db.commit()
    return as_dict(row)


@router.get("/model-runs")
def model_runs(user: Reader, db: Database):
    return [
        as_dict(r)
        for r in scoped(db, ModelRun, user.tenant_id)
        .order_by(ModelRun.created_at.desc())
        .limit(30)
    ]


@router.get("/recommendation/{item_id}")
def recommendation(
    item_id: str,
    user: Reader,
    db: Database,
    task: str = Query(
        "win_probability", pattern="^(win_probability|bid_no_bid|supplier_delay)$"
    ),
):
    from app.market_intelligence.training import feature_snapshot, predict_snapshot

    model = (
        scoped(db, ModelRun, user.tenant_id)
        .filter_by(task=task, status="evaluated")
        .order_by(ModelRun.created_at.desc())
        .first()
    )
    if not model or not model.report.get("performance_gate"):
        return {
            "status": "unavailable",
            "reason": "Nenhum modelo validado supera o baseline para este tenant.",
        }
    item = (
        scoped(db, Fact, user.tenant_id)
        .filter_by(kind="demand", item_id=item_id, active=True)
        .first()
    )
    if not item:
        raise HTTPException(404, "Item não encontrado.")
    offer = (
        scoped(db, Fact, user.tenant_id)
        .filter_by(kind="offer", item_id=item_id, source=item.source, active=True)
        .first()
    )
    return {
        "status": "shadow",
        "model_run_id": model.id,
        "dataset_version": model.dataset_version,
        **predict_snapshot(
            feature_snapshot(item, offer), model.report["serving_parameters"]
        ),
    }


@router.post("/webhooks/bling/{tenant_id}", status_code=202)
async def bling_webhook(tenant_id: int, request: Request, db: Database):
    import os

    from app.market_intelligence.config import bling_enabled

    if not bling_enabled():
        raise HTTPException(503, "Integração Bling ainda não habilitada.")

    from app.integrations.bling.credentials import CredentialCipher
    from app.integrations.bling.service import get_integration

    # Fail closed until companyId has been bound by the operator for this tenant.
    try:
        companies = json.loads(os.getenv("MARKET_BLING_COMPANY_MAP") or "{}")
    except ValueError as error:
        raise HTTPException(503, "Configuração do webhook inválida.") from error
    if not isinstance(companies, dict):
        raise HTTPException(503, "Configuração do webhook inválida.")
    company_id = companies.get(str(tenant_id))
    if not company_id:
        raise HTTPException(503, "Webhook não configurado.")
    set_tenant_context(db, tenant_id)
    record = get_integration(db, tenant_id)
    if not record:
        raise HTTPException(404, "Integração indisponível.")
    body = await request.body()
    if len(body) > 1024 * 1024:
        raise HTTPException(413, "Evento excede o limite.")
    secret = CredentialCipher.from_env().decrypt(record.client_secret_encrypted)
    if not verify_bling_signature(
        body, request.headers.get("X-Bling-Signature-256"), secret
    ):
        raise HTTPException(401, "Assinatura inválida.")
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError) as error:
        raise HTTPException(422, "JSON inválido.") from error
    if (
        not isinstance(data, dict)
        or str(data.get("companyId")) != str(company_id)
        or not data.get("eventId")
    ):
        raise HTTPException(422, "Identidade do evento inválida.")
    if not acquire_source_lock(db, tenant_id, "bling_webhook"):
        raise HTTPException(503, "Repetir entrega posteriormente.")
    # Signed events trigger authoritative reconciliation, so out-of-order payloads
    # cannot overwrite a newer product or delete it incorrectly.
    event_key = str(data["eventId"])
    from app.market_intelligence.models import RawRecord

    duplicate = (
        scoped(db, RawRecord, tenant_id)
        .filter_by(source="bling", entity="webhook", source_id=event_key)
        .first()
    )
    if duplicate:
        return {"accepted": True, "duplicate": True}
    pending = (
        scoped(db, SyncRun, tenant_id)
        .filter_by(source="bling", status="queued")
        .first()
    )
    if not pending:
        pending = SyncRun(
            tenant_id=tenant_id, source="bling", parameters={"trigger": "webhook"}
        )
        db.add(pending)
        db.flush()
    store_raw(db, tenant_id, pending.id, "bling", "webhook", event_key, data)
    db.commit()
    return {"accepted": True, "run_id": pending.id}
