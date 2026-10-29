from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from app.db.models import Base


class WhatsAppContact(Base):
    """Identity bridge, like password reset tokens; contains no tenant business data.

    Webhooks must resolve this bridge before establishing the tenant RLS context.
    Access through the portal always filters by the authenticated user's id.
    """

    __tablename__ = "whatsapp_contacts"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    phone = Column(String(15), unique=True, nullable=True)
    token_hash = Column(String(64), unique=True, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    auth_version = Column(Integer, nullable=False, default=0)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    notifications_enabled = Column(Boolean, nullable=False, default=False)
    last_request_at = Column(DateTime(timezone=True), nullable=True)


class WhatsAppDelivery(Base):
    """Dedupe keys only: never persist incoming message contents or responses."""

    __tablename__ = "whatsapp_deliveries"

    key = Column(String(64), primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
