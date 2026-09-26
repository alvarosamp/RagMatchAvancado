from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.integrations.tenders.schemas import TenderDocument, TenderOpportunity


class TenderProvider(ABC):
    """Stable boundary implemented by procurement data providers."""

    name: str

    @abstractmethod
    async def list_opportunities(self, **kwargs: Any) -> list[TenderOpportunity]: ...

    @abstractmethod
    async def get_opportunity(self, external_id: str) -> TenderOpportunity: ...

    @abstractmethod
    async def get_documents(self, external_id: str) -> list[TenderDocument]: ...

    @abstractmethod
    async def start_monitoring(self, external_id: str, user_id: int) -> dict[str, Any]: ...

    @abstractmethod
    async def stop_monitoring(self, external_id: str, user_id: int) -> dict[str, Any]: ...

    @abstractmethod
    async def get_monitored_tenders(self, **kwargs: Any) -> dict[str, Any]: ...

    @abstractmethod
    async def get_messages(self, external_id: str, **kwargs: Any) -> dict[str, Any]: ...
