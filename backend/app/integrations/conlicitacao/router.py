from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.core.config import settings
from app.db.models import Tender
from app.db.session import get_db
from app.integrations.conlicitacao.client import ConlicitacaoClient
from app.integrations.conlicitacao.diagnostics import run_readonly_diagnostics
from app.integrations.conlicitacao.exceptions import (
    ConlicitacaoAPIError,
    ConlicitacaoConfigurationError,
)
from app.integrations.conlicitacao.metrics import render_metrics
from app.integrations.conlicitacao.service import (
    ConlicitacaoLookupResult,
    ConlicitacaoService,
)
from app.integrations.tenders.repository import TenderRepository

router = APIRouter(tags=["tender-integrations"])
CurrentUser = Annotated[User, Depends(get_current_user)]
EditorUser = Annotated[User, Depends(require_role("admin", "editor"))]
AdminUser = Annotated[User, Depends(require_role("admin"))]
Database = Annotated[Session, Depends(get_db)]


class ConlicitacaoDiagnosticsRequest(BaseModel):
    filter_id: int | None = Field(default=None, gt=0)
    bulletin_id: int | None = Field(default=None, gt=0)


class ConlicitacaoMonitoringRequest(BaseModel):
    bidding_id: int = Field(gt=0)
    user_id: int = Field(gt=0)


@router.get("/integrations/conlicitacao/status")
def conlicitacao_status(current_user: CurrentUser) -> dict[str, bool]:
    configured = settings.conlicitacao_enabled and bool(settings.conlicitacao_token)
    authorized = current_user.tenant_id in settings.conlicitacao_sync_tenant_ids
    manual_import_authorized = authorized or _manual_import_user_authorized(current_user)
    return {
        "enabled": settings.conlicitacao_enabled,
        "configured": configured,
        "read_only_available": configured,
        "authorized": authorized,
        "manual_import_authorized": manual_import_authorized,
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


def _ensure_conlicitacao_configured() -> None:
    if not settings.conlicitacao_enabled or not settings.conlicitacao_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Integração ConLicitação não configurada neste ambiente.",
        )


def _ensure_conlicitacao_access(current_user: User) -> None:
    _ensure_conlicitacao_configured()
    if current_user.tenant_id not in settings.conlicitacao_sync_tenant_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant não autorizado a usar a assinatura ConLicitação configurada.",
        )


def _manual_import_user_authorized(current_user: User) -> bool:
    email = (current_user.email or "").strip().casefold()
    return bool(email) and email in settings.conlicitacao_manual_import_admin_emails


def _ensure_conlicitacao_manual_import_access(current_user: User) -> None:
    _ensure_conlicitacao_configured()
    if (
        current_user.tenant_id not in settings.conlicitacao_sync_tenant_ids
        and not _manual_import_user_authorized(current_user)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrador não autorizado para importar dados da ConLicitação.",
        )


def _provider_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ConlicitacaoAPIError):
        # Never emit an upstream 401: the frontend correctly interprets a local
        # 401 as an expired RagMatch session and would sign the administrator out.
        code = (
            status.HTTP_429_TOO_MANY_REQUESTS
            if exc.status_code == 429
            else status.HTTP_502_BAD_GATEWAY
        )
        return HTTPException(status_code=code, detail=exc.detail)
    return HTTPException(status_code=503, detail=str(exc))


@router.post("/integrations/conlicitacao/diagnostics")
async def conlicitacao_diagnostics(
    payload: ConlicitacaoDiagnosticsRequest,
    current_user: AdminUser,
) -> dict[str, Any]:
    # Diagnóstico é estritamente somente leitura, sanitiza valores retornados
    # e exige papel de administrador. A allowlist de tenant continua obrigatória
    # para sincronização e operações de acompanhamento que alteram estado.
    _ensure_conlicitacao_configured()
    try:
        async with ConlicitacaoClient() as client:
            return await run_readonly_diagnostics(
                client,
                filter_id=payload.filter_id,
                bulletin_id=payload.bulletin_id,
            )
    except ConlicitacaoConfigurationError as exc:
        raise _provider_http_error(exc) from exc


@router.get("/integrations/conlicitacao/opportunities/{external_id}/preview")
async def preview_conlicitacao_opportunity(
    external_id: int,
    current_user: AdminUser,
) -> dict[str, Any]:
    _ensure_conlicitacao_configured()
    correlation_id = str(uuid.uuid4())
    try:
        async with ConlicitacaoClient() as client:
            lookup = await ConlicitacaoService(client).find_opportunity(
                str(external_id),
                correlation_id=correlation_id,
                max_bulletins=settings.conlicitacao_lookup_max_bulletins,
            )
    except (ConlicitacaoAPIError, ConlicitacaoConfigurationError) as exc:
        raise _provider_http_error(exc) from exc
    if lookup is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Licitação não encontrada nos "
                f"{settings.conlicitacao_lookup_max_bulletins} boletins mais recentes."
            ),
        )
    return _serialize_lookup(lookup, correlation_id=correlation_id)


@router.post("/integrations/conlicitacao/opportunities/{external_id}/import")
async def import_conlicitacao_opportunity(
    external_id: int,
    current_user: EditorUser,
    db: Database,
) -> dict[str, Any]:
    _ensure_conlicitacao_manual_import_access(current_user)
    correlation_id = str(uuid.uuid4())
    try:
        async with ConlicitacaoClient() as client:
            lookup = await ConlicitacaoService(client).find_opportunity(
                str(external_id),
                correlation_id=correlation_id,
                max_bulletins=settings.conlicitacao_lookup_max_bulletins,
            )
        if lookup is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Licitação não encontrada nos "
                    f"{settings.conlicitacao_lookup_max_bulletins} boletins mais recentes."
                ),
            )
        row, created = TenderRepository(db, current_user.tenant_id).upsert(
            lookup.opportunity
        )
        db.commit()
    except (ConlicitacaoAPIError, ConlicitacaoConfigurationError) as exc:
        db.rollback()
        raise _provider_http_error(exc) from exc
    except Exception:
        db.rollback()
        raise
    return {
        "status": "imported" if created else "updated",
        "created": created,
        "correlation_id": correlation_id,
        "tender": _serialize_tender(row, include_raw=False),
    }


@router.post("/integrations/conlicitacao/monitoring/start")
async def start_conlicitacao_monitoring(
    payload: ConlicitacaoMonitoringRequest,
    current_user: AdminUser,
) -> dict[str, Any]:
    _ensure_conlicitacao_access(current_user)
    correlation_id = str(uuid.uuid4())
    try:
        async with ConlicitacaoClient() as client:
            await client.start_monitoring(
                payload.bidding_id, payload.user_id, correlation_id=correlation_id
            )
    except (ConlicitacaoAPIError, ConlicitacaoConfigurationError) as exc:
        raise _provider_http_error(exc) from exc
    return {"status": "started", "correlation_id": correlation_id}


@router.delete("/integrations/conlicitacao/monitoring/{bidding_id}")
async def stop_conlicitacao_monitoring(
    bidding_id: int,
    current_user: AdminUser,
    user_id: int = Query(gt=0),
) -> dict[str, Any]:
    _ensure_conlicitacao_access(current_user)
    correlation_id = str(uuid.uuid4())
    try:
        async with ConlicitacaoClient() as client:
            await client.stop_monitoring(
                bidding_id, user_id, correlation_id=correlation_id
            )
    except (ConlicitacaoAPIError, ConlicitacaoConfigurationError) as exc:
        raise _provider_http_error(exc) from exc
    return {"status": "stopped", "correlation_id": correlation_id}


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
    rows = (
        query.order_by(Tender.opening_at.desc(), Tender.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
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
        "id",
        "tenant_id",
        "provider",
        "external_id",
        "title",
        "object",
        "status",
        "edital_number",
        "process_number",
        "uasg",
        "public_body_name",
        "public_body_city",
        "public_body_state",
        "opening_at",
        "proposal_deadline_at",
        "estimated_value",
        "source_url",
        "created_at",
        "updated_at",
    )
    payload = {field: getattr(row, field) for field in fields}
    if include_raw:
        payload["raw_payload"] = row.raw_payload
    return payload


def _serialize_lookup(
    lookup: ConlicitacaoLookupResult,
    *,
    correlation_id: str,
) -> dict[str, Any]:
    opportunity = lookup.opportunity.model_dump(
        mode="json",
        exclude={"raw_payload"},
    )
    return {
        "correlation_id": correlation_id,
        "filter_id": lookup.filter_id,
        "bulletin_id": lookup.bulletin_id,
        "bulletin_number": lookup.bulletin_number,
        "bulletin_closed_at": lookup.bulletin_closed_at,
        "opportunity": opportunity,
    }
