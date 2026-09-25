from __future__ import annotations

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.db.models import Base


class BlingTenantIntegration(Base):
    """Encrypted Bling credentials and OAuth state owned by one tenant."""

    __tablename__ = "bling_tenant_integrations"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_bling_tenant_integrations_tenant"),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(String(255), nullable=False)
    client_secret_encrypted = Column(Text, nullable=False)
    access_token_encrypted = Column(Text)
    refresh_token_encrypted = Column(Text)
    token_expires_at = Column(DateTime(timezone=True))
    scopes = Column(Text)
    connected_at = Column(DateTime(timezone=True))
    pending_state_hash = Column(String(64), index=True)
    pending_state_expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
