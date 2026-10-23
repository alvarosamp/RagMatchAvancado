"""Revocable, supplier-scoped live presentations; no internal report is exposed."""

import hashlib
import os
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.auth.models import Tenant
from app.db.session import set_tenant_context

from .models import Entity, SupplierPresentationLink
from .repository import scoped
from .service import report

AUDIENCE = "supplier-presentation"
PUBLIC_FIELDS = (
    "product",
    "brand",
    "category",
    "items",
    "quantity",
    "unit",
    "quantity_sample",
    "value",
    "value_sample",
)


class ShareInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supplier_id: str = Field(min_length=1, max_length=36)
    days: int = Field(default=7, ge=1, le=30)
    source: str = Field(default="crm", pattern="^(crm|pncp|manual|bling)$")
    date_from: date | None = None
    date_to: date | None = None
    category: str | None = Field(default=None, max_length=160)
    brand: str | None = Field(default=None, max_length=160)
    state: str | None = Field(default=None, pattern="^[A-Z]{2}$")
    search: str | None = Field(default=None, max_length=200)
    product_search: str | None = Field(default=None, max_length=200)
    product_id: str | None = Field(default=None, max_length=36)
    price_type: str | None = Field(default=None, max_length=30)
    unresolved_product: bool = False


def create_share(db, user, request):
    set_tenant_context(db, user.tenant_id)
    if request.date_from and request.date_to and request.date_from > request.date_to:
        raise HTTPException(422, "Período invertido.")
    supplier = (
        scoped(db, Entity, user.tenant_id)
        .filter_by(id=request.supplier_id, kind="supplier", active=True)
        .first()
    )
    if not supplier:
        raise HTTPException(404, "Fornecedor não encontrado nesta empresa.")
    expires = datetime.now(timezone.utc) + timedelta(days=request.days)
    link_id = str(uuid4())
    token = jwt.encode(
        {
            "aud": AUDIENCE,
            "tenant": user.tenant_id,
            "sub": link_id,
            "exp": int(expires.timestamp()),
        },
        os.environ["SECRET_KEY"],
        algorithm="HS256",
    )
    scope = request.model_dump(
        mode="json", exclude={"supplier_id", "days"}, exclude_none=True
    )
    row = SupplierPresentationLink(
        id=link_id,
        tenant_id=user.tenant_id,
        supplier_id=supplier.id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        scope=scope,
        user_id=user.id,
        expires_at=expires,
    )
    db.add(row)
    db.commit()
    return {
        "id": link_id,
        "token": token,
        "expires_at": expires.isoformat(),
        "supplier": supplier.name,
    }


def shared_payload(db, token):
    try:
        claims = jwt.decode(
            token,
            os.environ["SECRET_KEY"],
            algorithms=["HS256"],
            audience=AUDIENCE,
            options={"require_exp": True, "require_sub": True, "require_aud": True},
        )
        tenant = int(claims["tenant"])
        set_tenant_context(db, tenant)
    except (JWTError, KeyError, ValueError, TypeError):
        raise HTTPException(401, "Link inválido ou expirado.") from None
    row = (
        scoped(db, SupplierPresentationLink, tenant)
        .filter_by(
            id=claims["sub"], token_hash=hashlib.sha256(token.encode()).hexdigest()
        )
        .first()
    )
    expires_at = (
        row.expires_at
        if row and row.expires_at.tzinfo
        else row.expires_at.replace(tzinfo=timezone.utc)
        if row
        else None
    )
    if not row or row.revoked_at or expires_at <= datetime.now(timezone.utc):
        raise HTTPException(401, "Link inválido, revogado ou expirado.")
    company = db.scalar(
        select(Tenant.__table__.c.name).where(
            Tenant.__table__.c.id == tenant, Tenant.__table__.c.is_active.is_(True)
        )
    )
    if company is None:
        raise HTTPException(401, "Apresentação indisponível.")
    supplier = (
        scoped(db, Entity, tenant)
        .filter_by(id=row.supplier_id, kind="supplier", active=True)
        .first()
    )
    if not supplier:
        raise HTTPException(401, "Apresentação indisponível.")
    scope = dict(row.scope)
    product_search = scope.pop("product_search", "").casefold()
    for key in ("date_from", "date_to"):
        if scope.get(key):
            scope[key] = date.fromisoformat(scope[key])
    try:
        data = report(db, tenant, **scope)
    except OverflowError:
        raise HTTPException(
            413, "Recorte muito amplo. Peça à empresa um novo link com período menor."
        ) from None
    products = {
        r["product_id"]
        for r in data["supplier_products"]
        if r["supplier_id"] == row.supplier_id
    }
    rows = [
        {key: r.get(key) for key in PUBLIC_FIELDS}
        for r in data["product_demand"]
        if r["product_id"] in products
        and r["source"] == row.scope["source"]
        and int(r.get("items") or 0) > 0
        and product_search in str(r.get("product") or "").casefold()
    ]
    freshness = next(
        (
            r
            for r in data["quality"].get("freshness", [])
            if r["source"] == row.scope["source"]
        ),
        {},
    )
    public_scope = {
        key: value for key, value in row.scope.items() if key != "product_id"
    }
    return {
        "company": company,
        "supplier": supplier.name,
        "scope": public_scope,
        "generated_at": data["generated_at"],
        "last_sync": freshness.get("finished_at"),
        "expires_at": row.expires_at.isoformat(),
        "rows": rows,
    }
