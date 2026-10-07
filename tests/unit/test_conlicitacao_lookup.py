from types import SimpleNamespace

import pytest

from app.integrations.conlicitacao.exceptions import ConlicitacaoUnsupportedOperation
from app.integrations.conlicitacao.schemas import (
    ConlicitacaoBulletin,
    ConlicitacaoBulletinsResponse,
    ConlicitacaoFilter,
    ConlicitacaoFiltersResponse,
)
from app.integrations.conlicitacao.service import ConlicitacaoService


def _tender(tender_id: int) -> dict:
    return {
        "id": tender_id,
        "edital": "PE/20/2026",
        "objeto": "Aquisição de equipamentos de informática",
        "orgao": {"nome": "Prefeitura Municipal", "cidade": "Apiacás", "uf": "MT"},
        "documento": [{"filename": "edital.pdf", "url": "/arquivos/edital.pdf"}],
    }


class FakeClient:
    def __init__(self) -> None:
        self.settings = SimpleNamespace(base_url="https://provider.example.test")
        self.requested_bulletins: list[int] = []

    async def get_filters(self, **_kwargs):
        return ConlicitacaoFiltersResponse(
            filtros=[ConlicitacaoFilter(id=10, descricao="Tecnologia")]
        )

    async def list_bulletins(self, *_args, **_kwargs):
        return ConlicitacaoBulletinsResponse.model_validate(
            {
                "boletins": [
                    {"id": 101, "numero_edicao": 2, "datahora_fechamento": "2026-10-07T13:00:00"},
                    {"id": 100, "numero_edicao": 1, "datahora_fechamento": "2026-10-07T09:00:00"},
                ]
            }
        )

    async def get_bulletin(self, bulletin_id: int, **_kwargs):
        self.requested_bulletins.append(bulletin_id)
        rows = [_tender(999)] if bulletin_id == 101 else [_tender(19399420)]
        return ConlicitacaoBulletin.model_validate({"licitacoes": rows})


def _run_immediate(coroutine):
    """Drive fake-I/O coroutines without creating a Windows socket event loop."""
    try:
        coroutine.send(None)
    except StopIteration as completed:
        return completed.value
    raise AssertionError("The fake client unexpectedly yielded pending I/O")


def test_lookup_finds_tender_and_preserves_bulletin_provenance():
    client = FakeClient()

    result = _run_immediate(
        ConlicitacaoService(client).find_opportunity(
            "19399420", max_bulletins=30, correlation_id="corr-1"
        )
    )

    assert result is not None
    assert result.filter_id == 10
    assert result.bulletin_id == 100
    assert result.bulletin_number == 1
    assert result.opportunity.external_id == "19399420"
    assert result.opportunity.documents[0].url == "https://provider.example.test/arquivos/edital.pdf"
    assert client.requested_bulletins == [101, 100]


def test_lookup_respects_bulletin_limit():
    client = FakeClient()

    result = _run_immediate(
        ConlicitacaoService(client).find_opportunity(
            "19399420", max_bulletins=1
        )
    )

    assert result is None
    assert client.requested_bulletins == [101]


def test_lookup_rejects_invalid_external_id():
    with pytest.raises(ConlicitacaoUnsupportedOperation):
        _run_immediate(ConlicitacaoService(FakeClient()).find_opportunity("invalid"))
