from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.crm.models import CrmNotice
from app.crm.query import TABLES, crm_user_payload, delete_records, insert_records, list_records, update_records
from app.db.session import get_db
from app.services.ops_summary import summarize_crm

router = APIRouter(prefix="/crm", tags=["crm"])


def _parse_json_param(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parametro JSON invalido.") from exc


def _ensure_table(table_name: str) -> None:
    if table_name not in TABLES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tabela CRM '{table_name}' nao suportada.")


@router.get("/auth/user")
def crm_auth_user(current_user: User = Depends(get_current_user)):
    return {"user": crm_user_payload(current_user)}


@router.get("/summary")
def crm_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notices = (
        db.query(CrmNotice)
        .options(selectinload(CrmNotice.organ))
        .filter(CrmNotice.tenant_id == current_user.tenant_id)
        .all()
    )
    return summarize_crm(notices)


@router.get("/query/{table_name}")
def crm_query_list(
    table_name: str,
    filters: str | None = Query(default=None),
    orders: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1),
    head: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_table(table_name)
    filter_values = _parse_json_param(filters, [])
    order_values = _parse_json_param(orders, [])

    try:
        data, count = list_records(
            db,
            current_user,
            table_name,
            filters=filter_values,
            orders=order_values,
            limit=limit,
            head=head,
        )
        return {"data": data, "count": count}
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/query/{table_name}/insert")
def crm_query_insert(
    table_name: str,
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_table(table_name)

    try:
        data = insert_records(db, current_user, table_name, payload.get("values", []))
        return {"data": data}
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.patch("/query/{table_name}")
def crm_query_update(
    table_name: str,
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_table(table_name)

    try:
        data = update_records(
            db,
            current_user,
            table_name,
            payload.get("values", {}),
            filters=payload.get("filters", []),
        )
        return {"data": data}
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/query/{table_name}")
def crm_query_delete(
    table_name: str,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_table(table_name)
    payload = payload or {}

    try:
        deleted = delete_records(db, current_user, table_name, payload.get("filters", []))
        return {"deleted": deleted}
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
