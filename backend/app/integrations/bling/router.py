from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import require_role
from app.auth.models import User
from app.db.session import get_db
from app.integrations.bling.client import BlingAPIError, BlingConfigurationError
from app.integrations.bling.schemas import (
    BlingCredentialsPayload,
    BlingIntegrationStatus,
    BlingInvoicePayload,
    BlingOAuthStartResponse,
    BlingSalesOrderPayload,
)
from app.integrations.bling.service import (
    build_tenant_client,
    complete_oauth,
    disconnect,
    get_integration,
    integration_status,
    save_credentials,
    start_oauth,
)

router = APIRouter(prefix="/integrations/bling", tags=["integrações - Bling"])
AdminUser = Annotated[User, Depends(require_role("admin"))]
WriterUser = Annotated[User, Depends(require_role("admin", "editor"))]
Database = Annotated[Session, Depends(get_db)]


def _call_bling(operation: Any) -> Any:
    try:
        return operation()
    except BlingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except BlingAPIError as exc:
        status_code = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status_code, detail=exc.detail) from exc


@router.get("/status", response_model=BlingIntegrationStatus)
def get_status(current_user: WriterUser, db: Database) -> dict[str, Any]:
    return integration_status(get_integration(db, current_user.tenant_id))


@router.put("/credentials", response_model=BlingIntegrationStatus)
def configure_credentials(
    payload: BlingCredentialsPayload,
    current_user: AdminUser,
    db: Database,
) -> dict[str, Any]:
    record = _call_bling(
        lambda: save_credentials(
            db,
            tenant_id=current_user.tenant_id,
            client_id=payload.client_id,
            client_secret=payload.client_secret,
        )
    )
    return integration_status(record)


@router.delete(
    "/credentials",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_credentials(current_user: AdminUser, db: Database) -> Response:
    disconnect(db, tenant_id=current_user.tenant_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/oauth/start", response_model=BlingOAuthStartResponse)
def begin_oauth(current_user: AdminUser, db: Database) -> dict[str, str]:
    authorization_url = _call_bling(
        lambda: start_oauth(db, tenant_id=current_user.tenant_id)
    )
    return {"authorizationUrl": authorization_url}


@router.get("/oauth/callback", include_in_schema=False)
def oauth_callback(
    current_user: AdminUser,
    db: Database,
    code: Annotated[str, Query(min_length=1)],
    state_value: Annotated[str, Query(alias="state", min_length=16)],
) -> RedirectResponse:
    _call_bling(
        lambda: complete_oauth(
            db,
            tenant_id=current_user.tenant_id,
            state=state_value,
            code=code,
        )
    )
    destination = os.getenv(
        "BLING_FRONTEND_CALLBACK_URL", "/integracoes/bling?bling=connected"
    )
    return RedirectResponse(destination, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/sales-orders", status_code=status.HTTP_201_CREATED)
def create_sales_order(
    payload: BlingSalesOrderPayload,
    current_user: WriterUser,
    db: Database,
) -> dict[str, Any]:
    body = payload.model_dump(mode="json", exclude_none=True)
    return _call_bling(
        lambda: build_tenant_client(
            db, tenant_id=current_user.tenant_id
        ).create_sales_order(body)
    )


@router.post(
    "/sales-orders/{sales_order_id}/invoice",
    status_code=status.HTTP_201_CREATED,
)
def create_invoice_from_sales_order(
    sales_order_id: int,
    current_user: WriterUser,
    db: Database,
) -> dict[str, Any]:
    return _call_bling(
        lambda: build_tenant_client(
            db, tenant_id=current_user.tenant_id
        ).create_invoice_from_sales_order(sales_order_id)
    )


@router.post("/invoices", status_code=status.HTTP_201_CREATED)
def create_invoice(
    payload: BlingInvoicePayload,
    current_user: WriterUser,
    db: Database,
) -> dict[str, Any]:
    body = payload.model_dump(mode="json", exclude_none=True)
    return _call_bling(
        lambda: build_tenant_client(
            db, tenant_id=current_user.tenant_id
        ).create_invoice(body)
    )


@router.post("/invoices/{invoice_id}/authorize")
def authorize_invoice(
    invoice_id: int,
    current_user: WriterUser,
    db: Database,
    send_email: Annotated[bool, Query(alias="sendEmail")] = False,
) -> dict[str, Any]:
    return _call_bling(
        lambda: build_tenant_client(
            db, tenant_id=current_user.tenant_id
        ).authorize_invoice(invoice_id, send_email=send_email)
    )
