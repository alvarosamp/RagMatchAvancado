from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urljoin

from app.integrations.conlicitacao.schemas import ConlicitacaoTender
from app.integrations.tenders.schemas import TenderDocument, TenderOpportunity

PROVIDER = "conlicitacao"


def map_tender(payload: dict[str, Any], *, base_url: str) -> TenderOpportunity:
    source = ConlicitacaoTender.model_validate(payload)
    public_body = source.orgao
    edital = _clean(source.edital)
    body_name = _clean(public_body.nome)
    title_parts = [part for part in (f"Edital {edital}" if edital else None, body_name) if part]
    title = " - ".join(title_parts) or _clip(_clean(source.objeto), 500) or f"Licitação {source.id}"

    documents = [
        TenderDocument(filename=document.filename, url=urljoin(base_url.rstrip("/") + "/", document.url))
        for document in source.documento
        if document.url
    ]
    return TenderOpportunity(
        provider=PROVIDER,
        external_id=str(source.id),
        title=title,
        object=_clean(source.objeto),
        status=_clean(source.situacao),
        edital_number=edital,
        process_number=_clean(source.processo),
        uasg=_clean(public_body.codigo),
        public_body_name=body_name,
        public_body_city=_clean(public_body.cidade),
        public_body_state=(_clean(public_body.uf) or "").upper() or None,
        opening_at=parse_provider_datetime(source.datahora_abertura),
        proposal_deadline_at=parse_provider_datetime(
            source.datahora_documento or source.datahora_prazo
        ),
        estimated_value=_decimal(source.valor_estimado),
        source_url=_clean(public_body.site),
        documents=documents,
        raw_payload=dict(payload),
    )


def parse_provider_datetime(value: str | None) -> datetime | None:
    value = _clean(value)
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(value, pattern)  # noqa: DTZ007 - provider local time
                break
            except ValueError:
                continue
        else:
            return None
    # The bidding timestamps documented without an offset are local official
    # times. Preserve them as published rather than inventing a timezone.
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _clip(value: str | None, limit: int) -> str | None:
    return value[:limit] if value else None


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None
