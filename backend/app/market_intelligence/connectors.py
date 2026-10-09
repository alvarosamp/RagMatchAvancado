"""Read-only external extractors with bounded pages and account-wide pacing."""

import hashlib
import hmac
import time
from datetime import date, timedelta
from typing import ClassVar

import requests

from app.integrations.bling.client import BlingAPIError
from app.services.pncp_client import CONSULTA_BASE_URL, PNCP_BASE_URL, parse_pncp_id


def verify_bling_signature(body, signature, secret):
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


class ReadClient:
    def __init__(self, session=None, sleeper=time.sleep):
        self.session = session or requests.Session()
        self.sleep = sleeper

    def get(self, url, params=None):
        for attempt in range(5):
            response = self.session.get(
                url,
                params=params,
                timeout=(10, 45),
                headers={
                    "Accept": "application/json",
                    "User-Agent": "RagMatch-MarketIntelligence/1",
                },
            )
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 4:
                    response.raise_for_status()
                wait = response.headers.get("Retry-After", "")
                self.sleep(min(60, int(wait) if wait.isdigit() else 2**attempt))
                continue
            if response.status_code == 204:
                return []
            response.raise_for_status()
            return response.json()
        raise RuntimeError("Fonte indisponível após retentativas.")

    def pages(self, url, params=None, page_size=100, max_pages=10000):
        for page in range(1, max_pages + 1):
            data = self.get(
                url, {**(params or {}), "pagina": page, "tamanhoPagina": page_size}
            )
            rows = data if isinstance(data, list) else data.get("data", [])
            if not isinstance(rows, list):
                raise TypeError("A fonte retornou uma página inválida.")
            yield from rows
            if (
                not rows
                or (
                    isinstance(data, dict)
                    and (data.get("empty") is True or data.get("paginasRestantes") == 0)
                )
                or len(rows) < page_size
            ):
                return
        raise ValueError(
            "Limite de páginas atingido; carga incompleta não será publicada."
        )


class BlingReader:
    RESOURCES: ClassVar[dict[str, str]] = {
        "product": "/produtos",
        "supplier": "/contatos",
        "product_supplier": "/produtos/fornecedores",
        "purchase": "/pedidos/compras",
        "sale": "/pedidos/vendas",
        "proposal": "/propostas/comerciais",
    }

    def __init__(self, client, sleeper=time.sleep):
        self.client, self.sleep = client, sleeper
        self.last_request = 0.0

    def get(self, path, params=None):
        # All resources of this account share one source lock and pacing budget.
        for attempt in range(5):
            delay = 0.4 - (time.monotonic() - self.last_request)
            if delay > 0:
                self.sleep(delay)
            self.last_request = time.monotonic()
            try:
                return self.client._request("GET", path, params=params or {})
            except BlingAPIError as error:
                if error.status_code not in {429, 500, 502, 503, 504} or attempt == 4:
                    raise
                self.sleep(min(60, 2**attempt))
        raise RuntimeError("Bling indisponível.")

    def records(self, resource, params=None, max_pages=10000):
        path = self.RESOURCES[resource]
        for page in range(1, max_pages + 1):
            data = self.get(
                path, {**(params or {}), "pagina": page, "limite": 100}
            ).get("data")
            if not isinstance(data, list):
                raise TypeError("Página Bling inválida.")
            for summary in data:
                if not isinstance(summary, dict) or "id" not in summary:
                    raise ValueError("Registro Bling sem identidade.")
                detail = self.get(f"{path}/{summary['id']}").get("data")
                if not isinstance(detail, dict):
                    raise TypeError("Detalhe Bling inválido.")
                yield detail
            if len(data) < 100:
                return
        raise ValueError("Limite Bling atingido; checkpoint não avançado.")

    def stock(self, product_ids):
        for offset in range(0, len(product_ids), 100):
            result = self.get(
                "/estoques/saldos",
                {"idsProdutos[]": product_ids[offset : offset + 100]},
            ).get("data")
            if not isinstance(result, list):
                raise TypeError("Saldo de estoque inválido.")
            yield from result


def date_windows(start, end, days=30):
    cursor = date.fromisoformat(str(start))
    end = date.fromisoformat(str(end))
    if cursor > end:
        raise ValueError("Período invertido.")
    while cursor <= end:
        stop = min(end, cursor + timedelta(days=days - 1))
        yield cursor, stop
        cursor = stop + timedelta(days=1)


def pncp_records(reader, start, end, modalities=(6,), updated=True):
    """Full item-result detail, not contract totals presented as unit prices."""
    endpoint = "contratacoes/atualizacao" if updated else "contratacoes/publicacao"
    for begin, finish in date_windows(start, end):
        for modality in modalities:
            params = {
                "dataInicial": begin.strftime("%Y%m%d"),
                "dataFinal": finish.strftime("%Y%m%d"),
                "codigoModalidadeContratacao": modality,
            }
            for notice in reader.pages(
                f"{CONSULTA_BASE_URL}/{endpoint}", params, page_size=50
            ):
                parsed = parse_pncp_id(notice.get("numeroControlePNCP", ""))
                if not parsed:
                    raise ValueError("Contratação PNCP sem identificador válido.")
                path = f"{PNCP_BASE_URL}/orgaos/{parsed.cnpj}/compras/{parsed.ano}/{parsed.sequencial}"
                yield "notice", notice["numeroControlePNCP"], notice
                for item in reader.pages(path + "/itens", page_size=500):
                    item_number = item.get("numeroItem")
                    if item_number is None:
                        raise ValueError("Item PNCP sem número.")
                    item_key = f"{notice['numeroControlePNCP']}:{item_number}"
                    yield "demand", item_key, {"notice": notice, "item": item}
                    for result in reader.pages(
                        f"{path}/itens/{item_number}/resultados", page_size=500
                    ):
                        result_id = result.get("sequencialResultado")
                        if result_id is None:
                            raise ValueError("Resultado PNCP sem sequencial.")
                        yield (
                            "award",
                            f"{item_key}:{result_id}",
                            {"notice": notice, "item": item, "result": result},
                        )
        # Contract totals are stored as raw evidence, never as item price facts.
        for contract in reader.pages(
            f"{CONSULTA_BASE_URL}/contratos/atualizacao",
            {
                "dataInicial": begin.strftime("%Y%m%d"),
                "dataFinal": finish.strftime("%Y%m%d"),
            },
            page_size=50,
        ):
            if not contract.get("numeroControlePNCP"):
                raise ValueError("Contrato PNCP sem identidade.")
            yield "contract", contract["numeroControlePNCP"], contract


def ibge_index(reader, table, variable, start_month, end_month):
    # Only aggregate-series API on the configured IBGE table/variable.
    if table not in {1737, 6903} or variable <= 0:
        raise ValueError("Tabela IBGE não autorizada para índices.")
    data = reader.get(
        f"https://servicodados.ibge.gov.br/api/v3/agregados/{table}/periodos/{start_month}-{end_month}/variaveis/{variable}",
        {"localidades": "N1[all]"},
    )
    for variable_data in data:
        for result in variable_data.get("resultados", []):
            for series in result.get("series", []):
                for month, value in series.get("serie", {}).items():
                    yield {
                        "id": f"{table}:{variable}:{month}",
                        "month": month,
                        "value": value,
                        "table": table,
                        "variable": variable,
                        "unit": variable_data.get("unidade"),
                    }
