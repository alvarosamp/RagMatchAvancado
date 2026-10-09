from __future__ import annotations

import math
import operator
from typing import Any

from .normalizer import RULES, canonical_category, canonical_name, normalize_value

OPERATORS = {"==": operator.eq, ">=": operator.ge, "<=": operator.le, ">": operator.gt, "<": operator.lt}


def compare_item_product(item: dict[str, Any], product: dict[str, Any]) -> dict[str, Any]:
    """Return a conservative, auditable decision for explicit JSON requirements.

    Invalid inputs and ambiguous catalog values produce VERIFICAR; only a
    demonstrated mandatory mismatch produces NAO_ATENDE. Scores never override
    those decisions. All scores are fractions between zero and one.
    """
    requirements = item.get("requisitos")
    attributes = product.get("atributos")
    attributes = attributes if isinstance(attributes, dict) else {}
    indexed: dict[str, list[tuple[str, Any]]] = {}
    for name, value in attributes.items():
        indexed.setdefault(canonical_name(name), []).append((name, value))
    details = []
    if not isinstance(requirements, dict) or not requirements:
        details.append(_pending("requisitos", "Requisitos estruturados ausentes ou invalidos"))
        requirements = {}

    wanted_category = canonical_category(item.get("categoria"))
    found_category = canonical_category(product.get("categoria"))
    if wanted_category:
        status = "VERIFICAR" if not found_category else ("ATENDE" if wanted_category == found_category else "NAO_ATENDE")
        details.append({
            "atributo": "categoria", "operador": "==", "exigido": item["categoria"],
            "encontrado": product.get("categoria"), "obrigatorio": True, "peso": 0,
            "status": status, "motivo": "Comparacao de categoria", "fontes": [],
        })

    for name, rule in requirements.items():
        canonical = canonical_name(name)
        detail = _pending(canonical, "Regra invalida")
        details.append(detail)
        if not isinstance(rule, dict):
            continue
        op = rule.get("operador", "==")
        required = rule.get("obrigatorio", True)
        weight = rule.get("peso", 1)
        detail.update(operador=op, exigido=rule.get("valor"), obrigatorio=required)
        if (not isinstance(required, bool) or isinstance(weight, bool)
                or not isinstance(weight, (int, float)) or not math.isfinite(weight) or weight <= 0
                or not isinstance(op, str) or op not in OPERATORS or "valor" not in rule):
            continue
        detail["peso"] = weight
        definition = RULES["attributes"].get(canonical, {})
        expected = rule["valor"]
        sample = expected.get("valor") if isinstance(expected, dict) else expected
        inferred_kind = "boolean" if isinstance(sample, bool) else ("number" if isinstance(sample, (int, float)) else "string")
        kind = definition.get("type", inferred_kind)
        unit = definition.get("unit") or rule.get("unidade")
        sources = indexed.get(canonical, [])
        detail["fontes"] = [{"atributo": key, "valor": value} for key, value in sources]
        detail["encontrado"] = sources[0][1] if len(sources) == 1 else None
        try:
            if kind != "number" and op != "==":
                raise ValueError("Operador nao permitido para este tipo")
            if "unidade" in rule:
                if isinstance(expected, dict):
                    raise ValueError("Informe a unidade no valor ou na regra, sem duplicacao")
                expected = {"valor": expected, "unidade": rule["unidade"]}
            normalized_expected = normalize_value(expected, kind=kind, unit=unit)
            if not sources:
                raise ValueError("Atributo ausente no produto")
            values = [normalize_value(value, kind=kind, unit=unit) for _, value in sources]
            if any(value != values[0] for value in values[1:]):
                raise ValueError("Aliases do atributo possuem valores conflitantes")
            normalized_found = values[0]
            # Strict JSON typing avoids True == 1 and lexical numeric comparisons.
            if type(normalized_expected) is not type(normalized_found) and kind != "number":
                raise ValueError("Tipos incompativeis")
            satisfies = OPERATORS[op](normalized_found, normalized_expected)
            detail.update(
                status="ATENDE" if satisfies else "NAO_ATENDE",
                motivo="Comparacao deterministica", exigido_normalizado=normalized_expected,
                encontrado_normalizado=normalized_found, unidade=unit,
            )
        except (ValueError, TypeError, OverflowError) as exc:
            detail["motivo"] = str(exc)

    failed = [d["atributo"] for d in details if d["obrigatorio"] is True and d["status"] == "NAO_ATENDE"]
    pending = [d["atributo"] for d in details if d["status"] == "VERIFICAR"]
    status = "NAO_ATENDE" if failed else ("VERIFICAR" if pending else "ATENDE")
    # Scaling avoids overflow when multiple individually finite weights add up.
    scale = max((d["peso"] for d in details), default=1) or 1
    total = sum(d["peso"] / scale for d in details)
    known = sum(d["peso"] / scale for d in details if d["status"] != "VERIFICAR")
    matched = sum(d["peso"] / scale for d in details if d["status"] == "ATENDE")
    return {
        "sku": product.get("sku"), "status": status,
        "score": round(matched / total, 4) if total else 0.0,
        "compatibilidade_conhecida": round(matched / known, 4) if known else None,
        "cobertura": round(known / total, 4) if total else 0.0,
        "falhas_obrigatorias": failed, "pendencias": pending, "detalhes": details,
    }


def _pending(attribute: str, reason: str) -> dict[str, Any]:
    return {
        "atributo": attribute, "operador": None, "exigido": None, "encontrado": None,
        "obrigatorio": True, "peso": 1, "status": "VERIFICAR", "motivo": reason, "fontes": [],
    }
