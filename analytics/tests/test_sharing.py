from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from app.market_intelligence.adapters import normalized_record
from app.market_intelligence.models import Entity, SupplierPresentationLink
from app.market_intelligence.sharing import ShareInput, create_share, shared_payload
from fastapi import HTTPException
from jose import jwt
from sqlalchemy import text


def setup(db):
    db.execute(
        text(
            "CREATE TABLE tenants (id INTEGER PRIMARY KEY, name TEXT, is_active BOOLEAN)"
        )
    )
    db.execute(
        text("INSERT INTO tenants VALUES (1,'Empresa 1',true),(2,'Empresa 2',true)")
    )
    for tenant in (1, 2):
        for entity, record in [
            ("product", {"id": "p", "name": f"Produto {tenant}"}),
            ("supplier", {"id": "s", "name": f"Fornecedor {tenant}"}),
            (
                "product_supplier",
                {"id": "r", "product_id": "p", "supplier_id": "s", "cost": 99},
            ),
            (
                "demand",
                {
                    "id": "d",
                    "product_id": "p",
                    "description": "Demanda",
                    "quantity": 2,
                    "unit": "UN",
                    "reference_price": 10,
                    "event_at": "2026-10-01T12:00:00Z",
                },
            ),
        ]:
            normalized_record(db, tenant, "manual", entity, record)
    db.commit()
    supplier = db.query(Entity).filter_by(tenant_id=1, kind="supplier").one()
    user = SimpleNamespace(id=100, tenant_id=1)
    share = create_share(db, user, ShareInput(supplier_id=supplier.id, source="manual"))
    return user, share


def test_live_response_excludes_private_data_and_updates(db):
    _, share = setup(db)
    data = shared_payload(db, share["token"])
    assert data["company"] == "Empresa 1"
    assert {r["product"] for r in data["rows"]} == {"Produto 1"}
    assert data["rows"][0]["quantity"] == 2
    assert not any(
        key in str(data)
        for key in [
            "tenant_id",
            "supplier_id",
            "product_id",
            "cost",
            "margin",
            "token_hash",
        ]
    )
    normalized_record(
        db,
        1,
        "manual",
        "demand",
        {
            "id": "d",
            "product_id": "p",
            "description": "Demanda",
            "quantity": 8,
            "unit": "UN",
            "reference_price": 10,
            "event_at": "2026-10-01T12:00:00Z",
        },
    )
    db.commit()
    assert shared_payload(db, share["token"])["rows"][0]["quantity"] == 8


def test_revocation_expiration_and_forgery(db):
    _, share = setup(db)
    with pytest.raises(HTTPException):
        shared_payload(db, share["token"] + "tampered")
    row = db.query(SupplierPresentationLink).filter_by(id=share["id"]).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()
    with pytest.raises(HTTPException):
        shared_payload(db, share["token"])
    row.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
    row.revoked_at = datetime.now(timezone.utc)
    db.commit()
    with pytest.raises(HTTPException):
        shared_payload(db, share["token"])


def test_cross_tenant_supplier_and_wrong_token_audience(db, monkeypatch):
    user, _ = setup(db)
    foreign = db.query(Entity).filter_by(tenant_id=2, kind="supplier").one()
    with pytest.raises(HTTPException):
        create_share(db, user, ShareInput(supplier_id=foreign.id))
    import os

    token = jwt.encode(
        {
            "sub": "100",
            "exp": int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp()),
        },
        os.environ["SECRET_KEY"],
        algorithm="HS256",
    )
    with pytest.raises(HTTPException):
        shared_payload(db, token)


def test_share_scope_rejects_extra_fields_and_inverted_period(db):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ShareInput(supplier_id="s", cost=True)
    user, _ = setup(db)
    with pytest.raises(HTTPException):
        create_share(
            db,
            user,
            ShareInput(supplier_id="s", date_from="2026-10-02", date_to="2026-10-01"),
        )
