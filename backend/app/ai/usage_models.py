"""Persistence model for privacy-preserving provider usage telemetry."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.db.models import Base


class AIUsageEvent(Base):
    __tablename__ = "ai_usage_events"

    id = Column(String(36), primary_key=True)
    tenant_slug = Column(String, ForeignKey("tenants.slug"), nullable=False, index=True)
    operation = Column(String(64), nullable=False)
    correlation_id = Column(String(36), nullable=True)
    provider = Column(String(32), nullable=False)
    model = Column(String(128), nullable=False)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
