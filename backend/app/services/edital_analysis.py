from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class ExtractedEditalItem:
    numero_item: str
    tipo: str | None
    descricao: str
    quantidade: float | None = None
    unidade: str | None = None
    valor_unitario: float | None = None
    valor_total: float | None = None
    marca: str | None = None
    modelo: str | None = None
    fornecedor: str | None = None
    cnpj_fornecedor: str | None = None
    especificacoes: list[str] | None = None
    observacoes: str | None = None


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip(" -\n\t")


def _to_float(value: str | None) -> float | None:
    if not value:
        return None
    text = value.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _infer_type(text: str) -> str | None:
    lowered = text.lower()
    if "switch" in lowered:
        return "switch"
    if "roteador" in lowered or "router" in lowered:
        return "roteador"
    if "gbic" in lowered or "sfp" in lowered:
        return "transceiver"
    if "access point" in lowered or "ap " in lowered:
        return "access point"
    return None


def _extract_specs(text: str) -> list[str]:
    specs: list[str] = []
    patterns = [
        (r"(\d+)\s*(?:portas?|p)\s*(?:rj-?45|10/100/1000|gigabit)?", "portas"),
        (r"poe", "PoE"),
        (r"vlan", "VLAN"),
        (r"gerenci[aá]vel|managed", "gerenciavel"),
        (r"snmp", "SNMP"),
        (r"sfp\+?", "SFP"),
        (r"rack\s*19", "rack 19"),
    ]
    lowered = text.lower()
    for pattern, label in patterns:
        match = re.search(pattern, lowered, re.IGNORECASE)
        if not match:
            continue
        if match.groups() and match.group(1).isdigit():
            specs.append(f"{match.group(1)} {label}")
        elif label not in specs:
            specs.append(label)
    return specs


def _extract_items_from_inline_table(text: str, *, max_items: int) -> list[ExtractedEditalItem]:
    """Extract PNCP-style inline item tables: "Item Descricao Unidade QTD"."""
    header = re.search(
        r"\bItem\s+Descri[cç][aã]o\s+Unidade\s+QTD\b",
        text,
        re.IGNORECASE,
    )
    if not header:
        return []

    tail = text[header.end() :]
    # Stop before long legal sections when possible; this keeps the parser focused
    # on the item table extracted by pypdf.
    stop = re.search(
        r"\b(?:DA\s+HABILITA[CÇ][AÃ]O|DAS\s+SAN[CÇ][OÕ]ES|MINUTA\s+DE\s+CONTRATO|"
        r"TERMO\s+DE\s+REFER[ÊE]NCIA|ANEXO\s+[IVX]+)\b",
        tail,
        re.IGNORECASE,
    )
    if stop:
        tail = tail[: stop.start()]

    unit_pattern = r"(?:UND|UN|UNIDADE|KG|M|M2|M3|CX|PCT|PC|SERV|HORA|MES)"
    row_pattern = re.compile(
        rf"(?:^|\s)(?P<num>\d{{1,4}})\s+"
        rf"(?P<desc>.*?)(?:\s+(?P<unit>{unit_pattern})\s+(?P<qty>[0-9]+(?:[.,][0-9]+)?))"
        rf"(?=\s+\d{{1,4}}\s+[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ0-9]|\s*$)",
        re.IGNORECASE | re.DOTALL,
    )

    items: list[ExtractedEditalItem] = []
    for match in row_pattern.finditer(tail):
        description = _clean(match.group("desc"))
        if len(description) < 12:
            continue
        # Avoid clause-like rows that leaked into the table window.
        if re.match(r"^\d+(?:\.\d+)+\s", description):
            continue

        items.append(
            ExtractedEditalItem(
                numero_item=_clean(match.group("num")),
                tipo=_infer_type(description),
                descricao=description[:2400],
                quantidade=_to_float(match.group("qty")),
                unidade=(match.group("unit") or "").upper(),
                especificacoes=_extract_specs(description),
            )
        )
        if len(items) >= max_items:
            break

    return items if len(items) >= 2 else []


def extract_items_from_edital_text(text: str, *, max_items: int = 80) -> list[ExtractedEditalItem]:
    if not text.strip():
        return []

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    inline_items = _extract_items_from_inline_table(normalized, max_items=max_items)
    if inline_items:
        return inline_items

    pattern = re.compile(
        r"(?:^|\n)\s*(\d{1,4})\s*[-–]\s*"
        r"([^\n]{2,120}?)"
        r"(?:\s+Descrição\s+Detalhada:\s*|\n)"
        r"(.*?)(?=(?:\n\s*\d{1,4}\s*[-–]\s*[^\n]{2,120}?(?:\s+Descrição\s+Detalhada:|\n))|\Z)",
        re.IGNORECASE | re.DOTALL,
    )

    items: list[ExtractedEditalItem] = []
    for match in pattern.finditer(normalized):
        numero = _clean(match.group(1))
        title = _clean(match.group(2))
        body = _clean(match.group(3))
        description = _clean(f"{title}. {body}") if body else title
        if len(description) < 12:
            continue

        quantity_match = re.search(
            r"\bQuantidade\s+Total:\s*([0-9.,]+)\s*([A-Z]{1,6})?",
            description,
            re.IGNORECASE,
        )
        if quantity_match is None:
            quantity_match = re.search(
                r"\bQuantidade(?:\s+\w+)?:\s*([0-9.,]+)\s*([A-Z]{1,6})?",
                description,
                re.IGNORECASE,
        )
        quantity = _to_float(quantity_match.group(1)) if quantity_match else None
        unit = quantity_match.group(2) if quantity_match and quantity_match.group(2) else None
        if unit and unit.lower().startswith("quanti"):
            unit = None

        items.append(
            ExtractedEditalItem(
                numero_item=numero,
                tipo=_infer_type(description),
                descricao=description[:2400],
                quantidade=quantity,
                unidade=unit,
                especificacoes=_extract_specs(description),
            )
        )
        if len(items) >= max_items:
            break

    if items:
        return items

    fallback_blocks = [
        _clean(block)
        for block in re.split(r"\n{2,}", normalized)
        if "switch" in block.lower() and len(_clean(block)) > 20
    ]
    return [
        ExtractedEditalItem(
            numero_item=str(index),
            tipo=_infer_type(block),
            descricao=block[:2400],
            especificacoes=_extract_specs(block),
        )
        for index, block in enumerate(fallback_blocks[:max_items], start=1)
    ]


def build_analysis_payload(edital: Any) -> dict[str, Any]:
    text = edital.full_text or ""
    items = extract_items_from_edital_text(text)
    return {
        "id_pncp": str(edital.id),
        "numero_ata": None,
        "orgao": None,
        "data_assinatura": None,
        "vigencia": None,
        "objeto": _clean(text[:600]) if text else None,
        "itens": [asdict(item) for item in items],
        "tokens_usados": 0,
        "aviso": None if items else "Nenhum item tecnico encontrado no texto extraido.",
    }


def sync_analysis_to_crm(db: Any, edital: Any, user: Any) -> dict[str, Any]:
    """Create/update a CRM notice from an analyzed edital.

    The CRM is the commercial working area, so analyzed edital items must land
    there as triage items instead of staying only in the technical `requirements`
    table.
    """
    from app.crm.models import CrmNotice, CrmNoticeProduct, CrmNoticeStage
    from app.services.crm_notice_sync import sync_notice_relationships

    items = extract_items_from_edital_text(edital.full_text or "")
    if not items:
        return {"notice_id": None, "products": 0}

    tenant_id = getattr(user, "tenant_id", None)
    tenant_slug = getattr(getattr(user, "tenant", None), "slug", None)
    import_key = f"edital:{tenant_slug or tenant_id}:{edital.id}"
    notice = (
        db.query(CrmNotice)
        .filter(CrmNotice.tenant_id == tenant_id, CrmNotice.import_key == import_key)
        .first()
    )

    number = f"EDITAL-{edital.id}"
    if notice is None:
        notice = CrmNotice(
            tenant_id=tenant_id,
            number=number,
            tor_id=number,
            title=getattr(edital, "filename", None) or number,
            import_key=import_key,
            stage=CrmNoticeStage.TRIAGE,
            created_by=getattr(user, "id", None),
            owner_id=getattr(user, "id", None),
        )
        db.add(notice)
        db.flush()
    else:
        notice.title = notice.title or getattr(edital, "filename", None) or number
        if not notice.stage:
            notice.stage = CrmNoticeStage.TRIAGE

    existing_by_item = {
        str(product.item_number): product
        for product in notice.notice_products
        if product.item_number is not None
    }
    changed = 0
    for index, item in enumerate(items, start=1):
        item_number = str(item.numero_item or index)
        product = existing_by_item.get(item_number)
        values = {
            "tenant_id": tenant_id,
            "notice_id": notice.id,
            "item_number": item_number,
            "description": item.descricao,
            "quantity": item.quantidade or 1.0,
            "unit": item.unidade,
            "sort_order": index,
            "notes": "; ".join(item.especificacoes or []) or item.observacoes,
        }
        if product is None:
            product = CrmNoticeProduct(**values)
            db.add(product)
            changed += 1
        else:
            for key, value in values.items():
                setattr(product, key, value)
            changed += 1

    sync_notice_relationships(db, notice, created_by=getattr(user, "id", None))
    return {"notice_id": notice.id, "products": changed}
