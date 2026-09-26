from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.core.config import settings
from app.db.models import Tender
from app.db.session import get_db
from app.integrations.conlicitacao.metrics import render_metrics

router = APIRouter(tags=["tender-integrations"])
CurrentUser = Annotated[User, Depends(get_current_user)]
EditorUser = Annotated[User, Depends(require_role("admin", "editor"))]
Database = Annotated[Session, Depends(get_db)]


@router.get("/integrations/conlicitacao/status")
def conlicitacao_status(current_user: CurrentUser) -> dict[str, bool]:
    authorized = current_user.tenant_id in settings.conlicitacao_sync_tenant_ids
    return {
        "enabled": settings.conlicitacao_enabled,
        "configured": settings.conlicitacao_enabled and bool(settings.conlicitacao_token),
        "authorized": authorized,
    }


@router.post("/integrations/conlicitacao/sync", status_code=status.HTTP_202_ACCEPTED)
def enqueue_conlicitacao_sync(
    current_user: EditorUser,
) -> dict[str, str]:
    if not settings.conlicitacao_enabled or not settings.conlicitacao_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Integração ConLicitação não configurada neste ambiente.",
        )
    if current_user.tenant_id not in settings.conlicitacao_sync_tenant_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant não autorizado a usar a assinatura ConLicitação configurada.",
        )
    from app.jobs.tasks import process_conlicitacao_sync

    correlation_id = str(uuid.uuid4())
    process_conlicitacao_sync.send(current_user.tenant_id, correlation_id)
    return {"status": "queued", "correlation_id": correlation_id}


@router.get("/integrations/tenders")
def list_tenders(
    current_user: CurrentUser,
    db: Database,
    provider: str | None = None,
    tender_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    query = db.query(Tender).filter(Tender.tenant_id == current_user.tenant_id)
    if provider:
        query = query.filter(Tender.provider == provider)
    if tender_status:
        query = query.filter(Tender.status == tender_status)
    total = query.count()
    rows = query.order_by(Tender.opening_at.desc(), Tender.id.desc()).offset(offset).limit(limit).all()
    return {
        "items": [_serialize_tender(row, include_raw=False) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/integrations/tenders/{tender_id}")
def get_tender(
    tender_id: int,
    current_user: CurrentUser,
    db: Database,
) -> dict:
    row = (
        db.query(Tender)
        .filter(Tender.id == tender_id, Tender.tenant_id == current_user.tenant_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Licitação não encontrada.")
    return _serialize_tender(row, include_raw=True)


@router.get("/metrics/conlicitacao", include_in_schema=False)
def conlicitacao_metrics() -> Response:
    return Response(content=render_metrics(), media_type="text/plain; version=0.0.4")


def _serialize_tender(row: Tender, *, include_raw: bool) -> dict:
    fields = (
        "id", "tenant_id", "provider", "external_id", "title", "object", "status",
        "edital_number", "process_number", "uasg", "public_body_name",
        "public_body_city", "public_body_state", "opening_at", "proposal_deadline_at",
        "estimated_value", "source_url", "created_at", "updated_at",
    )
    payload = {field: getattr(row, field) for field in fields}
    if include_raw:
        payload["raw_payload"] = row.raw_payload
    return payload
