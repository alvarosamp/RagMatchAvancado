from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.crm.sales_process_importer import build_import_context_for_user, run_import
from app.crm.models import CrmNotice
from app.crm.query import TABLES, crm_user_payload, delete_records, insert_records, list_records, update_records
from app.db.session import get_db
from app.jobs.models import Job, JobStatus, JobType
from app.jobs.queue import JobQueue
from app.services.crm_item_matcher import (
    confirm_notice_item_match,
    get_notice_item_match_payload,
    reject_notice_item_match,
    run_notice_item_match,
)
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


@router.post("/imports/sales-processes")
async def crm_import_sales_processes(
    file: UploadFile = File(..., description="Planilha XLSX de processos de vendas"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Somente administradores podem importar a planilha de processos.")

    filename = (file.filename or "").lower()
    if not filename.endswith(".xlsx"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Envie uma planilha .xlsx.")

    suffix = ".xlsx"
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = tmp.name
            content = await file.read()
            tmp.write(content)

        summary = run_import(
            Path(temp_path),
            context_override=build_import_context_for_user(current_user),
        )
        db.expire_all()
        return {"ok": True, "summary": summary}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        await file.close()
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


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


@router.get("/notices/{notice_id}/matches")
def crm_notice_matches(
    notice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return get_notice_item_match_payload(db, current_user, notice_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/notices/{notice_id}/matches/run")
def crm_run_notice_matches(
    notice_id: str,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {"admin", "editor"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente para rodar o match.")
    payload = payload or {}
    try:
        return run_notice_item_match(
            db,
            current_user,
            notice_id,
            use_llm=payload.get("use_llm", True),
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/notices/{notice_id}/matches/run-job")
def crm_run_notice_matches_job(
    notice_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {"admin", "editor"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente para rodar o match.")

    notice = (
        db.query(CrmNotice)
        .filter(CrmNotice.id == notice_id, CrmNotice.tenant_id == current_user.tenant_id)
        .first()
    )
    if not notice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edital CRM nao encontrado.")

    existing_job = next(
        (
            job
            for job in (
                db.query(Job)
                .filter(
                    Job.tenant_id == current_user.tenant.slug,
                    Job.job_type == JobType.CRM_NOTICE_MATCH,
                    Job.status.in_([JobStatus.PENDING, JobStatus.RUNNING]),
                )
                .order_by(Job.created_at.desc())
                .all()
            )
            if (job.payload or {}).get("notice_id") == notice_id
        ),
        None,
    )
    if existing_job:
        return {
            "job_id": existing_job.id,
            "notice_id": notice_id,
            "message": "Ja existe um match em andamento para este edital.",
            "status_url": f"/jobs/{existing_job.id}",
        }

    queue = JobQueue()
    job_id = queue.criar_job_crm_notice_match(
        background_tasks=background_tasks,
        notice_id=notice_id,
        tenant_id=current_user.tenant.slug,
        user_id=current_user.id,
        db=db,
    )
    return {
        "job_id": job_id,
        "notice_id": notice_id,
        "message": "Match iniciado em segundo plano.",
        "status_url": f"/jobs/{job_id}",
    }


@router.get("/matches/jobs")
def crm_match_jobs(
    notice_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(Job)
        .filter(
            Job.tenant_id == current_user.tenant.slug,
            Job.job_type == JobType.CRM_NOTICE_MATCH,
        )
        .order_by(Job.created_at.desc())
    )

    jobs = query.limit(limit).all()
    if notice_id:
        jobs = [job for job in jobs if (job.payload or {}).get("notice_id") == notice_id]
    return {
        "jobs": [
            {
                "id": job.id,
                "job_type": job.job_type.value if job.job_type else "",
                "status": job.status.value if job.status else "",
                "progress": job.progress or 0.0,
                "payload": job.payload,
                "result": job.result,
                "error_message": job.error_message,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            }
            for job in jobs
        ]
    }


@router.post("/matches/{match_id}/confirm")
def crm_confirm_match(
    match_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {"admin", "editor"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente para confirmar o match.")
    try:
        return confirm_notice_item_match(db, current_user, match_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/matches/{match_id}/reject")
def crm_reject_match(
    match_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {"admin", "editor"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente para rejeitar o match.")
    try:
        return reject_notice_item_match(db, current_user, match_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


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
