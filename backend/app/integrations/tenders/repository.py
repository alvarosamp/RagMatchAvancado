from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Tender, TenderSyncCheckpoint
from app.integrations.tenders.schemas import TenderOpportunity


class TenderRepository:
    """Tenant-scoped persistence with database-backed idempotency."""

    def __init__(self, db: Session, tenant_id: int) -> None:
        self.db = db
        self.tenant_id = tenant_id

    def upsert(self, opportunity: TenderOpportunity) -> tuple[Tender, bool]:
        row = self._find(opportunity.provider, opportunity.external_id)
        created = row is None
        if row is None:
            row = Tender(
                tenant_id=self.tenant_id,
                provider=opportunity.provider,
                external_id=opportunity.external_id,
                title=opportunity.title,
                raw_payload=opportunity.raw_payload,
            )
            try:
                with self.db.begin_nested():
                    self.db.add(row)
                    self.db.flush()
            except IntegrityError:
                # A unique constraint remains the final guard when two workers
                # discover the same external opportunity concurrently.
                row = self._find(opportunity.provider, opportunity.external_id)
                if row is None:
                    raise
                created = False

        values = opportunity.model_dump(exclude={"documents"})
        values.pop("provider")
        values.pop("external_id")
        for field, value in values.items():
            setattr(row, field, value)
        self.db.flush()
        return row, created

    def checkpoint(self, provider: str, external_filter_id: str) -> TenderSyncCheckpoint | None:
        return (
            self.db.query(TenderSyncCheckpoint)
            .filter(
                TenderSyncCheckpoint.tenant_id == self.tenant_id,
                TenderSyncCheckpoint.provider == provider,
                TenderSyncCheckpoint.external_filter_id == external_filter_id,
            )
            .first()
        )

    def advance_checkpoint(
        self,
        provider: str,
        external_filter_id: str,
        bulletin_id: str,
        closed_at: datetime | None,
    ) -> TenderSyncCheckpoint:
        checkpoint = self.checkpoint(provider, external_filter_id)
        if checkpoint is None:
            checkpoint = TenderSyncCheckpoint(
                tenant_id=self.tenant_id,
                provider=provider,
                external_filter_id=external_filter_id,
            )
            try:
                with self.db.begin_nested():
                    self.db.add(checkpoint)
                    self.db.flush()
            except IntegrityError:
                checkpoint = self.checkpoint(provider, external_filter_id)
                if checkpoint is None:
                    raise
        if (
            checkpoint.last_bulletin_closed_at is not None
            and closed_at is not None
            and checkpoint.last_bulletin_closed_at > closed_at
        ):
            return checkpoint
        checkpoint.last_bulletin_id = bulletin_id
        checkpoint.last_bulletin_closed_at = closed_at
        checkpoint.last_synced_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.flush()
        return checkpoint

    def commit(self) -> None:
        self.db.commit()

    def _find(self, provider: str, external_id: str) -> Tender | None:
        return (
            self.db.query(Tender)
            .filter(
                Tender.tenant_id == self.tenant_id,
                Tender.provider == provider,
                Tender.external_id == external_id,
            )
            .first()
        )
