from __future__ import annotations

import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Any

RULES = json.loads(Path(__file__).with_name("rules.json").read_text(encoding="utf-8"))
# Factors relative to a common base within each dimension.
UNITS = {
    "w": ("power", 1), "kw": ("power", 1000),
    "mbps": ("speed", 1), "gbps": ("speed", 1000), "tbps": ("speed", 1000000),
    "m": ("length", 1), "km": ("length", 1000),
}


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    # SFP+ and SFP must stay different.
    return re.sub(r"[^a-z0-9]+", "_", value.lower().replace("+", "_plus")).strip("_")


ALIASES = {
    normalize_name(alias): name
    for name, definition in RULES["attributes"].items()
    for alias in [name, *definition["aliases"]]
}
CATEGORIES = {
    normalize_name(alias): name
    for name, aliases in RULES["categories"].items()
    for alias in [name, *aliases]
}


def canonical_name(name: str) -> str:
    normalized = normalize_name(name)
    return ALIASES.get(normalized, normalized)


def canonical_category(category: Any) -> str | None:
    if not isinstance(category, str) or not category.strip():
        return None
    normalized = normalize_name(category)
    return CATEGORIES.get(normalized, normalized)


def normalize_value(value: Any, *, kind: str, unit: str | None = None) -> Any:
    """Reject ambiguous values instead of extracting a convenient first number."""
    source_unit = None
    if isinstance(value, dict):
        source_unit = value.get("unidade")
        value = value.get("valor")
    if value is None or (isinstance(value, str) and value.strip().lower() in {"", "-", "n/a", "desconhecido"}):
        raise ValueError("Dado ausente")
    if kind == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            token = normalize_name(value)
            if token in {"sim", "true", "yes"}:
                return True
            if token in {"nao", "false", "no"}:
                return False
        raise ValueError("Booleano invalido ou ambiguo")
    if kind == "string":
        if not isinstance(value, str) or source_unit is not None:
            raise ValueError("Texto invalido")
        # Unlike attribute aliases, technical values retain punctuation:
        # "L2+" must not become equal to "L2", nor "1.0" to "1-0".
        normalized = " ".join(unicodedata.normalize("NFKC", value).casefold().split())
        if not normalized:
            raise ValueError("Texto vazio ou invalido")
        return normalized
    if kind != "number" or isinstance(value, bool):
        raise ValueError("Tipo invalido")
    if isinstance(value, str):
        parsed = re.fullmatch(r"\s*([+-]?\d+(?:[.,]\d+)?)\s*([a-zA-Z]+)?\s*", value)
        if not parsed:
            raise ValueError("Numero invalido ou ambiguo")
        value = float(parsed[1].replace(",", "."))
        inline_unit = parsed[2]
        if inline_unit and source_unit and inline_unit.lower() != str(source_unit).lower():
            raise ValueError("Unidades conflitantes no valor")
        source_unit = inline_unit or source_unit
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Numero nao finito ou invalido")
    if unit is not None:
        target = UNITS.get(str(unit).lower())
        source = UNITS.get(str(source_unit or unit).lower())
        if not target or not source or source[0] != target[0]:
            raise ValueError("Unidade desconhecida ou incompativel")
        value = value * source[1] / target[1]
    elif source_unit is not None:
        raise ValueError("Atributo sem unidade canonica definida")
    if not math.isfinite(value):
        raise ValueError("Conversao resultou em numero nao finito")
    return value
