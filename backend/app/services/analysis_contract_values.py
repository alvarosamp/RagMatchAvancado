"""Presentation-only adapters for structured V8 commercial terms."""

from __future__ import annotations

from typing import Any


def display_contract_term(value: Any) -> str | None:
    """Keep the literal clause while avoiding dict repr in text DB columns."""
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return str(value) if value is not None else None
    literal = value.get("texto_original")
    if isinstance(literal, str) and literal.strip() and literal.strip().upper() != "N/C":
        return literal.strip()
    amount = value.get("valor")
    if amount is None or amount == "N/C":
        return "N/C"
    parts = [str(value.get("operador") or "").strip(), str(amount).strip(), str(value.get("unidade") or "").strip()]
    condition = str(value.get("condicao") or "").strip()
    if condition and condition != "N/C":
        parts.append(condition)
    return " ".join(part for part in parts if part)
