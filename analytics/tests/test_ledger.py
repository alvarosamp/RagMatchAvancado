from app.market_intelligence.adapters import normalized_record
from app.market_intelligence.models import Fact, RawRecord, Review
from app.market_intelligence.repository import (
    resolve,
    review_identity,
    scoped,
    store_raw,
)


def test_raw_dedup_and_reverting_to_old_value_preserve_latest_history(db):
    assert store_raw(db, 1, "run1", "manual", "product", "p", {"price": 10})
    assert not store_raw(db, 1, "run2", "manual", "product", "p", {"price": 10})
    assert store_raw(db, 1, "run3", "manual", "product", "p", {"price": 20})
    assert store_raw(db, 1, "run4", "manual", "product", "p", {"price": 10})
    assert scoped(db, RawRecord, 1).count() == 3
    assert scoped(db, RawRecord, 1).order_by(
        RawRecord.revision_number.desc()
    ).first().payload == {"price": 10}


def test_exact_supplier_identity_is_tenant_scoped(db):
    a = resolve(
        db,
        1,
        "manual",
        "supplier",
        "a",
        {"name": "ACME", "tax_id": "00.000.000/E08G-12"},
    )
    b = resolve(
        db,
        1,
        "bling",
        "supplier",
        "b",
        {"name": "ACME LTDA", "tax_id": "00.000.000/E08G-12"},
    )
    c = resolve(
        db,
        2,
        "manual",
        "supplier",
        "a",
        {"name": "ACME", "tax_id": "00.000.000/E08G-12"},
    )
    assert a.id == b.id
    assert a.id != c.id


def test_contradictory_cnpj_blocks_automatic_relink(db):
    resolve(
        db,
        1,
        "manual",
        "supplier",
        "a",
        {"name": "ACME", "tax_id": "00.000.000/E08G-12"},
    )
    assert (
        resolve(
            db,
            1,
            "manual",
            "supplier",
            "a",
            {"name": "ACME", "tax_id": "00.000.000/0001-91"},
        )
        is None
    )
    review = scoped(db, Review, 1).one()
    assert review.reason == "conflicting_identifier"
    import pytest

    with pytest.raises(ValueError, match="contraditórios"):
        review_identity(db, 1, review.id, "accepted", 100)


def test_reimport_updates_fact_instead_of_duplicating(db):
    record = {
        "id": "p1",
        "event_at": "2026-10-01T12:00:00Z",
        "quantity": 2,
        "unit_price": "0.1",
        "unit": "un",
    }
    normalized_record(db, 1, "manual", "purchase", record)
    normalized_record(db, 1, "manual", "purchase", {**record, "unit_price": "0.2"})
    assert scoped(db, Fact, 1).count() == 1
    assert float(scoped(db, Fact, 1).one().total_value) == 0.4


def test_similar_names_only_create_review_and_do_not_merge(db):
    a = resolve(db, 1, "manual", "supplier", "a", {"name": "ACME Tecnologia"})
    b = resolve(db, 1, "bling", "supplier", "b", {"name": "ACME Tecnologias"})
    assert a.id != b.id
    assert scoped(db, Review, 1).count() == 1
