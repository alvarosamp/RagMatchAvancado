from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.models import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class CrmNoticeStage(str, enum.Enum):
    TRIAGE = "triage"
    ANALYSIS = "analysis"
    DOCUMENTATION = "documentation"
    AUCTION = "auction"
    RESULT = "result"


class CrmNoticeOutcome(str, enum.Enum):
    PENDING = "pending"
    WON = "won"
    LOST = "lost"
    DISQUALIFIED = "disqualified"
    NOT_PURSUED = "not_pursued"


class CrmChecklistStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    EXPIRED = "expired"


class CrmNoticeSessionStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class CrmItemWinnerType(str, enum.Enum):
    US = "us"
    COMPETITOR = "competitor"
    CANCELLED = "cancelled"
    DESERT = "desert"


class CrmPostAuctionPhase(str, enum.Enum):
    JUDGMENT = "judgment"
    QUALIFICATION = "qualification"
    APPEALS = "appeals"
    ADJUDICATION = "adjudication"
    HOMOLOGATION = "homologation"
    CONVERTED = "converted"
    CLOSED = "closed"


class CrmNoticeProductMatchStatus(str, enum.Enum):
    SUGGESTED = "suggested"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class CrmNoticeProductMatchLevel(str, enum.Enum):
    STRONG = "strong"
    POSSIBLE = "possible"
    WEAK = "weak"
    NONE = "none"


class CrmOrgan(Base):
    __tablename__ = "crm_organs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "cnpj", name="uq_crm_organs_tenant_cnpj"),
        Index("ix_crm_organs_tenant_name", "tenant_id", "name"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    cnpj = Column(String)
    city = Column(String)
    state = Column(String)
    contact_name = Column(String)
    contact_email = Column(String)
    contact_phone = Column(String)
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    notices = relationship("CrmNotice", back_populates="organ")


class CrmPortal(Base):
    __tablename__ = "crm_portals"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_crm_portals_tenant_name"),
        Index("ix_crm_portals_tenant_name", "tenant_id", "name"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    url = Column(String)
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    notices = relationship("CrmNotice", back_populates="portal")


class CrmChecklistTemplate(Base):
    __tablename__ = "crm_checklist_templates"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_crm_checklist_templates_tenant_name"),)

    id = Column(String(36), primary_key=True, default=_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    items = relationship(
        "CrmChecklistTemplateItem",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="CrmChecklistTemplateItem.sort_order",
    )


class CrmChecklistTemplateItem(Base):
    __tablename__ = "crm_checklist_template_items"

    id = Column(String(36), primary_key=True, default=_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    template_id = Column(String(36), ForeignKey("crm_checklist_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    category = Column(String)
    is_required = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    template = relationship("CrmChecklistTemplate", back_populates="items")


class CrmCatalogProduct(Base):
    __tablename__ = "crm_catalog_products"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="uq_crm_catalog_products_tenant_sku"),
        Index("ix_crm_catalog_products_tenant_name", "tenant_id", "name"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    brand = Column(String)
    model = Column(String)
    specification = Column(Text)
    sku = Column(String)
    keywords = Column(Text)
    unit = Column(String)
    cost = Column(Float, nullable=False, default=0.0)
    tax_percent = Column(Float, nullable=False, default=0.0)
    margin_percent = Column(Float, nullable=False, default=0.0)
    notes = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    notice_products = relationship("CrmNoticeProduct", back_populates="catalog_product")
    notice_product_matches = relationship("CrmNoticeProductMatch", back_populates="catalog_product", cascade="all, delete-orphan")

    @property
    def min_price(self) -> float:
        return round((self.cost or 0.0) * (1 + (self.tax_percent or 0.0) / 100) * (1 + (self.margin_percent or 0.0) / 100), 4)


class CrmNotice(Base):
    __tablename__ = "crm_notices"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_crm_notices_tenant_number"),
        UniqueConstraint("tenant_id", "tor_id", name="uq_crm_notices_tenant_tor_id"),
        UniqueConstraint("tenant_id", "import_key", name="uq_crm_notices_tenant_import_key"),
        Index("ix_crm_notices_tenant_stage", "tenant_id", "stage"),
        Index("ix_crm_notices_tenant_outcome", "tenant_id", "outcome"),
        Index("ix_crm_notices_tenant_auction_date", "tenant_id", "auction_date"),
        Index("ix_crm_notices_tenant_tor_id", "tenant_id", "tor_id"),
        Index("ix_crm_notices_tenant_municipality", "tenant_id", "municipality_name"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    number = Column(String, nullable=False)
    tor_id = Column(String)
    municipality_name = Column(String)
    title = Column(Text)
    organ_id = Column(String(36), ForeignKey("crm_organs.id", ondelete="SET NULL"), index=True)
    portal_id = Column(String(36), ForeignKey("crm_portals.id", ondelete="SET NULL"), index=True)
    modality = Column(String)
    auction_date = Column(DateTime)
    estimated_value = Column(Float)
    final_value = Column(Float)
    drive_link = Column(Text)
    proposal_link = Column(Text)
    supplier_proposal_link = Column(Text)
    address = Column(String)
    state = Column(String)
    particularities = Column(Text)
    sales_status = Column(String)
    import_key = Column(String)
    stage = Column(SqlEnum(CrmNoticeStage, native_enum=False), nullable=False, default=CrmNoticeStage.TRIAGE)
    outcome = Column(SqlEnum(CrmNoticeOutcome, native_enum=False), nullable=False, default=CrmNoticeOutcome.PENDING)
    outcome_reason = Column(Text)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    post_auction_phase = Column(SqlEnum(CrmPostAuctionPhase, native_enum=False))
    post_auction_deadline = Column(Date)
    post_auction_owner = Column(Integer, ForeignKey("users.id"))
    post_auction_note = Column(Text)
    company_position = Column(Text)
    conversion_chance = Column(String)
    post_auction_entered_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    organ = relationship("CrmOrgan", back_populates="notices")
    portal = relationship("CrmPortal", back_populates="notices")
    notice_documents = relationship(
        "CrmNoticeDocument",
        back_populates="notice",
        cascade="all, delete-orphan",
        order_by="CrmNoticeDocument.sort_order",
    )
    notice_products = relationship(
        "CrmNoticeProduct",
        back_populates="notice",
        cascade="all, delete-orphan",
        order_by="CrmNoticeProduct.sort_order",
    )
    notice_history = relationship("CrmNoticeHistory", back_populates="notice", cascade="all, delete-orphan")
    notice_sessions = relationship(
        "CrmNoticeSession",
        back_populates="notice",
        cascade="all, delete-orphan",
        order_by="CrmNoticeSession.sequence",
    )
    notice_item_results = relationship("CrmNoticeItemResult", back_populates="notice", cascade="all, delete-orphan")
    notice_competitors = relationship("CrmNoticeCompetitor", back_populates="notice", cascade="all, delete-orphan")
    notice_product_matches = relationship("CrmNoticeProductMatch", back_populates="notice", cascade="all, delete-orphan")


class CrmNoticeProduct(Base):
    __tablename__ = "crm_notice_products"
    __table_args__ = (
        UniqueConstraint("notice_id", "item_number", name="uq_crm_notice_products_notice_item_number"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    notice_id = Column(String(36), ForeignKey("crm_notices.id", ondelete="CASCADE"), nullable=False, index=True)
    item_number = Column(String)
    lot = Column(String)
    product_code = Column(String)
    is_exclusive_epp = Column(Boolean)
    description = Column(Text, nullable=False)
    quantity = Column(Float, nullable=False, default=1.0)
    unit = Column(String)
    cost = Column(Float)
    unit_price = Column(Float)
    reference_price = Column(Float)
    reference_total_price = Column(Float)
    notes = Column(Text)
    sort_order = Column(Integer, nullable=False, default=0)
    catalog_product_id = Column(String(36), ForeignKey("crm_catalog_products.id", ondelete="SET NULL"), index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    notice = relationship("CrmNotice", back_populates="notice_products")
    catalog_product = relationship("CrmCatalogProduct", back_populates="notice_products")
    item_result = relationship("CrmNoticeItemResult", back_populates="notice_product", uselist=False, cascade="all, delete-orphan")
    product_matches = relationship(
        "CrmNoticeProductMatch",
        back_populates="notice_product",
        cascade="all, delete-orphan",
        order_by="CrmNoticeProductMatch.match_rank",
    )


class CrmNoticeDocument(Base):
    __tablename__ = "crm_notice_documents"

    id = Column(String(36), primary_key=True, default=_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    notice_id = Column(String(36), ForeignKey("crm_notices.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    category = Column(String)
    is_required = Column(Boolean, nullable=False, default=True)
    status = Column(SqlEnum(CrmChecklistStatus, native_enum=False), nullable=False, default=CrmChecklistStatus.PENDING)
    expires_at = Column(Date)
    notes = Column(Text)
    is_specific = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    notice = relationship("CrmNotice", back_populates="notice_documents")


class CrmNoticeProductMatch(Base):
    __tablename__ = "crm_notice_product_matches"
    __table_args__ = (
        UniqueConstraint("notice_product_id", "catalog_product_id", name="uq_crm_notice_product_matches_product_catalog"),
        Index("ix_crm_notice_product_matches_notice_rank", "notice_id", "notice_product_id", "match_rank"),
        Index("ix_crm_notice_product_matches_tenant_status", "tenant_id", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    notice_id = Column(String(36), ForeignKey("crm_notices.id", ondelete="CASCADE"), nullable=False, index=True)
    notice_product_id = Column(String(36), ForeignKey("crm_notice_products.id", ondelete="CASCADE"), nullable=False, index=True)
    catalog_product_id = Column(String(36), ForeignKey("crm_catalog_products.id", ondelete="CASCADE"), nullable=False, index=True)
    match_rank = Column(Integer, nullable=False, default=1)
    source_method = Column(String, nullable=False, default="hybrid")
    status = Column(SqlEnum(CrmNoticeProductMatchStatus, native_enum=False), nullable=False, default=CrmNoticeProductMatchStatus.SUGGESTED)
    match_level = Column(SqlEnum(CrmNoticeProductMatchLevel, native_enum=False), nullable=False, default=CrmNoticeProductMatchLevel.WEAK)
    lexical_score = Column(Float)
    semantic_score = Column(Float)
    llm_score = Column(Float)
    overall_score = Column(Float, nullable=False, default=0.0)
    rationale = Column(Text)
    matched_features = Column(JSON)
    conflicts = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    notice = relationship("CrmNotice", back_populates="notice_product_matches")
    notice_product = relationship("CrmNoticeProduct", back_populates="product_matches")
    catalog_product = relationship("CrmCatalogProduct", back_populates="notice_product_matches")


class CrmNoticeHistory(Base):
    __tablename__ = "crm_notice_history"

    id = Column(String(36), primary_key=True, default=_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    notice_id = Column(String(36), ForeignKey("crm_notices.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(Text, nullable=False)
    details = Column(JSON)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    notice = relationship("CrmNotice", back_populates="notice_history")


class CrmNoticeSession(Base):
    __tablename__ = "crm_notice_sessions"
    __table_args__ = (
        UniqueConstraint("notice_id", "sequence", name="uq_crm_notice_sessions_notice_sequence"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    notice_id = Column(String(36), ForeignKey("crm_notices.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False, default=1)
    scheduled_at = Column(DateTime)
    status = Column(SqlEnum(CrmNoticeSessionStatus, native_enum=False), nullable=False, default=CrmNoticeSessionStatus.SCHEDULED)
    outcome_summary = Column(Text)
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    notice = relationship("CrmNotice", back_populates="notice_sessions")


class CrmNoticeItemResult(Base):
    __tablename__ = "crm_notice_item_results"

    id = Column(String(36), primary_key=True, default=_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    notice_id = Column(String(36), ForeignKey("crm_notices.id", ondelete="CASCADE"), nullable=False, index=True)
    notice_product_id = Column(String(36), ForeignKey("crm_notice_products.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    winner_type = Column(SqlEnum(CrmItemWinnerType, native_enum=False), nullable=False, default=CrmItemWinnerType.US)
    competitor_name = Column(String)
    competitor_product = Column(String)
    winning_price = Column(Float)
    winning_quantity = Column(Float)
    winner_brand = Column(String)
    winner_model = Column(String)
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    notice = relationship("CrmNotice", back_populates="notice_item_results")
    notice_product = relationship("CrmNoticeProduct", back_populates="item_result")


class CrmNoticeCompetitor(Base):
    __tablename__ = "crm_notice_competitors"

    id = Column(String(36), primary_key=True, default=_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    notice_id = Column(String(36), ForeignKey("crm_notices.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    brand = Column(String)
    product = Column(String)
    price = Column(Float)
    status = Column(String, nullable=False, default="active")
    change_reason = Column(Text)
    last_update = Column(DateTime, server_default=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    notice = relationship("CrmNotice", back_populates="notice_competitors")
