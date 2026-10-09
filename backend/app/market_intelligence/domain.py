"""Pure normalization and metric rules, also used by ingestion and training."""

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

PRICE_TYPES = {
    "reference_price",
    "supplier_cost",
    "minimum_viable_price",
    "offered_price",
    "winning_price",
    "sales_price",
    "list_price",
}
OUTCOMES = {"won", "lost", "disqualified"}


def normalize(value):
    text = (
        unicodedata.normalize("NFKD", str(value or ""))
        .encode("ascii", "ignore")
        .decode()
        .lower()
    )
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def tax_id(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def valid_cnpj(value):
    value = tax_id(value)
    if not re.fullmatch(r"[A-Z0-9]{12}\d{2}", value) or len(set(value)) == 1:
        return False
    numbers = [ord(char) - 48 for char in value[:12]]
    for weights, expected in [
        ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], value[12]),
        ([6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], value[13]),
    ]:
        remainder = sum(a * b for a, b in zip(numbers, weights)) % 11
        digit = 0 if remainder < 2 else 11 - remainder
        if digit != int(expected):
            return False
        numbers.append(digit)
    return True


def gtin(value):
    value = str(value or "").strip()
    if not re.fullmatch(r"\d{8}|\d{12,14}", value) or len(set(value)) == 1:
        return None
    check = (
        10
        - sum(int(n) * (3 if i % 2 == 0 else 1) for i, n in enumerate(value[-2::-1]))
        % 10
    ) % 10
    return value.zfill(14) if check == int(value[-1]) else None


def number(value, positive=False):
    if value is None or isinstance(value, bool) or str(value).strip() == "":
        return None
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or (positive and result <= 0):
            return None
        return result.quantize(Decimal("0.000001"))
    except (InvalidOperation, ValueError):
        return None


def ratio(a, b):
    return float(a / b) if a is not None and b is not None and b > 0 else None


def unit(value):
    key = normalize(value)
    return {
        "un": "UN",
        "und": "UN",
        "unidade": "UN",
        "unidades": "UN",
        "pc": "UN",
        "peca": "UN",
        "kg": "KG",
        "quilograma": "KG",
        "m": "M",
        "metro": "M",
        "l": "L",
        "litro": "L",
    }.get(key, str(value or "").strip().upper() or None)


def timestamp(value, default=None):
    if not value:
        return default
    result = (
        value
        if isinstance(value, datetime)
        else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    )
    if result.tzinfo is None:
        # Historical CRM columns store local Brasilia time, not UTC.
        from zoneinfo import ZoneInfo

        result = result.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
    return result.astimezone(timezone.utc)


def json_value(value):
    if isinstance(value, (datetime, Decimal)):
        return value.isoformat() if isinstance(value, datetime) else str(value)
    if hasattr(value, "value"):
        return value.value
    raise TypeError(f"Unsupported payload type: {type(value).__name__}")


def payload_hash(payload):
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=json_value,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def coverage(verdict, linked=False, candidates=False):
    if verdict == "ATENDE":
        return "covered" if linked else "pending_review"
    if verdict == "NAO_ATENDE":
        # Rejecting a selected product does not prove all catalogue options fail.
        return "rejected_selection"
    return "pending_review" if linked or candidates or verdict else "unassessed"


def technical_attributes(text):
    """Evidence-preserving numeric constraints; never overrides match verdicts."""
    rules = {
        "ports": r"(\d+)\s*portas?",
        "speed_gbps": r"(\d+(?:[.,]\d+)?)\s*gbps",
        "capacity_gb": r"(\d+(?:[.,]\d+)?)\s*gb\b",
        "voltage": r"(\d+)\s*v\b",
        "warranty_months": r"(\d+)\s*meses",
    }
    output = {}
    for key, pattern in rules.items():
        matches = list(re.finditer(pattern, str(text or ""), re.IGNORECASE))
        if matches:
            output[key] = [
                {
                    "value": float(m.group(1).replace(",", ".")),
                    "evidence": m.group(0),
                    "start": m.start(),
                    "end": m.end(),
                }
                for m in matches
            ]
    return output


def technical_conflicts(requirement, product):
    required, offered = technical_attributes(requirement), technical_attributes(product)
    return [
        {"attribute": key, "required": required[key], "offered": offered[key]}
        for key in required.keys() & offered.keys()
        if max(x["value"] for x in offered[key])
        < max(x["value"] for x in required[key])
    ]
