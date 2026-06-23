from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.crm.models import (
    CrmNotice,
    CrmNoticeItemResult,
    CrmNoticeProduct,
    CrmNoticeProductMatch,
)
from app.db.models import Edital
from app.db.session import get_db
from app.services.reports import build_executive_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/executive")
def executive_report(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    editais = (
        db.query(Edital)
        .filter(Edital.tenant_id == current_user.tenant.slug)
        .all()
    )
    notices = (
        db.query(CrmNotice)
        .options(
            selectinload(CrmNotice.organ),
            selectinload(CrmNotice.notice_documents),
        )
        .filter(CrmNotice.tenant_id == current_user.tenant_id)
        .all()
    )
    products = (
        db.query(CrmNoticeProduct)
        .options(selectinload(CrmNoticeProduct.product_matches))
        .filter(CrmNoticeProduct.tenant_id == current_user.tenant_id)
        .all()
    )
    item_results = (
        db.query(CrmNoticeItemResult)
        .filter(CrmNoticeItemResult.tenant_id == current_user.tenant_id)
        .all()
    )
    matches = (
        db.query(CrmNoticeProductMatch)
        .filter(CrmNoticeProductMatch.tenant_id == current_user.tenant_id)
        .all()
    )
    return build_executive_report(
        editais=editais,
        notices=notices,
        products=products,
        item_results=item_results,
        matches=matches,
    )
