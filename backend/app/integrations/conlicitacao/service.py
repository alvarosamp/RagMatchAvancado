from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

from app.integrations.conlicitacao import metrics
from app.integrations.conlicitacao.client import ConlicitacaoClient
from app.integrations.conlicitacao.exceptions import ConlicitacaoUnsupportedOperation
from app.integrations.conlicitacao.mapper import (
    PROVIDER,
    map_tender,
    parse_provider_datetime,
)
from app.integrations.conlicitacao.schemas import ConlicitacaoBulletinSummary
from app.integrations.tenders.base import TenderProvider
from app.integrations.tenders.schemas import (
    TenderDocument,
    TenderOpportunity,
    TenderSyncResult,
)


@dataclass(frozen=True)
class ConlicitacaoLookupResult:
    filter_id: int
    bulletin_id: int
    bulletin_number: int | None
    bulletin_closed_at: str | None
    opportunity: TenderOpportunity


class _TenderRepository(Protocol):
    def checkpoint(self, provider: str, external_filter_id: str) -> Any: ...
    def upsert(self, opportunity: TenderOpportunity) -> tuple[Any, bool]: ...
    def advance_checkpoint(
        self, provider: str, external_filter_id: str, bulletin_id: str, closed_at: Any
    ) -> Any: ...
    def commit(self) -> None: ...


class ConlicitacaoService(TenderProvider):
    name = PROVIDER

    def __init__(
        self,
        client: ConlicitacaoClient,
        repository: _TenderRepository | None = None,
        *,
        max_pages: int = 10,
    ) -> None:
        self.client = client
        self.repository = repository
        self.max_pages = max(1, max_pages)

    async def list_opportunities(self, **kwargs: Any) -> list[TenderOpportunity]:
        correlation_id = kwargs.get("correlation_id")
        opportunities: list[TenderOpportunity] = []
        filters = await self.client.get_filters(correlation_id=correlation_id)
        for provider_filter in filters.filtros:
            summaries = await self._new_bulletins(
                provider_filter.id, checkpoint_id=None, correlation_id=correlation_id
            )
            for summary in reversed(summaries):
                bulletin = await self.client.get_bulletin(summary.id, correlation_id=correlation_id)
                opportunities.extend(
                    map_tender(row.model_dump(mode="json"), base_url=self.client.settings.base_url)
                    for row in bulletin.licitacoes
                )
        return opportunities

    async def get_opportunity(self, external_id: str) -> TenderOpportunity:
        result = await self.find_opportunity(external_id)
        if result is None:
            raise ConlicitacaoUnsupportedOperation(
                "Licitação não encontrada nos boletins recentes consultados."
            )
        return result.opportunity

    async def find_opportunity(
        self,
        external_id: str,
        *,
        correlation_id: str | None = None,
        max_bulletins: int = 30,
    ) -> ConlicitacaoLookupResult | None:
        """Locate a tender by scanning the newest provider bulletins.

        The provider does not document a direct bidding lookup endpoint. Keep
        this search bounded so a typo cannot fan out into the full history.
        """
        try:
            target_id = int(external_id)
        except (TypeError, ValueError) as exc:
            raise ConlicitacaoUnsupportedOperation(
                "O número ConLicitação deve ser um inteiro positivo."
            ) from exc
        if target_id <= 0:
            raise ConlicitacaoUnsupportedOperation(
                "O número ConLicitação deve ser um inteiro positivo."
            )

        limit = max(1, min(int(max_bulletins), 100))
        filters = await self.client.get_filters(correlation_id=correlation_id)
        candidates: list[tuple[int, ConlicitacaoBulletinSummary]] = []
        for provider_filter in filters.filtros:
            response = await self.client.list_bulletins(
                provider_filter.id,
                page=1,
                per_page=limit,
                order="desc",
                correlation_id=correlation_id,
            )
            candidates.extend((provider_filter.id, row) for row in response.boletins)

        candidates.sort(
            key=lambda item: item[1].datahora_fechamento or "",
            reverse=True,
        )
        for filter_id, summary in candidates[:limit]:
            bulletin = await self.client.get_bulletin(
                summary.id, correlation_id=correlation_id
            )
            for row in bulletin.licitacoes:
                if row.id != target_id:
                    continue
                return ConlicitacaoLookupResult(
                    filter_id=filter_id,
                    bulletin_id=summary.id,
                    bulletin_number=summary.numero_edicao,
                    bulletin_closed_at=summary.datahora_fechamento,
                    opportunity=map_tender(
                        row.model_dump(mode="json"),
                        base_url=self.client.settings.base_url,
                    ),
                )
        return None

    async def get_documents(self, external_id: str) -> list[TenderDocument]:
        raise ConlicitacaoUnsupportedOperation(
            "Os documentos são fornecidos no payload do boletim, não por endpoint próprio."
        )

    async def start_monitoring(self, external_id: str, user_id: int) -> dict[str, Any]:
        return await self.client.start_monitoring(int(external_id), user_id)

    async def stop_monitoring(self, external_id: str, user_id: int) -> dict[str, Any]:
        return await self.client.stop_monitoring(int(external_id), user_id)

    async def get_monitored_tenders(self, **kwargs: Any) -> dict[str, Any]:
        return await self.client.get_monitored_biddings(**kwargs)

    async def get_messages(self, external_id: str, **kwargs: Any) -> dict[str, Any]:
        return await self.client.get_messages(int(external_id), **kwargs)

    async def sync(self, tenant_id: int, *, correlation_id: str) -> TenderSyncResult:
        if self.repository is None:
            raise RuntimeError("Sincronização exige um TenderRepository.")
        result = TenderSyncResult(provider=self.name, tenant_id=tenant_id)
        filters = await self.client.get_filters(correlation_id=correlation_id)
        result.filters_seen = len(filters.filtros)

        for provider_filter in filters.filtros:
            filter_id = str(provider_filter.id)
            checkpoint = self.repository.checkpoint(self.name, filter_id)
            checkpoint_id = checkpoint.last_bulletin_id if checkpoint else None
            summaries = await self._new_bulletins(
                provider_filter.id,
                checkpoint_id=checkpoint_id,
                correlation_id=correlation_id,
            )
            for summary in reversed(summaries):
                bulletin = await self.client.get_bulletin(summary.id, correlation_id=correlation_id)
                for row in bulletin.licitacoes:
                    opportunity = map_tender(
                        row.model_dump(mode="json"), base_url=self.client.settings.base_url
                    )
                    _, created = self.repository.upsert(opportunity)
                    if created:
                        result.tenders_imported += 1
                        metrics.TENDERS_IMPORTED.labels(self.name).inc()
                    else:
                        result.tenders_updated += 1
                        result.tenders_deduplicated += 1
                        metrics.TENDERS_DEDUPLICATED.labels(self.name).inc()
                self.repository.advance_checkpoint(
                    self.name,
                    filter_id,
                    str(summary.id),
                    parse_provider_datetime(summary.datahora_fechamento),
                )
                self.repository.commit()
                result.bulletins_processed += 1

        metrics.LAST_SYNC_SUCCESS.labels(str(tenant_id)).set(time.time())
        return result

    async def _new_bulletins(
        self,
        filter_id: int,
        *,
        checkpoint_id: str | None,
        correlation_id: str | None,
    ) -> list[ConlicitacaoBulletinSummary]:
        found: list[ConlicitacaoBulletinSummary] = []
        for page in range(1, self.max_pages + 1):
            response = await self.client.list_bulletins(
                filter_id,
                page=page,
                per_page=100,
                order="desc",
                correlation_id=correlation_id,
            )
            if not response.boletins:
                break
            reached_checkpoint = False
            for summary in response.boletins:
                if checkpoint_id is not None and str(summary.id) == checkpoint_id:
                    reached_checkpoint = True
                    break
                found.append(summary)
            if reached_checkpoint or len(response.boletins) < 100:
                break
            total = response.filtro.get("total_boletins")
            if isinstance(total, int) and page * 100 >= total:
                break
        return found
