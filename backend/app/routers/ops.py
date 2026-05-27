from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.crm.models import CrmNotice
from app.db.models import Edital
from app.db.session import get_db
from app.jobs.models import Job
from app.services.ops_summary import summarize_crm, summarize_editais, summarize_jobs

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/summary")
def ops_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    editais = (
        db.query(Edital)
        .options(selectinload(Edital.chunks), selectinload(Edital.requirements))
        .filter(Edital.tenant_id == current_user.tenant.slug)
        .all()
    )
    jobs = (
        db.query(Job)
        .filter(Job.tenant_id == current_user.tenant.slug)
        .order_by(Job.created_at.desc())
        .all()
    )
    notices = (
        db.query(CrmNotice)
        .options(selectinload(CrmNotice.organ))
        .filter(CrmNotice.tenant_id == current_user.tenant_id)
        .all()
    )

    return {
        "generated_at": now.isoformat(),
        "health": {"api": "ok"},
        "editais": summarize_editais(editais),
        "jobs": summarize_jobs(jobs, now=now),
        "crm": summarize_crm(notices, now=now),
    }
