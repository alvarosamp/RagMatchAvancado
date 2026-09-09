from types import SimpleNamespace

import pytest

from app.crm.models import CrmItemWinnerType, CrmNoticeOutcome, CrmNoticeStage
from app.services.crm_notice_sync import derive_notice_outcome_from_items, sync_notice_result_from_items


@pytest.mark.parametrize(
    ("winner_type", "expected"),
    [
        (CrmItemWinnerType.CANCELLED, CrmNoticeOutcome.CANCELLED),
        (CrmItemWinnerType.DESERT, CrmNoticeOutcome.DESERT),
    ],
)
def test_notice_outcome_preserves_uniform_terminal_item_result(winner_type, expected):
    notice = SimpleNamespace(
        notice_item_results=[SimpleNamespace(winner_type=winner_type, notice_product_id="p1")],
        notice_products=[SimpleNamespace(id="p1")],
    )

    assert derive_notice_outcome_from_items(notice) == expected


def test_mixed_cancelled_and_desert_items_do_not_invent_one_terminal_outcome():
    notice = SimpleNamespace(
        notice_item_results=[
            SimpleNamespace(winner_type=CrmItemWinnerType.CANCELLED, notice_product_id="p1"),
            SimpleNamespace(winner_type=CrmItemWinnerType.DESERT, notice_product_id="p2"),
        ],
        notice_products=[SimpleNamespace(id="p1"), SimpleNamespace(id="p2")],
    )

    assert derive_notice_outcome_from_items(notice) == CrmNoticeOutcome.LOST


def test_lost_notice_leaves_triage_and_moves_to_results():
    notice = SimpleNamespace(
        outcome=CrmNoticeOutcome.PENDING,
        stage=CrmNoticeStage.TRIAGE,
        final_value=None,
        notice_item_results=[
            SimpleNamespace(winner_type=CrmItemWinnerType.COMPETITOR, notice_product_id="p1", winning_quantity=1, winning_price=90),
        ],
        notice_products=[SimpleNamespace(id="p1", quantity=1)],
    )

    sync_notice_result_from_items(notice)

    assert notice.outcome == CrmNoticeOutcome.LOST
    assert notice.stage == CrmNoticeStage.RESULT
