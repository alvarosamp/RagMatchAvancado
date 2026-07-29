from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import requests


CONSULTA_BASE_URL = os.getenv("PNCP_CONSULTA_BASE_URL", "https://pncp.gov.br/api/consulta/v1")
PNCP_BASE_URL = os.getenv("PNCP_BASE_URL", "https://pncp.gov.br/api/pncp/v1")

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; EditalMatcher-Radar/1.0)",
}

_PNCP_ID_PATTERN = re.compile(r"^(\d{14})-(\d+)-(\d+)/(\d{4})$")


@dataclass(frozen=True)
class ParsedPncpId:
    raw: str
    cnpj: str
    tipo: int
    sequencial: int
    ano: int


def parse_pncp_id(raw: str) -> ParsedPncpId | None:
    match = _PNCP_ID_PATTERN.match((raw or "").strip())
    if not match:
        return None
    return ParsedPncpId(
        raw=raw.strip(),
        cnpj=match.group(1),
        tipo=int(match.group(2)),
        sequencial=int(match.group(3)),
        ano=int(match.group(4)),
    )


def search_publications(
    *,
    texto: str | None = None,
    cnpj: str | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
    pagina: int = 1,
    tamanho_pagina: int = 20,
    modalidade: str | None = None,
    propostas_abertas: bool = False,
    max_pages: int = 1,
) -> dict[str, Any]:
    start, end = _date_range(data_inicio, data_fim)
    endpoint = "contratacoes/proposta" if propostas_abertas else "contratacoes/publicacao"
    params: dict[str, Any] = {
        "dataInicial": start.strftime("%Y%m%d"),
        "dataFinal": end.strftime("%Y%m%d"),
        "pagina": max(1, pagina),
        "tamanhoPagina": min(max(10, tamanho_pagina), 50),
    }
    modalidade_codigo = _modalidade_codigo(modalidade)
    if modalidade_codigo is None and not propostas_abertas:
        # O endpoint /publicacao exige modalidade. Pregao e o default mais util
        # para a operacao de TIC e evita erro 400 quando o filtro vier vazio.
        modalidade_codigo = 6
    if modalidade_codigo is not None:
        params["codigoModalidadeContratacao"] = modalidade_codigo

    rows: list[dict[str, Any]] = []
    payload: dict[str, Any] = {}
    pages_to_scan = max(1, min(max_pages, 8))
    for offset in range(pages_to_scan):
        params["pagina"] = max(1, pagina + offset)
        response = requests.get(
            f"{CONSULTA_BASE_URL}/{endpoint}",
            params=params,
            headers=HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        current_payload = response.json()
        if isinstance(current_payload, dict):
            payload = current_payload
        current_rows = _extract_rows(current_payload)
        rows.extend(current_rows)
        if not current_rows or (isinstance(current_payload, dict) and current_payload.get("paginasRestantes", 0) <= 0):
            break
    if cnpj:
        digits = re.sub(r"\D", "", cnpj)
        rows = [
            row for row in rows
            if digits in str(row.get("orgaoEntidade", {}).get("cnpj", "") or row.get("cnpjOrgao", ""))
        ]
    if texto:
        rows = [row for row in rows if _matches_text(row, texto)]

    normalized = [normalize_notice(row) for row in rows]
    return {
        "items": normalized,
        "total": payload.get("totalRegistros", len(normalized)) if isinstance(payload, dict) else len(normalized),
        "pagina": payload.get("numeroPagina", pagina) if isinstance(payload, dict) else pagina,
        "paginas_restantes": payload.get("paginasRestantes", 0) if isinstance(payload, dict) else 0,
        "paginas_varridas": min(pages_to_scan, max(1, (payload.get("numeroPagina", pagina) - pagina + 1) if isinstance(payload, dict) else 1)),
        "source": "pncp",
    }


def get_purchase_detail(id_pncp: str) -> dict[str, Any]:
    parsed = parse_pncp_id(id_pncp)
    if not parsed:
        raise ValueError("ID PNCP invalido.")
    response = requests.get(
        f"{PNCP_BASE_URL}/orgaos/{parsed.cnpj}/compras/{parsed.ano}/{parsed.sequencial}",
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return normalize_notice(response.json())


def list_purchase_files(id_pncp: str) -> list[dict[str, Any]]:
    parsed = parse_pncp_id(id_pncp)
    if not parsed:
        raise ValueError("ID PNCP invalido.")
    response = requests.get(
        f"{PNCP_BASE_URL}/orgaos/{parsed.cnpj}/compras/{parsed.ano}/{parsed.sequencial}/arquivos",
        headers=HEADERS,
        timeout=30,
    )
    if response.status_code in (204, 404):
        return []
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "dados", "arquivos", "documentos"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


def list_purchase_items(id_pncp: str) -> list[dict[str, Any]]:
    parsed = parse_pncp_id(id_pncp)
    if not parsed:
        raise ValueError("ID PNCP invalido.")
    response = requests.get(
        f"{PNCP_BASE_URL}/orgaos/{parsed.cnpj}/compras/{parsed.ano}/{parsed.sequencial}/itens",
        headers=HEADERS,
        timeout=30,
    )
    if response.status_code in (204, 404):
        return []
    response.raise_for_status()
    payload = response.json()
    rows = _extract_rows(payload)
    if not rows and isinstance(payload, list):
        rows = payload
    return [normalize_purchase_item(row) for row in rows if isinstance(row, dict)]


def download_file(url: str) -> bytes:
    response = requests.get(url, headers=HEADERS, timeout=60)
    response.raise_for_status()
    return response.content


def normalize_purchase_item(row: dict[str, Any]) -> dict[str, Any]:
    description = (
        row.get("descricao")
        or row.get("descricaoItem")
        or row.get("descricaoDetalhada")
        or row.get("objeto")
        or row.get("nome")
    )
    quantity = row.get("quantidade") or row.get("quantidadeItem") or row.get("qtd")
    unit_value = row.get("valorUnitarioEstimado") or row.get("valorUnitario") or row.get("valorUnitarioHomologado")
    total_value = row.get("valorTotal") or row.get("valorTotalEstimado") or row.get("valorTotalHomologado")
    return {
        **row,
        "numero_item": row.get("numeroItem") or row.get("numero") or row.get("item"),
        "descricao": description,
        "quantidade": quantity,
        "unidade": row.get("unidadeMedida") or row.get("unidade") or row.get("siglaUnidadeMedida"),
        "valor_unitario": unit_value,
        "valor_total": total_value,
        "criterio_julgamento": row.get("criterioJulgamentoNome") or row.get("criterioJulgamento"),
        "categoria": row.get("categoriaItemCatalogo") or row.get("tipoItem") or row.get("materialOuServico"),
        "beneficio": row.get("tipoBeneficioNome") or row.get("beneficio"),
    }


def normalize_notice(row: dict[str, Any]) -> dict[str, Any]:
    orgao = row.get("orgaoEntidade") or row.get("orgao_entidade") or {}
    unidade = row.get("unidadeOrgao") or row.get("unidade_orgao") or {}
    numero = row.get("numeroControlePNCP") or row.get("numero_controle_pncp") or row.get("id_pncp")
    return {
        **row,
        "id_pncp": numero,
        "numero_controle": numero,
        "objeto": row.get("objetoCompra") or row.get("objeto") or row.get("descricaoObjeto"),
        "modalidade": row.get("modalidadeNome") or row.get("modalidade") or row.get("nomeModalidade"),
        "situacao": row.get("situacaoCompraNome") or row.get("situacao") or row.get("status"),
        "orgao_entidade": {
            "cnpj": orgao.get("cnpj"),
            "nome_razao_social": orgao.get("razaoSocial") or orgao.get("nome") or orgao.get("nomeRazaoSocial"),
        },
        "unidade_orgao": {
            "uf": unidade.get("ufNome") or unidade.get("uf"),
            "municipio": unidade.get("municipioNome") or unidade.get("nomeMunicipio"),
        },
        "data_publicacao_pncp": row.get("dataPublicacaoPncp") or row.get("dataPublicacaoPNCP"),
        "data_encerramento_proposta": row.get("dataEncerramentoProposta"),
        "valor_total_estimado": row.get("valorTotalEstimado") or row.get("valorGlobal"),
        "link_sistema_origem": row.get("linkSistemaOrigem") or row.get("linkProcessoEletronico"),
        "numero_itens": row.get("quantidadeItens") or row.get("numeroItens"),
    }


def _date_range(data_inicio: str | None, data_fim: str | None) -> tuple[date, date]:
    end = _parse_date(data_fim) or date.today()
    start = _parse_date(data_inicio) or (end - timedelta(days=30))
    if start > end:
        start, end = end, start
    return start, end


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return date.fromisoformat(value) if fmt == "%Y-%m-%d" else datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "dados", "content", "items", "resultado"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def _row_text(row: dict[str, Any]) -> str:
    return " ".join(
        str(value).lower()
        for key, value in row.items()
        if key not in {"orgaoEntidade", "unidadeOrgao"} and isinstance(value, (str, int, float))
    )


def _matches_text(row: dict[str, Any], texto: str) -> bool:
    haystack = _row_text(row)
    terms = [
        term
        for term in re.split(r"[,;\s]+", texto.lower().strip())
        if len(term) >= 3
    ]
    if not terms:
        return True
    return any(term in haystack for term in terms)


def _modalidade_codigo(value: str | None) -> int | None:
    if not value:
        return None
    text = value.lower()
    mapping = {
        "pregao": 6,
        "pregão": 6,
        "concorrencia": 4,
        "concorrência": 4,
        "dispensa": 8,
        "inexigibilidade": 9,
        "leilao": 5,
        "leilão": 5,
    }
    for needle, code in mapping.items():
        if needle in text:
            return code
    return None
