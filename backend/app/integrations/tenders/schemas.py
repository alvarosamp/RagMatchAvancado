from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TenderDocument(BaseModel):
    filename: str
    url: str


class TenderOpportunity(BaseModel):
    """Canonical opportunity exchanged between providers and the application."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    external_id: str
    title: str
    object: str | None = None
    status: str | None = None
    edital_number: str | None = None
    process_number: str | None = None
    uasg: str | None = None
    public_body_name: str | None = None
    public_body_city: str | None = None
    public_body_state: str | None = None
    opening_at: datetime | None = None
    proposal_deadline_at: datetime | None = None
    estimated_value: Decimal | None = None
    source_url: str | None = None
    documents: list[TenderDocument] = Field(default_factory=list)
    raw_payload: dict[str, Any]


class TenderSyncResult(BaseModel):
    provider: str
    tenant_id: int
    filters_seen: int = 0
    bulletins_processed: int = 0
    tenders_imported: int = 0
    tenders_updated: int = 0
    tenders_deduplicated: int = 0
