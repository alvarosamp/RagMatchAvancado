"""Provider-neutral contracts for public procurement integrations."""

from app.integrations.tenders.base import TenderProvider
from app.integrations.tenders.schemas import TenderDocument, TenderOpportunity

__all__ = ["TenderDocument", "TenderOpportunity", "TenderProvider"]
