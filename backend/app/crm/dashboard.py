"""Read dashboard fields without loading catalog, documents or item relationships."""

import logging
from datetime import datetime, timezone

from sqlalchemy import String, and_, cast, func, select
from sqlalchemy.exc import SQLAlchemyError

from app.auth.models import Tenant
from app.crm.models import (
    CrmNotice,
    CrmNoticeDocument,
    CrmNoticeItemResult,
    CrmNoticeProduct,
    CrmOrgan,
    CrmPortal,
)
from app.db.models import Edital, Requirement

logger = logging.getLogger(__name__)


def dashboard_snapshot(db, tenant_id: int) -> dict:
    """Keep independent sections available; failed queries never become zeroes."""
    errors = []

    def read(section, operation):
        try:
            # A failed optional query must not abort subsequent reads on PostgreSQL.
            with db.begin_nested():
                return operation()
        except SQLAlchemyError:
            logger.exception("CRM dashboard section failed: %s", section)
            errors.append(section)
            return None

    n, o, p = CrmNotice.__table__.c, CrmOrgan.__table__.c, CrmPortal.__table__.c
    notices_query = select(
        n.id, n.number, n.title, n.auction_date, n.created_at,
        cast(n.stage, String).label("stage"),
        cast(n.outcome, String).label("outcome"),
        cast(n.post_auction_phase, String).label("post_auction_phase"),
        o.name.label("organ_name"), p.name.label("portal_name"),
    ).select_from(CrmNotice.__table__).outerjoin(
        CrmOrgan.__table__, and_(n.organ_id == o.id, o.tenant_id == tenant_id)
    ).outerjoin(
        CrmPortal.__table__, and_(n.portal_id == p.id, p.tenant_id == tenant_id)
    ).where(n.tenant_id == tenant_id).order_by(n.created_at.desc(), n.id)

    def notices():
        rows = []
        for record in db.execute(notices_query).mappings():
            row = dict(record)
            row["organs"] = {"name": row.pop("organ_name")}
            row["portals"] = {"name": row.pop("portal_name")}
            for field in ("stage", "outcome", "post_auction_phase"):
                row[field] = row[field].lower() if row[field] else None
            for field in ("auction_date", "created_at"):
                row[field] = row[field].isoformat() if row[field] else None
            rows.append(row)
        return rows

    product = CrmNoticeProduct.__table__.c
    result = CrmNoticeItemResult.__table__.c
    products_query = select(product.id, product.notice_id, product.quantity).where(product.tenant_id == tenant_id)
    results_query = select(
        result.id, result.notice_id, result.notice_product_id,
        func.lower(cast(result.winner_type, String)).label("winner_type"),
        result.winning_price, result.winning_quantity,
    ).where(result.tenant_id == tenant_id)
    documents = CrmNoticeDocument.__table__.c
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tenant_name": read("company", lambda: db.scalar(select(Tenant.__table__.c.name).where(Tenant.__table__.c.id == tenant_id))),
        "notices": read("notices", notices),
        "products": read("products", lambda: [dict(row) for row in db.execute(products_query).mappings()]),
        "results": read("results", lambda: [dict(row) for row in db.execute(results_query).mappings()]),
        "pending_documents": read("documents", lambda: db.scalar(select(func.count()).select_from(CrmNoticeDocument.__table__).where(
            documents.tenant_id == tenant_id, func.lower(cast(documents.status, String)).in_(["pending", "in_progress"])
        ))),
        "analyzed_points": read("points", lambda: db.scalar(select(func.count()).select_from(Requirement.__table__).join(
            Edital.__table__, Requirement.__table__.c.edital_id == Edital.__table__.c.id
        ).where(Edital.__table__.c.tenant_id == tenant_id))),
        "errors": errors,
    }
