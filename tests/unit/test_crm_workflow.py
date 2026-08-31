import pytest

from app.services.crm_workflow import ensure_not_last_active_admin, validate_post_auction_transition


def test_post_auction_advances_sequentially_through_homologation():
    phases = ("judgment", "qualification", "appeals", "adjudication", "homologation")
    validate_post_auction_transition(None, phases[0])
    for previous, target in zip(phases, phases[1:]):
        validate_post_auction_transition(previous, target)


def test_post_auction_rejects_forward_skip_and_allows_return():
    with pytest.raises(ValueError, match="sequencial"):
        validate_post_auction_transition("judgment", "appeals")
    validate_post_auction_transition("homologation", "judgment")


def test_last_active_administrator_is_protected():
    with pytest.raises(ValueError, match="ultimo administrador"):
        ensure_not_last_active_admin(
            previous_role="admin", new_role="editor", target_is_active=True, active_admin_count=1,
        )


def test_role_change_is_allowed_when_another_active_admin_exists():
    ensure_not_last_active_admin(
        previous_role="admin", new_role="viewer", target_is_active=True, active_admin_count=2,
    )
