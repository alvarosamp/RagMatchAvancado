"""Pure aggregation of populated BI fields for demand rankings."""

from __future__ import annotations

import re
from typing import Any


BREAKDOWN_FIELDS = {
    "Switch": {
        "quantidade_portas": [("quantidade_portas",), ("switch", "interfaces", "portas_acesso_rj45_qtd")],
        "alimentacao_poe": [("alimentacao_poe",), ("switch", "poe", "poe_padroes")],
        "gerenciamento": [("gerenciamento",), ("switch", "gerenciamento", "gerenciamento_local")],
        "camada": [("camada",), ("switch", "camada_3", "protocolos_roteamento")],
        "portas_acesso": [("portas_acesso",), ("switch", "interfaces", "velocidades_porta")],
        "uplinks": [("uplinks",), ("switch", "interfaces", "uplinks_formatos")],
        "quantidade_uplinks": [("switch", "interfaces", "uplinks_qtd")],
        "potencia_poe_w": [("switch", "poe", "poe_budget_w")],
        "capacidade_comutacao_gbps": [("switch", "capacidade", "switching_capacity_gbps")],
        "vlan": [("switch", "camada_2", "vlan")],
        "roteamento": [("switch", "camada_3", "protocolos_roteamento")],
        "empilhamento": [("switch", "stacking_resiliencia", "stacking_tipo")],
        "gerenciamento_local": [("gerenciamento",), ("switch", "gerenciamento", "gerenciamento_local")],
        "gerenciamento_remoto": [("switch", "gerenciamento", "gerenciamento_remoto")],
        "classe": [("switch", "identificacao", "classe_switch")],
        "garantia_meses": [("switch", "comercial", "garantia_meses")],
    },
    "Access Point": {
        "tecnologia_wifi": [("tecnologia_wifi",), ("access_point", "radio", "padroes_ieee")],
        "ambiente": [("ambiente",), ("access_point", "identificacao", "ambiente_uso")],
        "alimentacao": [("alimentacao",), ("access_point", "energia_fisico", "poe_padroes")],
    },
    "Transceiver": {
        "formato": [("formato",), ("transceiver", "identificacao", "form_factor")],
        "velocidade": [("velocidade",), ("transceiver", "identificacao", "velocidade_nominal_gbps")],
        "tipo_meio": [("tipo_meio",), ("transceiver", "fibra_conector", "tipo_fibra")],
        "alcance": [("alcance",), ("transceiver", "fibra_conector", "alcance_m")],
    },
}
BREAKDOWN_FIELDS["Módulo óptico"] = BREAKDOWN_FIELDS["Transceiver"]
BREAKDOWN_FIELDS["Modulo optico"] = BREAKDOWN_FIELDS["Transceiver"]


def aggregate_feature_breakdowns(
    rows: list[Any], fields: dict[str, list[tuple[str, ...]]]
) -> dict[str, list[dict[str, Any]]]:
    """Rank values by units, item lines and distinct notices; omit unknown values."""
    grouped: dict[str, dict[str, dict[str, Any]]] = {field: {} for field in fields}
    for analysis_id, quantity, features in rows:
        if not isinstance(features, dict):
            continue
        try:
            units = max(float(quantity or 0), 0)
        except (TypeError, ValueError):
            units = 0
        for field, paths in fields.items():
            value = _first_documented_value(features, paths)
            if value is None:
                continue
            if field == "quantidade_portas":
                match = re.fullmatch(r"(\d+)\s*(?:portas?)?", value, flags=re.IGNORECASE)
                if match:
                    value = match.group(1)
            entry = grouped[field].setdefault(
                value, {"valor": value, "unidades": 0, "itens": 0, "_editais": set()}
            )
            entry["unidades"] += units
            entry["itens"] += 1
            entry["_editais"].add(analysis_id)
    return {
        field: [
            {
                "valor": entry["valor"],
                "unidades": entry["unidades"],
                "itens": entry["itens"],
                "editais": len(entry["_editais"]),
            }
            for entry in sorted(
                values.values(), key=lambda row: (-row["unidades"], -row["itens"], row["valor"])
            )
        ]
        for field, values in grouped.items()
    }


def _first_documented_value(features: dict[str, Any], paths: list[tuple[str, ...]]) -> str | None:
    for path in paths:
        value: Any = features
        for part in path:
            value = value.get(part) if isinstance(value, dict) else None
        if isinstance(value, str):
            value = " ".join(value.split())
            if value and value.casefold() not in {"n/c", "nc", "não identificado", "nao identificado"}:
                return value
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
    return None
