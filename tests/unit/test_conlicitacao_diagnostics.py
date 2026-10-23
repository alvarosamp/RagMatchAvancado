from __future__ import annotations

from app.integrations.conlicitacao.diagnostics import (
    describe_shape,
    run_readonly_diagnostics,
)
from app.integrations.conlicitacao.schemas import (
    ConlicitacaoBulletin,
    ConlicitacaoBulletinsResponse,
    ConlicitacaoBulletinSummary,
    ConlicitacaoFilter,
    ConlicitacaoFiltersResponse,
)


class FakeConlicitacaoClient:
    async def get_filters(self, **_kwargs):
        return ConlicitacaoFiltersResponse(
            cliente={"id": 9, "razao_social": "Empresa sigilosa"},
            filtros=[ConlicitacaoFilter(id=12, descricao="Filtro sigiloso")],
        )

    async def list_bulletins(self, filter_id, **_kwargs):
        assert filter_id == 12
        return ConlicitacaoBulletinsResponse(
            boletins=[ConlicitacaoBulletinSummary(id=34, filtro_id=filter_id)]
        )

    async def get_bulletin(self, bulletin_id, **_kwargs):
        assert bulletin_id == 34
        return ConlicitacaoBulletin(
            licitacoes=[
                {
                    "id": 56,
                    "objeto": "Conteúdo sigiloso do edital",
                    "orgao": {"nome": "Órgão sigiloso"},
                }
            ]
        )

    async def get_monitored_biddings(self, **_kwargs):
        return {"items": [{"bidding_id": 56, "status": "active"}]}

    async def get_messages(self, bidding_id, **_kwargs):
        assert bidding_id == 56
        return {"messages": [{"message": "Mensagem sigilosa"}]}

    async def get_users(self, **_kwargs):
        return {"users": [{"id": 78, "email": "sigiloso@example.com"}]}


def run_immediate(coroutine):
    """Drive fake-only coroutines without opening a Windows event-loop socket."""
    try:
        coroutine.send(None)
    except StopIteration as completed:
        return completed.value
    raise AssertionError("The fake diagnostic unexpectedly performed blocking I/O")


def test_describe_shape_reports_structure_without_values():
    result = describe_shape({"items": [{"id": 10, "name": "segredo"}]})

    assert result["fields"]["items"]["count"] == 1
    assert result["fields"]["items"]["items"]["fields"]["id"] == "integer"
    assert "segredo" not in str(result)


def test_readonly_diagnostics_exercises_all_get_endpoints_without_leaking_values():
    result = run_immediate(run_readonly_diagnostics(FakeConlicitacaoClient()))

    assert result["summary"] == {"total": 6, "completed": 6, "failed": 0, "skipped": 0}
    assert [item["ok"] for item in result["results"]] == [True] * 6
    assert result["results"][0]["counts"] == {"filtros": 1}
    assert result["results"][2]["counts"] == {"licitacoes": 1, "acompanhamentos": 0}
    serialized = str(result)
    assert "Empresa sigilosa" not in serialized
    assert "Conteúdo sigiloso" not in serialized
    assert "sigiloso@example.com" not in serialized


def test_readonly_diagnostics_skips_dependent_calls_when_collections_are_empty():
    class EmptyClient(FakeConlicitacaoClient):
        async def get_filters(self, **_kwargs):
            return ConlicitacaoFiltersResponse()

        async def get_monitored_biddings(self, **_kwargs):
            return {"items": []}

    result = run_immediate(run_readonly_diagnostics(EmptyClient()))

    assert result["summary"] == {"total": 6, "completed": 3, "failed": 0, "skipped": 3}
