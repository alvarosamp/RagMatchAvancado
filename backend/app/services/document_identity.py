from __future__ import annotations

import hashlib
import re
from typing import Any


def content_hash(data: bytes | str | None) -> str:
    digest = hashlib.sha256()
    if isinstance(data, bytes):
        digest.update(data)
    elif data:
        digest.update(str(data).encode("utf-8", errors="ignore"))
    return digest.hexdigest()


def normalize_identifier(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def edital_business_key_from_result(result: dict[str, Any]) -> str | None:
    edital = result.get("edital") or {}
    n_interno = result.get("n_interno")
    if _meaningful(n_interno):
        return f"edital|n-interno|{normalize_identifier(n_interno)}"

    parts = [
        edital.get("numero_pregao"),
        edital.get("orgao"),
        edital.get("data_disputa"),
        edital.get("hora_disputa"),
    ]
    meaningful = [normalize_identifier(part) for part in parts if _meaningful(part)]
    if len(meaningful) < 2:
        return None
    return "edital|meta|" + hashlib.sha1("|".join(meaningful).encode("utf-8", errors="ignore")).hexdigest()[:16]


def edital_business_key_from_text(text: str | None, filename: str | None = None) -> str | None:
    source = " ".join(part for part in [filename or "", text or ""] if part)
    if len((text or "").strip()) < 400:
        return None

    numero = _first_match(
        source,
        [
            r"(?:preg[aã]o|concorr[eê]ncia|dispensa|processo|edital)\s*(?:eletr[oô]nico)?\s*(?:n[ºo.]*)?\s*([0-9]{1,6}[\/.-][0-9]{2,4})",
            r"\b(PE|PP|CE|CP|DL)\s*[- ]?\s*([0-9]{1,6}[\/.-][0-9]{2,4})\b",
        ],
    )
    orgao = _first_match(
        source,
        [
            r"(?:prefeitura|munic[ií]pio|c[aâ]mara|governo|secretaria|universidade|instituto)\s+(?:municipal\s+)?(?:de|do|da)?\s*([A-ZÁÀÂÃÉÈÊÍÓÔÕÚÇ][A-Za-zÁÀÂÃÉÈÊÍÓÔÕÚÇ\s.-]{3,80})",
            r"(?:[oó]rg[aã]o|unidade)\s*[:\-]\s*([A-Za-zÁÀÂÃÉÈÊÍÓÔÕÚÇ\s.-]{4,90})",
        ],
    )
    data = _first_match(source, [r"\b([0-3]?\d[\/.-][01]?\d[\/.-]20\d{2})\b"])

    meaningful = [normalize_identifier(part) for part in [numero, orgao, data] if _meaningful(part)]
    if not meaningful:
        return None
    if len(meaningful) == 1:
        meaningful.append(normalize_identifier(filename or ""))
    if len(meaningful) < 2:
        return None
    return "edital|ocr|" + hashlib.sha1("|".join(meaningful).encode("utf-8", errors="ignore")).hexdigest()[:16]


def is_unidentified_edital_result(result: dict[str, Any]) -> bool:
    edital = result.get("edital") or {}
    has_key = edital_business_key_from_result(result) is not None
    has_items = bool(result.get("itens_elegiveis") or result.get("itens"))
    has_source = any(_meaningful(edital.get(key)) for key in ("numero_pregao", "orgao", "data_disputa"))
    return not has_key or (not has_items and not has_source)


def is_unidentified_pdf_text(text: str | None, filename: str | None = None) -> bool:
    clean = (text or "").strip()
    if len(clean) < 400:
        return True
    return edital_business_key_from_text(clean, filename) is None


def _meaningful(value: Any) -> bool:
    return value is not None and str(value).strip() not in ("", "-", "N/C", "n/c")


def _first_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        groups = [group for group in match.groups() if group]
        if groups:
            return " ".join(groups).strip()
    return None
