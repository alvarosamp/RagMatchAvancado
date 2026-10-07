"""Evaluation helpers for the ConLicitação trial.

Everything here is read-only against the provider and returns real values to
an administrator so the data quality can be judged. Signed document URLs are
the one exception: they embed the client token, so only an index is exposed
and downloads are proxied by the API.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections import Counter
from typing import Any

from app.integrations.conlicitacao.client import ConlicitacaoClient
from app.integrations.conlicitacao.exceptions import ConlicitacaoError
from app.integrations.conlicitacao.schemas import ConlicitacaoBulletin

TRACKED_FIELDS = (
    "situacao",
    "objeto",
    "datahora_abertura",
    "datahora_documento",
    "datahora_prazo",
    "datahora_retirada",
    "datahora_visita",
    "valor_estimado",
    "preco_edital",
    "edital",
    "processo",
    "observacao",
    "item",
    "has_electronic_trading",
)

FOLLOW_UP_KINDS = (
    ("homologacao", ("homologa",)),
    ("adjudicacao", ("adjudica",)),
    ("resultado", ("resultado", "vencedor", "vencedora")),
    ("ata_registro_precos", ("ata de registro",)),
    ("contrato", ("extrato de contrato", "extrato do contrato", "contrato n")),
    ("revogacao", ("revoga",)),
    ("anulacao", ("anula",)),
    ("deserta", ("desert",)),
    ("fracassada", ("fracassad",)),
    ("suspensao", ("suspens",)),
    ("adiamento", ("adiad", "adiament", "prorroga", "nova data")),
    ("retificacao", ("retifica", "errata")),
    ("impugnacao", ("impugna",)),
    ("esclarecimento", ("esclarecimento",)),
    ("recurso", ("recurso",)),
)

_MONEY = re.compile(r"R\$\s*([\d.]+,\d{2})")
_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_COMPANY = re.compile(
    r"(?:a favor d[ao]s? empresas?|empresa vencedora|vencedora|adjudicad[ao]|"
    r"adjudicat[aá]ri[ao]|contratad[ao]|empresa)\s*[:\-–]?\s*"
    r"([A-ZÀ-Ü0-9][A-ZÀ-Ü0-9&.,\-/ ]{3,120}?(?:LTDA|EIRELI|S/?A|ME|EPP|MEI)\.?)\b",
    re.IGNORECASE,
)


def _filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _money(text: str) -> float | None:
    try:
        return float(text.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def analyze_follow_up(sintese: str | None) -> dict[str, Any]:
    """Best-effort extraction of outcome, winner and values from ``sintese``."""
    text = re.sub(r"\s+", " ", sintese or "").strip()
    lowered = text.casefold()
    kinds = [kind for kind, needles in FOLLOW_UP_KINDS if any(n in lowered for n in needles)]
    values = [v for v in (_money(m) for m in _MONEY.findall(text)) if v is not None]
    companies = list(dict.fromkeys(m.strip(" ,.-") for m in _COMPANY.findall(text)))
    return {
        "kinds": kinds,
        "companies": companies[:5],
        "cnpjs": list(dict.fromkeys(_CNPJ.findall(text)))[:5],
        "values": values[:10],
        "max_value": max(values) if values else None,
    }


def _tender_row(row: dict[str, Any]) -> dict[str, Any]:
    documents = row.get("documento") or []
    if isinstance(documents, str):
        documents = [{"filename": "documento", "url": documents}]
    safe = {key: value for key, value in row.items() if key != "documento"}
    safe["documentos"] = [
        {"index": index, "filename": (doc or {}).get("filename") or f"documento-{index + 1}"}
        for index, doc in enumerate(documents)
        if isinstance(doc, dict) and doc.get("url")
    ]
    return safe


def _rate(rows: list[dict[str, Any]], getter) -> dict[str, Any]:
    total = len(rows)
    filled = sum(1 for row in rows if _filled(getter(row)))
    return {"filled": filled, "total": total, "pct": round(filled * 100 / total, 1) if total else 0.0}


def quality_report(tenders: list[dict[str, Any]], follow_ups: list[dict[str, Any]]) -> dict[str, Any]:
    """Field fill-rates used to judge whether the feed is worth subscribing."""
    orgao = lambda key: (lambda row: (row.get("orgao") or {}).get(key))  # noqa: E731
    tender_rates = {
        "valor_estimado (> 0)": _rate(tenders, lambda r: r.get("valor_estimado")),
        "preco_edital (> 0)": _rate(tenders, lambda r: r.get("preco_edital")),
        "documento": _rate(tenders, lambda r: r.get("documentos")),
        "item": _rate(tenders, lambda r: r.get("item")),
        "observacao": _rate(tenders, lambda r: r.get("observacao")),
        "processo": _rate(tenders, lambda r: r.get("processo")),
        "datahora_abertura": _rate(tenders, lambda r: r.get("datahora_abertura")),
        "datahora_documento": _rate(tenders, lambda r: r.get("datahora_documento")),
        "datahora_prazo": _rate(tenders, lambda r: r.get("datahora_prazo")),
        "orgao.codigo (UASG)": _rate(tenders, orgao("codigo")),
        "orgao.site": _rate(tenders, orgao("site")),
        "orgao.telefone": _rate(tenders, orgao("telefone")),
        "orgao.endereco": _rate(tenders, orgao("endereco")),
        "has_electronic_trading": _rate(tenders, lambda r: r.get("has_electronic_trading") is True),
    }
    analyses = [row.get("analise") or {} for row in follow_ups]
    follow_up_rates = {
        "sintese": _rate(follow_ups, lambda r: r.get("sintese")),
        "licitacao_id": _rate(follow_ups, lambda r: r.get("licitacao_id")),
        "empresa extraída": _rate(analyses, lambda a: a.get("companies")),
        "CNPJ extraído": _rate(analyses, lambda a: a.get("cnpjs")),
        "valor extraído": _rate(analyses, lambda a: a.get("values")),
    }
    return {
        "tenders": tender_rates,
        "follow_ups": follow_up_rates,
        "situacao": Counter(str(r.get("situacao") or "—") for r in tenders).most_common(),
        "uf": Counter(str((r.get("orgao") or {}).get("uf") or "—") for r in tenders).most_common(),
        "follow_up_kinds": Counter(k for a in analyses for k in (a.get("kinds") or ["outros"])).most_common(),
        "total_estimated_value": round(
            sum(float(r.get("valor_estimado") or 0) for r in tenders), 2
        ),
    }


def summarize_bulletin(bulletin: ConlicitacaoBulletin) -> dict[str, Any]:
    tenders = [_tender_row(row.model_dump(mode="json")) for row in bulletin.licitacoes]
    tender_ids = {row["id"] for row in tenders}
    follow_ups = []
    for row in bulletin.acompanhamentos:
        item = dict(row)
        item["analise"] = analyze_follow_up(item.get("sintese"))
        item["licitacao_no_boletim"] = item.get("licitacao_id") in tender_ids
        follow_ups.append(item)
    return {
        "boletim": bulletin.boletim,
        "licitacoes": tenders,
        "acompanhamentos": follow_ups,
        "qualidade": quality_report(tenders, follow_ups),
    }


def _diff(previous: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    changes = []
    for field in TRACKED_FIELDS:
        before, after = previous.get(field), current.get(field)
        if before != after:
            changes.append({"field": field, "before": before, "after": after})
    return changes


async def trace_bidding(
    client: ConlicitacaoClient,
    bidding_id: int,
    *,
    max_bulletins: int = 15,
    concurrency: int = 3,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Find every appearance of a bidding in recent bulletins.

    The API has no lookup by bidding id, but the docs guarantee a stable id
    across bulletins, so scanning recent bulletins reveals how a tender
    evolves (situação, datas, documentos) and which follow-ups it received.
    """
    started = time.perf_counter()
    limit = max(1, min(max_bulletins, 60))
    filters = await client.get_filters(correlation_id=correlation_id)
    candidates: list[tuple[int, Any]] = []
    for provider_filter in filters.filtros:
        response = await client.list_bulletins(
            provider_filter.id, page=1, per_page=limit, order="desc", correlation_id=correlation_id
        )
        candidates.extend((provider_filter.id, row) for row in response.boletins)
    candidates.sort(key=lambda item: item[1].datahora_fechamento or "", reverse=True)
    candidates = candidates[:limit]

    semaphore = asyncio.Semaphore(max(1, concurrency))
    errors: list[dict[str, Any]] = []

    async def load(filter_id: int, summary: Any):
        async with semaphore:
            t0 = time.perf_counter()
            try:
                bulletin = await client.get_bulletin(summary.id, correlation_id=correlation_id)
            except ConlicitacaoError as exc:
                errors.append({"bulletin_id": summary.id, "error": str(exc)})
                return None
            return filter_id, summary, bulletin, round((time.perf_counter() - t0) * 1000, 1)

    loaded = [r for r in await asyncio.gather(*(load(f, s) for f, s in candidates)) if r]

    appearances: list[dict[str, Any]] = []
    follow_ups: list[dict[str, Any]] = []
    latencies = []
    for filter_id, summary, bulletin, latency in loaded:
        latencies.append(latency)
        origin = {
            "filter_id": filter_id,
            "bulletin_id": summary.id,
            "bulletin_number": summary.numero_edicao,
            "bulletin_closed_at": summary.datahora_fechamento,
        }
        for row in bulletin.licitacoes:
            if row.id == bidding_id:
                appearances.append({**origin, "licitacao": _tender_row(row.model_dump(mode="json"))})
        for row in bulletin.acompanhamentos:
            if row.get("licitacao_id") == bidding_id or row.get("id") == bidding_id:
                follow_ups.append(
                    {**origin, **row, "analise": analyze_follow_up(row.get("sintese"))}
                )

    appearances.sort(key=lambda item: item["bulletin_closed_at"] or "")
    follow_ups.sort(key=lambda item: item["bulletin_closed_at"] or "")
    for previous, current in zip(appearances, appearances[1:]):
        current["changes"] = _diff(previous["licitacao"], current["licitacao"])

    return {
        "bidding_id": bidding_id,
        "found": bool(appearances or follow_ups),
        "bulletins_scanned": len(loaded),
        "bulletins_requested": len(candidates),
        "oldest_bulletin_scanned": candidates[-1][1].datahora_fechamento if candidates else None,
        "appearances": appearances,
        "latest": appearances[-1]["licitacao"] if appearances else None,
        "follow_ups": follow_ups,
        "errors": errors,
        "bulletin_latency_ms": {
            "max": max(latencies) if latencies else None,
            "avg": round(sum(latencies) / len(latencies), 1) if latencies else None,
        },
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
    }


async def find_monitored(
    client: ConlicitacaoClient,
    bidding_id: int,
    *,
    max_pages: int = 5,
    correlation_id: str | None = None,
) -> dict[str, Any] | None:
    for page in range(1, max_pages + 1):
        payload = await client.get_monitored_biddings(
            page=page, per_page=50, correlation_id=correlation_id
        )
        for row in payload.get("electronics_trading") or []:
            if row.get("bidding_id") == bidding_id:
                return row
        total_pages = payload.get("total_pages")
        if not isinstance(total_pages, int) or page >= total_pages:
            break
    return None
