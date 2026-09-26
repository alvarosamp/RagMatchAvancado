from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.integrations.conlicitacao.client import ConlicitacaoSettings
from app.integrations.conlicitacao.schemas import (
    ConlicitacaoBulletin,
    ConlicitacaoBulletinsResponse,
    ConlicitacaoFiltersResponse,
)
from app.integrations.conlicitacao.service import ConlicitacaoService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "conlicitacao"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeClient:
    settings = ConlicitacaoSettings(enabled=True, base_url="https://provider.example.test")

    def __init__(self) -> None:
        self.bulletin_calls = 0

    async def get_filters(self, **_):
        return ConlicitacaoFiltersResponse.model_validate(_fixture("filters.json"))

    async def list_bulletins(self, *_args, **_kwargs):
        return ConlicitacaoBulletinsResponse.model_validate(_fixture("bulletins.json"))

    async def get_bulletin(self, *_args, **_kwargs):
        self.bulletin_calls += 1
        return ConlicitacaoBulletin.model_validate(_fixture("bulletin.json"))


class MemoryRepository:
    def __init__(self) -> None:
        self.rows = {}
        self.checkpoints = {}
        self.commits = 0

    def checkpoint(self, provider, external_filter_id):
        value = self.checkpoints.get((provider, external_filter_id))
        return SimpleNamespace(last_bulletin_id=value) if value else None

    def upsert(self, opportunity):
        key = (opportunity.provider, opportunity.external_id)
        created = key not in self.rows
        self.rows[key] = opportunity
        return opportunity, created

    def advance_checkpoint(self, provider, external_filter_id, bulletin_id, _closed_at):
        self.checkpoints[(provider, external_filter_id)] = bulletin_id

    def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_bulletin_becomes_tender_and_second_sync_is_idempotent():
    client = FakeClient()
    repository = MemoryRepository()
    service = ConlicitacaoService(client, repository)

    first = await service.sync(tenant_id=17, correlation_id="first")
    second = await service.sync(tenant_id=17, correlation_id="second")

    assert first.tenders_imported == 1
    assert first.bulletins_processed == 1
    assert second.tenders_imported == 0
    assert second.bulletins_processed == 0
    assert len(repository.rows) == 1
    assert client.bulletin_calls == 1
    assert repository.commits == 1
