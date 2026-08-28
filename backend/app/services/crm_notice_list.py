"""Fast summary endpoint for the CRM pipeline.

The legacy Supabase-compatible query returns complete relationships.  That is
useful for a detail page, but makes the initial pipeline load grow with every
document and product ever added to a notice.  This module deliberately returns
only fields needed by the cards, plus aggregate counters.
"""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime
from typing import Any

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session, joinedload

from app.auth.models import User
from app.crm.models import CrmChecklistStatus, CrmNotice, CrmNoticeDocument, CrmNoticeProduct


DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
CACHE_TTL_SECONDS = max(0, int(os.getenv("CRM_NOTICE_LIST_CACHE_TTL_SECONDS", "60")))


def list_notice_summaries(
    db: Session,
    current_user: User,
    *,
    limit: int = DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
    stage: str | None = None,
    include_discarded: bool = False,
) -> dict[str, Any]:
    """Return a stable cursor page without hydrating child collections."""
    limit = max(1, min(int(limit), MAX_PAGE_SIZE))
    cache_key = _cache_key(current_user.tenant_id, limit, cursor, stage, include_discarded)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    cursor_values = _decode_cursor(cursor) if cursor else None

    doc_counts = (
        db.query(
            CrmNoticeDocument.notice_id.label("notice_id"),
            func.count(CrmNoticeDocument.id).label("documents_count"),
            func.coalesce(
                func.sum(case((CrmNoticeDocument.status != CrmChecklistStatus.READY, 1), else_=0)),
                0,
            ).label("pending_documents_count"),
        )
        .filter(CrmNoticeDocument.tenant_id == current_user.tenant_id)
        .group_by(CrmNoticeDocument.notice_id)
        .subquery()
    )
    product_counts = (
        db.query(
            CrmNoticeProduct.notice_id.label("notice_id"),
            func.count(CrmNoticeProduct.id).label("products_count"),
        )
        .filter(CrmNoticeProduct.tenant_id == current_user.tenant_id)
        .group_by(CrmNoticeProduct.notice_id)
        .subquery()
    )

    query = (
        db.query(CrmNotice, doc_counts.c.documents_count, doc_counts.c.pending_documents_count, product_counts.c.products_count)
        .options(joinedload(CrmNotice.organ), joinedload(CrmNotice.portal))
        .outerjoin(doc_counts, doc_counts.c.notice_id == CrmNotice.id)
        .outerjoin(product_counts, product_counts.c.notice_id == CrmNotice.id)
        .filter(CrmNotice.tenant_id == current_user.tenant_id)
    )
    if not include_discarded:
        query = query.filter(CrmNotice.outcome != "not_pursued")
    if stage:
        query = query.filter(CrmNotice.stage == stage)
    if cursor_values:
        created_at, notice_id = cursor_values
        query = query.filter(
            or_(
                CrmNotice.created_at < created_at,
                and_(CrmNotice.created_at == created_at, CrmNotice.id < notice_id),
            )
        )

    rows = (
        query.order_by(CrmNotice.created_at.desc(), CrmNotice.id.desc())
        .limit(limit + 1)
        .all()
    )
    has_next = len(rows) > limit
    rows = rows[:limit]
    items = [_serialize_summary(notice, documents_count, pending_documents_count, products_count) for notice, documents_count, pending_documents_count, products_count in rows]
    next_cursor = _encode_cursor(rows[-1][0]) if has_next and rows else None
    response = {"items": items, "next_cursor": next_cursor, "has_next": has_next}
    _cache_set(cache_key, response)
    return response


def invalidate_notice_list_cache(tenant_id: int) -> None:
    """Bump a tenant-local cache version; obsolete keys expire naturally."""
    client = _redis_client()
    if client is None:
        return
    try:
        client.incr(f"crm:notice-list:version:{tenant_id}")
    except Exception:
        return


def _serialize_summary(notice: CrmNotice, documents_count: int | None, pending_documents_count: int | None, products_count: int | None) -> dict[str, Any]:
    return {
        "id": notice.id,
        "number": notice.number,
        "tor_id": notice.tor_id,
        "bid_number": notice.bid_number,
        "municipality_name": notice.municipality_name,
        "title": notice.title,
        "stage": notice.stage.value if hasattr(notice.stage, "value") else notice.stage,
        "outcome": notice.outcome.value if hasattr(notice.outcome, "value") else notice.outcome,
        "auction_date": _iso(notice.auction_date),
        "estimated_value": notice.estimated_value,
        "owner_id": str(notice.owner_id) if notice.owner_id is not None else None,
        "post_auction_phase": notice.post_auction_phase.value if hasattr(notice.post_auction_phase, "value") else notice.post_auction_phase,
        "post_auction_deadline": _iso(notice.post_auction_deadline),
        "company_position": notice.company_position,
        "conversion_chance": notice.conversion_chance,
        "post_auction_note": notice.post_auction_note,
        "particularities": notice.particularities,
        "organs": {"id": notice.organ.id, "name": notice.organ.name, "city": notice.organ.city} if notice.organ else None,
        "portals": {"id": notice.portal.id, "name": notice.portal.name, "url": notice.portal.url} if notice.portal else None,
        "documents_count": int(documents_count or 0),
        "pending_documents_count": int(pending_documents_count or 0),
        "products_count": int(products_count or 0),
    }


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _encode_cursor(notice: CrmNotice) -> str:
    payload = json.dumps([notice.created_at.isoformat(), notice.id], separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        created_at, notice_id = json.loads(raw.decode("utf-8"))
        return datetime.fromisoformat(created_at), str(notice_id)
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Cursor de paginacao invalido.") from exc


def _redis_client():
    if CACHE_TTL_SECONDS <= 0:
        return None
    try:
        from redis import Redis
        return Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), socket_connect_timeout=0.2, socket_timeout=0.2)
    except Exception:
        return None


def _cache_key(tenant_id: int, limit: int, cursor: str | None, stage: str | None, include_discarded: bool) -> str:
    client = _redis_client()
    version = 0
    if client is not None:
        try:
            version = int(client.get(f"crm:notice-list:version:{tenant_id}") or 0)
        except Exception:
            pass
    raw = json.dumps([tenant_id, version, limit, cursor, stage, include_discarded], separators=(",", ":"), ensure_ascii=True)
    return "crm:notice-list:" + base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def _cache_get(key: str) -> dict[str, Any] | None:
    client = _redis_client()
    if client is None:
        return None
    try:
        value = client.get(key)
        return json.loads(value) if value else None
    except Exception:
        return None


def _cache_set(key: str, payload: dict[str, Any]) -> None:
    client = _redis_client()
    if client is None:
        return
    try:
        client.setex(key, CACHE_TTL_SECONDS, json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    except Exception:
        return
