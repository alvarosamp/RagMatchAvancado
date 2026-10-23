"""Analytical ledger. Operational CRM metadata is deliberately kept separate."""

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

from app.db.models import JSON_PAYLOAD

WarehouseBase = declarative_base()


def new_id():
    return str(uuid.uuid4())


class TenantRow:
    id = Column(String(36), primary_key=True, default=new_id)
    tenant_id = Column(Integer, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RawRecord(TenantRow, WarehouseBase):
    __tablename__ = "records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "source", "entity", "source_id", "revision_number"
        ),
        Index(
            "ix_raw_latest", "tenant_id", "source", "entity", "source_id", "ingested_at"
        ),
        {"schema": "raw"},
    )
    source = Column(String(40), nullable=False)
    entity = Column(String(40), nullable=False)
    source_id = Column(String(180), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    revision_number = Column(Integer, nullable=False)
    payload = Column(JSON_PAYLOAD, nullable=False)
    source_updated_at = Column(DateTime(timezone=True))
    ingested_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    batch_id = Column(String(36), nullable=False)


class SyncRun(TenantRow, WarehouseBase):
    __tablename__ = "sync_runs"
    __table_args__ = ({"schema": "raw"},)
    source = Column(String(40), nullable=False)
    status = Column(String(20), nullable=False, default="queued")
    parameters = Column(JSON_PAYLOAD, nullable=False, default=dict)
    counts = Column(JSON_PAYLOAD, nullable=False, default=dict)
    error = Column(Text)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))


class Checkpoint(TenantRow, WarehouseBase):
    __tablename__ = "checkpoints"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source", "entity"),
        {"schema": "raw"},
    )
    source = Column(String(40), nullable=False)
    entity = Column(String(40), nullable=False)
    watermark = Column(DateTime(timezone=True))
    details = Column(JSON_PAYLOAD, nullable=False, default=dict)


class Entity(TenantRow, WarehouseBase):
    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "kind", "identity_key"),
        CheckConstraint("kind IN ('supplier','product','brand','category')"),
        {"schema": "core"},
    )
    kind = Column(String(20), nullable=False)
    identity_key = Column(String(220), nullable=False)
    name = Column(String(500), nullable=False)
    normalized_name = Column(String(500), nullable=False)
    tax_id = Column(String(14))
    gtin = Column(String(14))
    mpn = Column(String(160))
    sku = Column(String(160))
    brand = Column(String(160))
    category = Column(String(160))
    crm_product_id = Column(String(36))
    active = Column(Boolean, nullable=False, default=True)
    attributes = Column(JSON_PAYLOAD, nullable=False, default=dict)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Identity(TenantRow, WarehouseBase):
    __tablename__ = "identities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source", "kind", "source_id"),
        ForeignKeyConstraint(
            ["tenant_id", "entity_id"], ["core.entities.tenant_id", "core.entities.id"]
        ),
        {"schema": "core"},
    )
    source = Column(String(40), nullable=False)
    kind = Column(String(20), nullable=False)
    source_id = Column(String(180), nullable=False)
    entity_id = Column(String(36), nullable=False)
    method = Column(String(40), nullable=False)
    confidence = Column(Numeric(6, 5), nullable=False)
    evidence = Column(JSON_PAYLOAD, nullable=False, default=dict)
    reviewed_by = Column(Integer)
    reviewed_at = Column(DateTime(timezone=True))


class BrandAlias(TenantRow, WarehouseBase):
    __tablename__ = "brand_aliases"
    __table_args__ = (UniqueConstraint("tenant_id", "alias"), {"schema": "core"})
    alias = Column(String(160), nullable=False)
    canonical = Column(String(160), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    reviewed_by = Column(Integer, nullable=False)


class ProductSupplier(TenantRow, WarehouseBase):
    __tablename__ = "product_suppliers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "product_id", "supplier_id", "source"),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"], ["core.entities.tenant_id", "core.entities.id"]
        ),
        ForeignKeyConstraint(
            ["tenant_id", "supplier_id"],
            ["core.entities.tenant_id", "core.entities.id"],
        ),
        {"schema": "core"},
    )
    product_id = Column(String(36), nullable=False)
    supplier_id = Column(String(36), nullable=False)
    source = Column(String(40), nullable=False)
    supplier_sku = Column(String(160))
    cost = Column(Numeric(20, 6))
    lead_time_days = Column(Integer)
    minimum_quantity = Column(Numeric(20, 6))
    active = Column(Boolean, nullable=False, default=True)


class Fact(TenantRow, WarehouseBase):
    """Typed measures at source-line grain; payload carries evidence, not money."""

    __tablename__ = "facts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source", "kind", "source_id"),
        CheckConstraint(
            "kind IN ('demand','match','offer','purchase','sale','award','price','inventory','index')"
        ),
        CheckConstraint("quantity IS NULL OR quantity >= 0"),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"], ["core.entities.tenant_id", "core.entities.id"]
        ),
        ForeignKeyConstraint(
            ["tenant_id", "supplier_id"],
            ["core.entities.tenant_id", "core.entities.id"],
        ),
        Index("ix_fact_slice", "tenant_id", "kind", "event_at", "category", "state"),
        {"schema": "core"},
    )
    source = Column(String(40), nullable=False)
    kind = Column(String(20), nullable=False)
    source_id = Column(String(180), nullable=False)
    notice_id = Column(String(180))
    item_id = Column(String(180))
    product_id = Column(String(36))
    supplier_id = Column(String(36))
    category = Column(String(160))
    brand = Column(String(160))
    state = Column(String(2))
    unit = Column(String(40))
    currency = Column(String(3), nullable=False, default="BRL")
    description = Column(Text)
    quantity = Column(Numeric(20, 6))
    unit_price = Column(Numeric(20, 6))
    total_value = Column(Numeric(24, 6))
    reference_price = Column(Numeric(20, 6))
    cost = Column(Numeric(20, 6))
    offered_price = Column(Numeric(20, 6))
    winning_price = Column(Numeric(20, 6))
    price_type = Column(String(30))
    outcome = Column(String(30))
    coverage = Column(String(30))
    event_at = Column(DateTime(timezone=True), nullable=False)
    available_at = Column(DateTime(timezone=True), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    attributes = Column(JSON_PAYLOAD, nullable=False, default=dict)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Review(TenantRow, WarehouseBase):
    __tablename__ = "identity_reviews"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source", "kind", "source_id", "candidate_id"),
        {"schema": "core"},
    )
    source = Column(String(40), nullable=False)
    kind = Column(String(20), nullable=False)
    source_id = Column(String(180), nullable=False)
    candidate_id = Column(String(36), nullable=False)
    current_id = Column(String(36))
    status = Column(String(20), nullable=False, default="pending")
    reason = Column(Text)
    evidence = Column(JSON_PAYLOAD, nullable=False, default=dict)
    reviewed_by = Column(Integer)
    reviewed_at = Column(DateTime(timezone=True))


class Feedback(TenantRow, WarehouseBase):
    __tablename__ = "feedback"
    __table_args__ = ({"schema": "core"},)
    item_id = Column(String(180), nullable=False)
    action = Column(String(40), nullable=False)
    payload = Column(JSON_PAYLOAD, nullable=False, default=dict)
    user_id = Column(Integer, nullable=False)
    available_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SupplierPresentationLink(TenantRow, WarehouseBase):
    __tablename__ = "supplier_presentation_links"
    __table_args__ = ({"schema": "core"},)
    supplier_id = Column(String(36), nullable=False)
    token_hash = Column(String(64), nullable=False)
    scope = Column(JSON_PAYLOAD, nullable=False, default=dict)
    user_id = Column(Integer, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True))


class ModelRun(TenantRow, WarehouseBase):
    __tablename__ = "model_runs"
    __table_args__ = ({"schema": "mart"},)
    task = Column(String(40), nullable=False)
    status = Column(String(30), nullable=False)
    report = Column(JSON_PAYLOAD, nullable=False, default=dict)
    model_uri = Column(Text)
    dataset_version = Column(String(64))
    feature_version = Column(String(40), nullable=False, default="commercial-v1")


class ProcurementRequest(TenantRow, WarehouseBase):
    __tablename__ = "procurement_requests"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"], ["core.entities.tenant_id", "core.entities.id"]
        ),
        CheckConstraint("quantity > 0"),
        {"schema": "core"},
    )
    product_id = Column(String(36), nullable=False)
    quantity = Column(Numeric(20, 6), nullable=False)
    unit = Column(String(40), nullable=False)
    needed_by = Column(Date)
    notes = Column(Text)
    status = Column(String(20), nullable=False, default="open")
    user_id = Column(Integer, nullable=False)
    snapshot = Column(JSON_PAYLOAD, nullable=False, default=dict)
    selection_history = Column(JSON_PAYLOAD, nullable=False, default=list)


class SupplierQuote(TenantRow, WarehouseBase):
    __tablename__ = "supplier_quotes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "request_id"],
            ["core.procurement_requests.tenant_id", "core.procurement_requests.id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "supplier_id"],
            ["core.entities.tenant_id", "core.entities.id"],
        ),
        CheckConstraint("unit_price > 0"),
        CheckConstraint("shipping IS NULL OR shipping >= 0"),
        CheckConstraint("taxes IS NULL OR taxes >= 0"),
        {"schema": "core"},
    )
    request_id = Column(String(36), nullable=False)
    supplier_id = Column(String(36), nullable=False)
    unit_price = Column(Numeric(20, 6), nullable=False)
    shipping = Column(Numeric(20, 6))
    taxes = Column(Numeric(20, 6))
    available_quantity = Column(Numeric(20, 6))
    minimum_quantity = Column(Numeric(20, 6))
    lead_time_days = Column(Integer)
    valid_until = Column(Date, nullable=False)
    notes = Column(Text)
    user_id = Column(Integer, nullable=False)
    evidence = Column(JSON_PAYLOAD, nullable=False, default=dict)


WAREHOUSE_TABLES = tuple(WarehouseBase.metadata.sorted_tables)
