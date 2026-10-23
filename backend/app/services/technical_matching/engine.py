from __future__ import annotations

import hashlib
import json
import math
import operator
from typing import Any

from .normalizer import RULES, canonical_category, canonical_name

from .comparators import RANGE_OPERATORS, SET_OPERATORS, sample_of, normalize_operand, satisfies as advanced_satisfies, scoped_sources, aggregate_groups, numeric_scalars

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
    if not isinstance(requirements, (dict, list)) or not requirements:
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

    entries = requirements.items() if isinstance(requirements, dict) else ((r.get("atributo", "") if isinstance(r, dict) else "", r) for r in requirements)
    for name, rule in entries:
        canonical = canonical_name(name) if isinstance(name, str) else ""
        detail = _pending(canonical, "Regra invalida")
        details.append(detail)
        if not isinstance(rule, dict) or not canonical:
            continue
        op = rule.get("operador", "==")
        required = rule.get("obrigatorio", True)
        weight = rule.get("peso", 1)
        detail.update(operador=op, exigido=rule.get("valor"), obrigatorio=required,
                      id=rule.get("id"), texto_original=rule.get("texto_original"),
                      origem=rule.get("origem") or rule.get("fonte"),
                      evidencias=rule.get("evidencias"), escopo=rule.get("escopo") or rule.get("condicao"),
                      grupo_logico=rule.get("grupo_logico"),
                      operador_logico=rule.get("operador_logico", rule.get("logica", "E")))
        if not isinstance(required, bool):
            detail["obrigatoriedade_original"] = required
            detail["obrigatorio"] = True
        if not isinstance(detail["operador_logico"], str) or (detail["grupo_logico"] is not None and not isinstance(detail["grupo_logico"], str)):
            detail["grupo_logico"] = None
            detail["motivo"] = "Grupo ou operador logico invalido"
            continue
        if rule.get("alternativas") is not None or rule.get("valores") is not None:
            detail["motivo"] = "Informe alternativas como valor de um operador em/contem_algum"
            continue
        if detail["operador_logico"] not in {"E", "AND", "and", "OU", "OR", "or"} or (detail["operador_logico"] in {"OU", "OR", "or"} and not detail["grupo_logico"]):
            detail["motivo"] = "Grupo logico ausente ou operador logico desconhecido"
            continue
        if (not isinstance(required, bool) or isinstance(weight, bool)
                or not isinstance(weight, (int, float)) or not math.isfinite(weight) or weight <= 0
                or not isinstance(op, str) or op not in (OPERATORS.keys() | RANGE_OPERATORS | SET_OPERATORS) or "valor" not in rule):
            continue
        detail["peso"] = weight
        definition = RULES["attributes"].get(canonical, {})
        expected = rule["valor"]
        sample = sample_of(expected)
        inferred_kind = "boolean" if isinstance(sample, bool) else ("number" if isinstance(sample, (int, float)) else "string")
        kind = definition.get("type", inferred_kind)
        unit = definition.get("unit") or rule.get("unidade")
        sources = indexed.get(canonical, [])
        detail["fontes"] = [{"atributo": key, "valor": value} for key, value in sources]
        detail["encontrado"] = sources[0][1] if len(sources) == 1 else None
        try:
            sources = scoped_sources(sources, detail["escopo"])
            detail["fontes"] = [{"atributo": key, "valor": value} for key, value in sources]
            detail["encontrado"] = sources[0][1] if len(sources) == 1 else None
            if kind != "number" and op in {">", "<", ">=", "<="}:
                raise ValueError("Operador nao permitido para este tipo")
            if "unidade" in rule:
                if isinstance(expected, dict) and (op not in RANGE_OPERATORS or expected.get("unidade")):
                    raise ValueError("Informe a unidade no valor ou na regra, sem duplicacao")
                expected = {"valor": expected, "unidade": rule["unidade"]}
            normalized_expected = normalize_operand(expected, op, kind=kind, unit=unit)
            if not sources:
                raise ValueError("Atributo ausente no produto")
            values = [normalize_operand(value, "==" if op in {"em", "in"} else op, kind=kind, unit=unit) for _, value in sources]
            if any(value != values[0] for value in values[1:]):
                raise ValueError("Aliases do atributo possuem valores conflitantes")
            normalized_found = values[0]
            domain_values = numeric_scalars([normalized_expected, *values])
            if definition.get("integer") and any(not float(v).is_integer() for v in domain_values):
                raise ValueError("Contagem deve ser inteira")
            if "minimum" in definition and any(v < definition["minimum"] for v in domain_values):
                raise ValueError("Valor fora do dominio do atributo")
            # Strict JSON typing avoids True == 1 and lexical numeric comparisons.
            if type(normalized_expected) is not type(normalized_found) and kind != "number" and op not in SET_OPERATORS:
                raise ValueError("Tipos incompativeis")
            satisfies = (OPERATORS[op](normalized_found, normalized_expected) if op in OPERATORS
                         else advanced_satisfies(normalized_found, normalized_expected, op))
            if satisfies and item.get("exigir_evidencia") and not all(_documented(v) for _, v in sources):
                raise ValueError("Valor sem evidencia documental revisada")
            detail.update(
                status="ATENDE" if satisfies else "NAO_ATENDE",
                motivo="Comparacao deterministica", exigido_normalizado=normalized_expected,
                encontrado_normalizado=normalized_found, unidade=unit,
            )
        except (ValueError, TypeError, OverflowError) as exc:
            detail["motivo"] = str(exc)

    if item.get("conflitos_documentais") or item.get("requisitos_gerais_aplicaveis"):
        details.append(_pending("documentacao", "Conflitos ou requisitos gerais exigem revisao"))

    effective, group_results = aggregate_groups(details)
    failed = [d["atributo"] for d in effective if d["obrigatorio"] is True and d["status"] == "NAO_ATENDE"]
    pending = [d["atributo"] for d in effective if d["status"] == "VERIFICAR"]
    status = "NAO_ATENDE" if failed else ("VERIFICAR" if pending else "ATENDE")
    # Scaling avoids overflow when multiple individually finite weights add up.
    scale = max((d["peso"] for d in effective), default=1) or 1
    total = sum(d["peso"] / scale for d in effective)
    known = sum(d["peso"] / scale for d in effective if d["status"] != "VERIFICAR")
    matched = sum(d["peso"] / scale for d in effective if d["status"] == "ATENDE")
    return {
        "versao_regras": RULES.get("version", "1.0.0"),
        "hash_requisitos": _hash(item), "hash_produto": _hash(product),
        "revisao_produto": product.get("revisao"), "variante_produto": product.get("variante"),
        "sku": product.get("sku"), "status": status,
        "score": round(matched / total, 4) if total else 0.0,
        "compatibilidade_conhecida": round(matched / known, 4) if known else None,
        "cobertura": round(known / total, 4) if total else 0.0,
        "falhas_obrigatorias": failed, "pendencias": pending, "detalhes": details, "grupos": group_results,
    }


def _pending(attribute: str, reason: str) -> dict[str, Any]:
    return {
        "atributo": attribute, "operador": None, "exigido": None, "encontrado": None,
        "obrigatorio": True, "peso": 1, "status": "VERIFICAR", "motivo": reason, "fontes": [],
    }


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def _documented(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    evidences = value.get("evidencias")
    return isinstance(evidences, list) and any(
        isinstance(e, dict) and e.get("revisado") is True
        and e.get("documento_id") and e.get("hash_documento")
        and isinstance(e.get("pagina"), int) and not isinstance(e.get("pagina"), bool) and e["pagina"] > 0
        for e in evidences
    )
