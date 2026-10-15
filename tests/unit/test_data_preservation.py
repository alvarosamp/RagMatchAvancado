from types import SimpleNamespace

import pytest

from app.core.data_preservation import require_explicit_empty_database_bootstrap
from app.crm.models import CrmNoticeProductMatchStatus
from app.services.crm_item_matcher import _has_validated_match


def test_empty_database_bootstrap_is_blocked_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ALLOW_EMPTY_DATABASE_BOOTSTRAP", raising=False)

    with pytest.raises(RuntimeError, match="Banco vazio em producao"):
        require_explicit_empty_database_bootstrap()


def test_empty_database_bootstrap_requires_explicit_production_override(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOW_EMPTY_DATABASE_BOOTSTRAP", "1")

    require_explicit_empty_database_bootstrap()


def test_empty_database_bootstrap_remains_available_outside_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("ALLOW_EMPTY_DATABASE_BOOTSTRAP", raising=False)

    require_explicit_empty_database_bootstrap()


@pytest.mark.parametrize(
    "evidence",
    [
        {"catalog_match_confirmed_at": object()},
        {"catalog_match_confirmed_by": "user-id"},
        {"catalog_match_source": "manual_confirmed"},
        {"match_reviewed_at": object()},
        {
            "product_matches": [
                SimpleNamespace(status=CrmNoticeProductMatchStatus.CONFIRMED)
            ]
        },
    ],
)
def test_validated_catalog_matches_are_protected(evidence):
    values = {
        "catalog_match_confirmed_at": None,
        "catalog_match_confirmed_by": None,
        "catalog_match_source": None,
        "match_reviewed_at": None,
        "product_matches": [],
    }
    values.update(evidence)
    product = SimpleNamespace(**values)

    assert _has_validated_match(product) is True


def test_unreviewed_catalog_match_can_be_recalculated():
    product = SimpleNamespace(
        catalog_match_confirmed_at=None,
        catalog_match_confirmed_by=None,
        catalog_match_source=None,
        match_reviewed_at=None,
        product_matches=[],
    )

    assert _has_validated_match(product) is False
