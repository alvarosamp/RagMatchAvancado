# =============================================================================
# jobs/router.py
# =============================================================================
#
# Endpoints para consultar o status de jobs assíncronos.
#
# GET /jobs/{job_id}           → status + progresso + resultado
# GET /jobs/                   → lista jobs do tenant (paginado)
#
# ISOLAMENTO MULTI-TENANT:
#   Cada tenant só vê seus próprios jobs.
#   Um tenant não consegue consultar jobs de outro tenant (retorna 404).
#
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.db.session import get_db
from app.jobs.models import Job, JobStatus, JobType
from app.auth.models import User
from app.auth.dependencies import get_current_user
from app.logs.config import logger

router = APIRouter(prefix="/jobs", tags=["jobs"])


# ─────────────────────────────────────────────────────────────────────────────
# Schemas de resposta
# ─────────────────────────────────────────────────────────────────────────────

class JobResponse(BaseModel):
    """
    Resposta completa de um job.

    O cliente usa este schema para implementar polling:
        while job.status not in ("done", "failed"):
            sleep(2)
            job = GET /jobs/{id}
        if job.status == "done":
            edital_id = job.result["edital_id"]
    """
    id:            str
    job_type:      str
    status:        str
    progress:      float          # 0.0 a 1.0 — para barra de progresso
    tenant_id:     str
    payload:       Optional[dict]
    result:        Optional[dict]  # preenchido quando status="done"
    error_message: Optional[str]   # preenchido quando status="failed"
    created_at:    Optional[datetime]
    started_at:    Optional[datetime]
    finished_at:   Optional[datetime]

    # Campos calculados — úteis para o frontend
    duration_seconds: Optional[float]  # tempo total de execução
    status_label:     str              # "⏳ Aguardando" / "🔄 Processando" / etc.

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# GET /jobs/{job_id} — consulta um job específico
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id:       str,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Retorna o status e resultado de um job.

    Use para polling — consulte a cada 2-3 segundos até status="done" ou "failed".

    ISOLAMENTO: só retorna o job se pertencer ao tenant do usuário.
    Retorna 404 para jobs de outros tenants (sem revelar que existem).

    Response quando PENDING:
        {"status": "pending", "progress": 0.0, "result": null}

    Response quando RUNNING:
        {"status": "running", "progress": 0.45, "result": null}

    Response quando DONE:
        {"status": "done", "progress": 1.0, "result": {"edital_id": 7, "n_chunks": 42}}

    Response quando FAILED:
        {"status": "failed", "progress": 0.3, "error_message": "Erro no OCR: ..."}
    """
    job = _get_job_do_tenant(job_id, current_user, db)
    return _build_response(job)


# ─────────────────────────────────────────────────────────────────────────────
# GET /jobs/ — lista jobs do tenant
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[JobResponse])
def list_jobs(
    status:       Optional[str] = None,   # filtrar por status (opcional)
    limit:        int           = 20,     # paginação
    offset:       int           = 0,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Lista os jobs do tenant autenticado, do mais recente para o mais antigo.

    Filtros opcionais:
        ?status=pending   → só jobs aguardando
        ?status=running   → jobs em execução agora
        ?status=done      → jobs concluídos
        ?status=failed    → jobs que falharam

    Paginação:
        ?limit=20&offset=0   → primeira página
        ?limit=20&offset=20  → segunda página
    """
    query = (
        db.query(Job)
        .filter(Job.tenant_id == current_user.tenant.slug)
        .order_by(Job.created_at.desc())
    )

    # Aplica filtro de status se fornecido
    if status:
        try:
            status_enum = JobStatus(status)
            query = query.filter(Job.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Status inválido: '{status}'. Use: pending, running, done, failed",
            )

    jobs = query.offset(offset).limit(limit).all()
    return [_build_response(j) for j in jobs]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────────────────────

def _get_job_do_tenant(job_id: str, current_user: User, db: Session) -> Job:
    """
    Busca um job e verifica que pertence ao tenant do usuário.
    Retorna 404 se não encontrado OU se pertencer a outro tenant.
    """
    job = (
        db.query(Job)
        .filter(
            Job.id        == job_id,
            Job.tenant_id == current_user.tenant.slug,
        )
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    return job


def _build_response(job: Job) -> JobResponse:
    """
    Constrói o JobResponse com campos calculados.
    """
    # Calcula duração se o job terminou
    duration = None
    if job.started_at and job.finished_at:
        duration = round((job.finished_at - job.started_at).total_seconds(), 1)

    # Label legível para o status
    labels = {
        JobStatus.PENDING: "⏳ Aguardando",
        JobStatus.RUNNING: "🔄 Processando",
        JobStatus.DONE:    "✅ Concluído",
        JobStatus.FAILED:  "❌ Falhou",
    }

    return JobResponse(
        id               = job.id,
        job_type         = job.job_type.value if job.job_type else "",
        status           = job.status.value if job.status else "",
        progress         = job.progress or 0.0,
        tenant_id        = job.tenant_id,
        payload          = job.payload,
        result           = job.result,
        error_message    = job.error_message,
        created_at       = job.created_at,
        started_at       = job.started_at,
        finished_at      = job.finished_at,
        duration_seconds = duration,
        status_label     = labels.get(job.status, job.status),
    )