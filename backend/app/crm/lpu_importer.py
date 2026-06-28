from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.crm.models import CrmCatalogProduct


@dataclass
class LpuImportSummary:
    sheets: int = 0
    processed: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "sheets": self.sheets,
            "processed": self.processed,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
        }


def import_lpu_catalog(
    path: Path,
    *,
    db: Session,
    tenant_id: int,
    user_id: int | None,
) -> dict[str, int]:
    workbook = load_workbook(path, data_only=True)
    summary = LpuImportSummary()

    for sheet in workbook.worksheets:
        header = [str(value or "").strip() for value in next(sheet.iter_rows(max_row=1, values_only=True))]
        if not any(header):
            continue
        summary.sheets += 1
        normalized_header = [_norm(value) for value in header]

        for row in sheet.iter_rows(min_row=2, values_only=True):
            record = _row_to_record(header, normalized_header, row, sheet.title)
            if not record:
                summary.skipped += 1
                continue

            summary.processed += 1
            existing = (
                db.query(CrmCatalogProduct)
                .filter(
                    CrmCatalogProduct.tenant_id == tenant_id,
                    CrmCatalogProduct.sku == record["sku"],
                )
                .first()
            )
            if existing:
                for key, value in record.items():
                    setattr(existing, key, value)
                db.add(existing)
                summary.updated += 1
            else:
                db.add(
                    CrmCatalogProduct(
                        tenant_id=tenant_id,
                        created_by=user_id,
                        **record,
                    )
                )
                summary.created += 1

    db.commit()
    return summary.as_dict()


def _row_to_record(
    header: list[str],
    normalized_header: list[str],
    row: tuple[Any, ...],
    sheet_name: str,
) -> dict[str, Any] | None:
    values = {normalized_header[index]: row[index] for index in range(min(len(row), len(header)))}
    brand = _clean_text(_get(values, "marca")) or "TOR"
    pn_tor = _clean_text(_get(values, "pn tor", "part number tor", "partnumber tor"))
    part_no = _clean_text(_get(values, "part no", "part number", "partno"))
    price = _to_float(_get(values, "preco", "preço", "price"))
    category = _category_from_sheet(sheet_name)

    if category == "switch":
        model = _clean_text(_get(values, "description")) or part_no or pn_tor
        description = _clean_text(_get(values, "vig")) or model
    else:
        description = _clean_text(_get(values, "description", "descricao", "descrição"))
        model = part_no or pn_tor or description

    sku = _valid_sku(pn_tor) or _valid_sku(part_no)
    if not sku or not description:
        return None

    name = " ".join(part for part in [brand, model] if part) or description
    keywords = " ".join(
        part
        for part in [
            brand,
            pn_tor,
            part_no,
            model,
            description,
            _clean_text(_get(values, "rate")),
            _clean_text(_get(values, "distance")),
        ]
        if part
    )
    notes = _clean_text(_get(values, "disponibilidade"))
    if notes:
        notes = f"Disponibilidade: {notes}"

    return {
        "name": name[:255],
        "description": description,
        "category": category,
        "brand": brand,
        "model": (model or sku)[:255],
        "specification": description,
        "sku": sku[:255],
        "keywords": keywords,
        "unit": "UN",
        "cost": price,
        "tax_percent": 0.0,
        "margin_percent": 0.0,
        "notes": notes,
        "is_active": True,
    }


def _get(values: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        normalized = _norm(key)
        if normalized in values:
            return values[normalized]
    return None


def _norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    replacements = str.maketrans("áàâãéêíóôõúüçº°", "aaaaeeiooouucoo")
    return " ".join(text.translate(replacements).replace("-", " ").split())


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _valid_sku(value: str) -> str:
    if not value or value in {"-", "0", "0.0"}:
        return ""
    return value


def _to_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("R$", "").replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _category_from_sheet(sheet_name: str) -> str:
    normalized = _norm(sheet_name)
    if "switch" in normalized:
        return "switch"
    if "cabo" in normalized:
        return "cabo"
    if "transceiver" in normalized:
        return "transceiver"
    return normalized or "produto"
