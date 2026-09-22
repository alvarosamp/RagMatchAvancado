from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import case, func

from app.auth.dependencies import get_current_user, require_role
from app.ai.usage_models import AIUsageEvent
from app.auth.models import User
from app.crm.models import CrmNotice
from app.db.models import Edital
from app.db.session import get_db
from app.jobs.models import Job
from app.services.ops_summary import summarize_crm, summarize_editais, summarize_jobs
from app.services.ai_usage_summary import build_ai_usage_summary
from app.jobs.queue import _month_bounds_utc

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/ai-usage")
def ai_usage_summary(
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Return monthly reported tokens and call counts for one tenant only."""
    start, end = _month_bounds_utc(datetime.now(timezone.utc))
    start = start.replace(tzinfo=timezone.utc)
    end = end.replace(tzinfo=timezone.utc)
    rows = (
        db.query(
            AIUsageEvent.provider.label("provider"),
            AIUsageEvent.model.label("model"),
            AIUsageEvent.operation.label("operation"),
            func.sum(case((AIUsageEvent.succeeded.is_(True), 1), else_=0)).label("calls"),
            func.sum(case((AIUsageEvent.succeeded.is_(False), 1), else_=0)).label("failed_calls"),
            func.sum(AIUsageEvent.input_tokens).label("input_tokens"),
            func.sum(AIUsageEvent.output_tokens).label("output_tokens"),
            func.sum(case(
                (
                    AIUsageEvent.succeeded.is_(True)
                    & (AIUsageEvent.input_tokens.is_(None) | AIUsageEvent.output_tokens.is_(None)),
                    1,
                ),
                else_=0,
            )).label("calls_without_token_counts"),
            func.sum(AIUsageEvent.duration_ms).label("total_duration_ms"),
        )
        .filter(
            AIUsageEvent.tenant_slug == current_user.tenant.slug,
            AIUsageEvent.created_at >= start,
            AIUsageEvent.created_at < end,
        )
        .group_by(AIUsageEvent.provider, AIUsageEvent.model, AIUsageEvent.operation)
        .all()
    )
    return build_ai_usage_summary(rows, start, end)


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
