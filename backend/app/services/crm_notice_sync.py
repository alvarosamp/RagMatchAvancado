from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.crm.models import (
    CrmItemWinnerType,
    CrmNotice,
    CrmNoticeItemResult,
    CrmNoticeOutcome,
    CrmNoticeProduct,
    CrmNoticeSession,
    CrmNoticeStage,
)


def apply_notice_defaults(values: dict[str, Any], existing: CrmNotice | None = None) -> None:
    tor_id = _clean(values.get("tor_id")) or _clean(getattr(existing, "tor_id", None))
    number = _clean(values.get("number")) or _clean(getattr(existing, "number", None))

    if tor_id and not values.get("number"):
        values["number"] = tor_id
    elif number and not values.get("tor_id"):
        values["tor_id"] = number

    if values.get("state"):
        values["state"] = str(values["state"]).strip().upper()[:8]


def apply_notice_product_defaults(values: dict[str, Any], existing: CrmNoticeProduct | None = None) -> None:
    explicit_reference_price = "reference_price" in values
    quantity = _coerce_float(values.get("quantity"), getattr(existing, "quantity", None), default=1.0)
    reference_price = _coerce_float(values.get("reference_price"), getattr(existing, "reference_price", None))
    reference_total = _coerce_float(values.get("reference_total_price"), getattr(existing, "reference_total_price", None))

    if explicit_reference_price and reference_price is None:
        values["reference_total_price"] = None
    elif reference_price is not None and quantity not in (None, 0):
        values["reference_total_price"] = round(reference_price * quantity, 4)
    elif reference_price is None and reference_total is not None and quantity not in (None, 0):
        values["reference_price"] = round(reference_total / quantity, 4)


def sync_notice_relationships(db: Session, notice: CrmNotice, *, created_by: int | None = None) -> None:
    primary_session = next((item for item in notice.notice_sessions if item.sequence == 1), None)

    if notice.auction_date:
        if primary_session is None:
            primary_session = CrmNoticeSession(
                tenant_id=notice.tenant_id,
                notice_id=notice.id,
                sequence=1,
                scheduled_at=notice.auction_date,
                created_by=created_by,
            )
            db.add(primary_session)
            notice.notice_sessions.append(primary_session)
        else:
            primary_session.scheduled_at = notice.auction_date
    elif primary_session and primary_session.scheduled_at:
        notice.auction_date = primary_session.scheduled_at

    if not notice.municipality_name and notice.organ and notice.organ.city:
        notice.municipality_name = notice.organ.city

    if not notice.title:
        first_description = next(
            (item.description for item in notice.notice_products if item.description),
            None,
        )
        if first_description:
            notice.title = first_description

    notice.estimated_value = derive_notice_estimated_value(notice)

    sync_notice_result_from_items(notice)


def sync_notice_from_product(
    db: Session,
    product: CrmNoticeProduct,
    *,
    created_by: int | None = None,
) -> None:
    notice = product.notice
    if notice is None and product.notice_id:
        notice = db.get(CrmNotice, product.notice_id)
    if notice is None:
        return
    sync_notice_relationships(db, notice, created_by=created_by)


def sync_notice_from_session(
    db: Session,
    session: CrmNoticeSession,
    *,
    created_by: int | None = None,
) -> None:
    notice = session.notice
    if notice is None and session.notice_id:
        notice = db.get(CrmNotice, session.notice_id)
    if notice is None:
        return

    if session.sequence == 1:
        if session.scheduled_at:
            notice.auction_date = session.scheduled_at
        elif notice.auction_date:
            session.scheduled_at = notice.auction_date

    sync_notice_relationships(db, notice, created_by=created_by)


def sync_notice_from_item_result(
    db: Session,
    item_result: CrmNoticeItemResult,
    *,
    created_by: int | None = None,
) -> None:
    notice = item_result.notice
    if notice is None and item_result.notice_id:
        notice = db.get(CrmNotice, item_result.notice_id)
    if notice is None:
        return
    sync_notice_relationships(db, notice, created_by=created_by)


def derive_notice_estimated_value(notice: CrmNotice) -> float | None:
    totals: list[float] = []
    for item in notice.notice_products:
        if item.reference_total_price is not None:
            totals.append(float(item.reference_total_price))
        elif item.reference_price is not None and item.quantity is not None:
            totals.append(float(item.reference_price) * float(item.quantity))
    if not totals:
        return None
    return round(sum(totals), 4)


def derive_notice_final_value(notice: CrmNotice) -> float | None:
    total = 0.0
    has_won_items = False
    product_by_id = {item.id: item for item in notice.notice_products}
    for result in notice.notice_item_results:
        if _winner_type(result.winner_type) != CrmItemWinnerType.US:
            continue
        has_won_items = True
        product = product_by_id.get(result.notice_product_id)
        quantity = _coerce_float(result.winning_quantity)
        if quantity is None and product is not None:
            quantity = _coerce_float(product.quantity, default=0.0)
        price = _coerce_float(result.winning_price, default=0.0)
        total += float(quantity or 0.0) * float(price or 0.0)
    if not has_won_items:
        return 0.0 if notice.notice_item_results else None
    return round(total, 4)


def derive_notice_outcome_from_items(notice: CrmNotice) -> CrmNoticeOutcome | None:
    results = list(notice.notice_item_results)
    if not results:
        return None

    if any(_winner_type(result.winner_type) == CrmItemWinnerType.US for result in results):
        return CrmNoticeOutcome.WON

    product_ids = {item.id for item in notice.notice_products if item.id}
    result_product_ids = {result.notice_product_id for result in results if result.notice_product_id}
    if product_ids and product_ids.issubset(result_product_ids):
        return CrmNoticeOutcome.LOST

    return CrmNoticeOutcome.PENDING


def sync_notice_result_from_items(notice: CrmNotice) -> None:
    derived_outcome = derive_notice_outcome_from_items(notice)
    derived_final_value = derive_notice_final_value(notice)

    if derived_final_value is not None:
        notice.final_value = derived_final_value

    if derived_outcome is None:
        return

    if derived_outcome == CrmNoticeOutcome.PENDING:
        if _outcome_value(notice.outcome) in {
            CrmNoticeOutcome.WON.value,
            CrmNoticeOutcome.LOST.value,
        }:
            notice.outcome = CrmNoticeOutcome.PENDING
        return

    notice.outcome = derived_outcome
    notice.stage = CrmNoticeStage.RESULT


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_float(value: Any, fallback: Any = None, *, default: float | None = None) -> float | None:
    raw = value if value is not None else fallback
    if raw in (None, ""):
        return default
    return float(raw)


def _winner_type(value: Any) -> CrmItemWinnerType | None:
    if value in (None, ""):
        return None
    if isinstance(value, CrmItemWinnerType):
        return value
    return CrmItemWinnerType(str(value))


def _outcome_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, CrmNoticeOutcome):
        return value.value
    return str(value)
