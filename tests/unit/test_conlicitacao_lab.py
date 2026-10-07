import asyncio
from types import SimpleNamespace

from app.integrations.conlicitacao.exceptions import ConlicitacaoAPIError
from app.integrations.conlicitacao.lab import (
    analyze_follow_up,
    find_monitored,
    summarize_bulletin,
    trace_bidding,
)
from app.integrations.conlicitacao.schemas import (
    ConlicitacaoBulletin,
    ConlicitacaoBulletinsResponse,
    ConlicitacaoFilter,
    ConlicitacaoFiltersResponse,
)

SIGNED_URL = "/boletim_web/public/api/download?auth=eyJ.secret.token"


def _tender(situacao="NOVA", valor=4316335.47, **extra):
    return {
        "id": 19399420,
        "orgao": {"nome": "Prefeitura Municipal de Apiacás", "codigo": "", "cidade": "Apiacás",
                  "uf": "MT", "endereco": "", "telefone": [], "site": ""},
        "objeto": "Aquisição de equipamentos de informática",
        "situacao": situacao,
        "datahora_abertura": "",
        "datahora_documento": "2026-10-07 08:00:00",
        "edital": "PE/20/2026",
        "documento": [{"filename": "edital.zip", "url": SIGNED_URL}],
        "item": "",
        "preco_edital": 0.0,
        "valor_estimado": valor,
        "has_electronic_trading": True,
        **extra,
    }


FOLLOW_UP = {
    "id": 8958501,
    "licitacao_id": 19399420,
    "orgao": {"nome": "Prefeitura", "cidade": "Caraguatatuba", "uf": "SP"},
    "sintese": (
        "EXTRATO DE HOMOLOGAÇÃO\r\nPregão Eletrônico nº 43/2020\r\n"
        "Adjudicada: RODONAVES CAMINHOES COMERCIO E SERVICOS LTDA - Item 01 - "
        "Valor: R$ 1.878.000,00 CNPJ 12.345.678/0001-90"
    ),
    "data_fonte": "2020-11-11",
}


def test_follow_up_analysis_extracts_outcome_winner_and_value():
    analysis = analyze_follow_up(FOLLOW_UP["sintese"])

    assert "homologacao" in analysis["kinds"]
    assert "adjudicacao" in analysis["kinds"]
    assert analysis["companies"] == ["RODONAVES CAMINHOES COMERCIO E SERVICOS LTDA"]
    assert analysis["cnpjs"] == ["12.345.678/0001-90"]
    assert analysis["max_value"] == 1878000.0


def test_follow_up_analysis_tolerates_empty_text():
    assert analyze_follow_up(None) == {
        "kinds": [], "companies": [], "cnpjs": [], "values": [], "max_value": None,
    }


def test_bulletin_summary_hides_signed_urls_and_reports_fill_rates():
    bulletin = ConlicitacaoBulletin.model_validate(
        {"boletim": {"id": 1}, "licitacoes": [_tender(), _tender(valor=0.0) | {"id": 2}],
         "acompanhamentos": [FOLLOW_UP]}
    )

    summary = summarize_bulletin(bulletin)

    assert "auth=" not in repr(summary)
    assert summary["licitacoes"][0]["documentos"] == [{"index": 0, "filename": "edital.zip"}]
    assert summary["licitacoes"][0]["has_electronic_trading"] is True
    rates = summary["qualidade"]["tenders"]
    assert rates["valor_estimado (> 0)"] == {"filled": 1, "total": 2, "pct": 50.0}
    assert rates["preco_edital (> 0)"]["filled"] == 0
    assert summary["acompanhamentos"][0]["licitacao_no_boletim"] is True


class FakeClient:
    def __init__(self, fail_bulletin=None):
        self.fail_bulletin = fail_bulletin

    async def get_filters(self, **_):
        return ConlicitacaoFiltersResponse(filtros=[ConlicitacaoFilter(id=10)])

    async def list_bulletins(self, *_args, **_):
        return ConlicitacaoBulletinsResponse.model_validate({"boletins": [
            {"id": 3, "numero_edicao": 3, "datahora_fechamento": "2026-10-07 13:00:00 -03:00"},
            {"id": 2, "numero_edicao": 2, "datahora_fechamento": "2026-10-07 09:45:00 -03:00"},
            {"id": 1, "numero_edicao": 1, "datahora_fechamento": "2026-10-06 18:30:00 -03:00"},
        ]})

    async def get_bulletin(self, bulletin_id, **_):
        if bulletin_id == self.fail_bulletin:
            raise ConlicitacaoAPIError(502, "timeout")
        rows = {1: [_tender()], 2: [_tender(situacao="PRORROGADA")], 3: []}[bulletin_id]
        follow_ups = [FOLLOW_UP] if bulletin_id == 3 else []
        return ConlicitacaoBulletin.model_validate(
            {"licitacoes": rows, "acompanhamentos": follow_ups}
        )

    async def get_monitored_biddings(self, page, **_):
        return {"electronics_trading": [{"bidding_id": 19399420, "id": 7}], "total_pages": 1}


def test_trace_orders_appearances_and_reports_field_changes():
    result = asyncio.run(trace_bidding(FakeClient(), 19399420, max_bulletins=10))

    assert result["found"] is True
    assert [a["bulletin_id"] for a in result["appearances"]] == [1, 2]
    assert result["appearances"][1]["changes"] == [
        {"field": "situacao", "before": "NOVA", "after": "PRORROGADA"}
    ]
    assert result["latest"]["situacao"] == "PRORROGADA"
    assert result["follow_ups"][0]["bulletin_id"] == 3
    assert "auth=" not in repr(result)


def test_trace_keeps_partial_results_when_a_bulletin_fails():
    result = asyncio.run(trace_bidding(FakeClient(fail_bulletin=2), 19399420))

    assert result["bulletins_scanned"] == 2
    assert result["errors"] == [{"bulletin_id": 2, "error": "timeout"}]
    assert [a["bulletin_id"] for a in result["appearances"]] == [1]


def test_find_monitored_matches_bidding_id():
    row = asyncio.run(find_monitored(FakeClient(), 19399420))
    assert row == {"bidding_id": 19399420, "id": 7}
    assert asyncio.run(find_monitored(FakeClient(), 1)) is None


def test_document_download_rejects_foreign_hosts():
    from app.integrations.conlicitacao.client import ConlicitacaoClient, ConlicitacaoSettings
    from pydantic import SecretStr

    client = ConlicitacaoClient(
        ConlicitacaoSettings(enabled=True, token=SecretStr("t"), base_url="https://provider.test"),
        client=SimpleNamespace(),
    )
    try:
        asyncio.run(client.download_document("https://evil.test/x", max_bytes=10))
    except ConlicitacaoAPIError as exc:
        assert exc.status_code == 502
    else:
        raise AssertionError("foreign host must be rejected")


def test_document_download_follows_storage_redirect_without_token():
    import httpx
    from app.integrations.conlicitacao.client import ConlicitacaoClient, ConlicitacaoSettings
    from pydantic import SecretStr

    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.host, request.headers.get("x-auth-token")))
        if request.url.host == "provider.test":
            return httpx.Response(302, headers={"Location": "https://storage.test/f.zip"})
        return httpx.Response(200, content=b"PK", headers={"Content-Type": "application/zip"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = ConlicitacaoClient(
                ConlicitacaoSettings(enabled=True, token=SecretStr("t"), base_url="https://provider.test"),
                client=http,
            )
            return await client.download_document(SIGNED_URL, max_bytes=10)

    content, content_type = asyncio.run(run())

    assert content == b"PK" and content_type == "application/zip"
    assert seen == [("provider.test", "t"), ("storage.test", None)]


def test_httpx_request_logs_are_silenced_to_protect_signed_urls():
    import logging
    import app.integrations.conlicitacao.client  # noqa: F401

    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)
